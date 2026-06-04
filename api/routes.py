"""
api/routes.py — FastAPI route definitions with exception handling.
"""

from __future__ import annotations
import uuid
import sqlite3
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import JSONResponse

from api.models import (
    TicketRequest, TicketResponse, TicketRecord,
    TicketListResponse, ErrorResponse
)
from orchestrator.agent import get_graph
from orchestrator.state import TicketState
from tools.send_reply import DB_PATH
from exceptions import (
    TicketValidationError,
    SupportPilotError,
    DatabaseError,
    ConfigurationError,
)
from logger import get_logger

logger = get_logger("api.routes")
router = APIRouter()

_graph = None


def _get_graph():
    global _graph
    if _graph is None:
        _graph = get_graph()
    return _graph


async def _run_pipeline(state: TicketState) -> None:
    """Runs the LangGraph pipeline in the background."""
    ticket_id = state["ticket_id"]
    logger.info(f"Pipeline starting | ticket_id={ticket_id}")
    try:
        graph = _get_graph()
        final_state = graph.invoke(state)
        logger.info(
            f"Pipeline complete | ticket_id={ticket_id} "
            f"status={final_state.get('status')} "
            f"confidence={final_state.get('confidence')}"
        )
    except ConfigurationError as e:
        logger.critical(f"Configuration error: {e}")
    except SupportPilotError as e:
        logger.error(f"Pipeline error | ticket_id={ticket_id} | {e}")
    except Exception as e:
        logger.exception(f"Unexpected pipeline error | ticket_id={ticket_id} | {e}")


@router.post(
    "/ticket",
    response_model=TicketResponse,
    status_code=202,
    summary="Submit a new support ticket",
)
async def submit_ticket(
    payload: TicketRequest,
    background_tasks: BackgroundTasks,
):
    """
    Accepts a new support ticket and kicks off the AI pipeline
    asynchronously. Returns immediately with a ticket_id.
    """
    ticket_id = f"TKT-{uuid.uuid4().hex[:8].upper()}"
    logger.info(
        f"Ticket received | ticket_id={ticket_id} "
        f"source={payload.source} email={payload.customer_email}"
    )

    initial_state: TicketState = {
        "ticket_id":       ticket_id,
        "customer_email":  payload.customer_email,
        "subject":         payload.subject,
        "body":            payload.body,
        "source":          payload.source,
        "category":        None,
        "priority":        None,
        "sentiment":       None,
        "retrieved_chunks": None,
        "order_info":      None,
        "draft_reply":     None,
        "confidence":      None,
        "retry_count":     0,
        "status":          "pending",
        "escalation_reason": None,
        "tool_calls_log":  [],
        "error_log":       [],
    }

    background_tasks.add_task(_run_pipeline, initial_state)

    return TicketResponse(
        ticket_id=ticket_id,
        status="pending",
        message="Ticket received. AI pipeline running.",
    )


@router.get(
    "/tickets",
    response_model=TicketListResponse,
    summary="List all tickets with optional filters",
)
async def list_tickets(
    status: str | None = Query(None, description="Filter by status: pending/resolved/escalated"),
    priority: str | None = Query(None, description="Filter by priority"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Returns a paginated list of tickets from the database."""
    logger.info(f"Listing tickets | status={status} priority={priority} limit={limit}")

    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row

        query = "SELECT * FROM tickets WHERE 1=1"
        params: list = []

        if status:
            query += " AND status = ?"
            params.append(status)
        if priority:
            query += " AND priority = ?"
            params.append(priority)

        count_row = conn.execute(
            f"SELECT COUNT(*) FROM tickets WHERE 1=1"
            + (" AND status = ?" if status else "")
            + (" AND priority = ?" if priority else ""),
            params,
        ).fetchone()
        total = count_row[0]

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        conn.close()

        tickets = [
            TicketRecord(
                ticket_id=row["ticket_id"],
                customer_email=row["customer_email"],
                subject=row["subject"],
                source=row["source"],
                category=row["category"],
                priority=row["priority"],
                sentiment=row["sentiment"],
                status=row["status"],
                confidence=row["confidence"],
                escalation_reason=row["escalation_reason"],
                retry_count=row["retry_count"] or 0,
                created_at=row["created_at"],
                resolved_at=row["resolved_at"],
            )
            for row in rows
        ]

        return TicketListResponse(total=total, tickets=tickets)

    except sqlite3.Error as e:
        logger.error(f"DB read error: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@router.get(
    "/ticket/{ticket_id}",
    response_model=TicketRecord,
    summary="Get a single ticket by ID",
)
async def get_ticket(ticket_id: str):
    """Returns the full record for a single ticket."""
    logger.info(f"Fetching ticket | ticket_id={ticket_id}")

    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()
        conn.close()
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    if not row:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")

    return TicketRecord(
        ticket_id=row["ticket_id"],
        customer_email=row["customer_email"],
        subject=row["subject"],
        body=row["body"],
        source=row["source"],
        category=row["category"],
        priority=row["priority"],
        sentiment=row["sentiment"],
        status=row["status"],
        confidence=row["confidence"],
        draft_reply=row["draft_reply"],
        escalation_reason=row["escalation_reason"],
        retry_count=row["retry_count"] or 0,
        created_at=row["created_at"],
        resolved_at=row["resolved_at"],
    )


@router.get("/health", summary="Health check")
async def health():
    return {"status": "ok", "service": "SupportPilot"}