"""
orchestrator/agent.py — LangGraph StateGraph orchestrator.

Wires all tools into a reasoning loop:
  START → classify → search_kb → get_order → draft → route → (loop or END)

Uses LangGraph's StateGraph with TicketState as the shared state.
"""

from __future__ import annotations
import os
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END

from orchestrator.state import TicketState
from logger import get_logger
from exceptions import (
    ClassificationError,
    KnowledgeBaseError,
    NoRelevantChunksError,
    ResolutionError,
    EscalationError,
    SupportPilotError,
)
from tools.classify_ticket import classify_ticket
from tools.search_kb import search_kb
from tools.get_order_status import get_order_status
from tools.draft_reply import draft_reply
from tools.send_reply import send_reply, init_db

load_dotenv()
logger = get_logger("orchestrator.agent")


# ── Node functions ─────────────────────────────────────────────────────────────

def node_classify(state: TicketState) -> dict:
    """Node 1 — classifies the ticket with Groq."""
    logger.info(f"[NODE] classify | ticket_id={state['ticket_id']}")
    tool_log = list(state.get("tool_calls_log", []))
    error_log = list(state.get("error_log", []))

    try:
        result = classify_ticket(state["subject"], state["body"])
        tool_log.append("classify_ticket")
        return {
            "category":       result["category"],
            "priority":       result["priority"],
            "sentiment":      result["sentiment"],
            "tool_calls_log": tool_log,
            "error_log":      error_log,
        }
    except (ClassificationError, SupportPilotError) as e:
        logger.error(f"Classification failed: {e}")
        error_log.append(f"classify_ticket: {e}")
        tool_log.append("classify_ticket[FAILED]")
        return {
            "category":       "general",
            "priority":       "medium",
            "sentiment":      "neutral",
            "tool_calls_log": tool_log,
            "error_log":      error_log,
        }


def node_search_kb(state: TicketState) -> dict:
    """Node 2 — retrieves relevant KB chunks with ChromaDB."""
    logger.info(f"[NODE] search_kb | ticket_id={state['ticket_id']}")
    tool_log = list(state.get("tool_calls_log", []))
    error_log = list(state.get("error_log", []))

    query = f"{state['subject']} {state['body']}"

    try:
        chunks = search_kb(query, category=state.get("category"))
        tool_log.append("search_kb")
        return {"retrieved_chunks": chunks, "tool_calls_log": tool_log, "error_log": error_log}
    except NoRelevantChunksError:
        logger.warning("No KB chunks found — proceeding with empty context")
        tool_log.append("search_kb[NO_RESULTS]")
        return {"retrieved_chunks": [], "tool_calls_log": tool_log, "error_log": error_log}
    except KnowledgeBaseError as e:
        logger.error(f"KB search error: {e}")
        error_log.append(f"search_kb: {e}")
        tool_log.append("search_kb[FAILED]")
        return {"retrieved_chunks": [], "tool_calls_log": tool_log, "error_log": error_log}


def node_get_order(state: TicketState) -> dict:
    """Node 3 — looks up order status if an order ID is present."""
    logger.info(f"[NODE] get_order | ticket_id={state['ticket_id']}")
    tool_log = list(state.get("tool_calls_log", []))
    error_log = list(state.get("error_log", []))

    try:
        order_info = get_order_status(state["body"])
        tool_log.append("get_order_status")
        return {"order_info": order_info, "tool_calls_log": tool_log, "error_log": error_log}
    except SupportPilotError as e:
        logger.error(f"Order lookup failed: {e}")
        error_log.append(f"get_order_status: {e}")
        tool_log.append("get_order_status[FAILED]")
        return {"order_info": None, "tool_calls_log": tool_log, "error_log": error_log}


def node_draft(state: TicketState) -> dict:
    """Node 4 — drafts the reply with Gemini."""
    logger.info(f"[NODE] draft | ticket_id={state['ticket_id']} retry={state.get('retry_count', 0)}")
    tool_log = list(state.get("tool_calls_log", []))
    error_log = list(state.get("error_log", []))

    try:
        result = draft_reply(
            subject=state["subject"],
            body=state["body"],
            category=state.get("category", "general"),
            sentiment=state.get("sentiment", "neutral"),
            retrieved_chunks=state.get("retrieved_chunks") or [],
            order_info=state.get("order_info"),
            retry_count=state.get("retry_count", 0),
        )
        tool_log.append("draft_reply")
        return {
            "draft_reply":    result["reply"],
            "confidence":     result["confidence"],
            "tool_calls_log": tool_log,
            "error_log":      error_log,
        }
    except SupportPilotError as e:
        logger.error(f"Draft reply failed: {e}")
        error_log.append(f"draft_reply: {e}")
        tool_log.append("draft_reply[FAILED]")
        return {
            "draft_reply":    None,
            "confidence":     0.0,
            "tool_calls_log": tool_log,
            "error_log":      error_log,
        }


def node_send(state: TicketState) -> dict:
    """Node 5 — persists the ticket and simulates sending the reply."""
    logger.info(f"[NODE] send | ticket_id={state['ticket_id']} status={state.get('status')}")
    tool_log = list(state.get("tool_calls_log", []))
    error_log = list(state.get("error_log", []))

    try:
        send_reply(
            ticket_id=state["ticket_id"],
            customer_email=state["customer_email"],
            subject=state["subject"],
            body=state["body"],
            source=state["source"],
            category=state.get("category"),
            priority=state.get("priority"),
            sentiment=state.get("sentiment"),
            draft_reply=state.get("draft_reply"),
            confidence=state.get("confidence"),
            status=state.get("status", "pending"),
            escalation_reason=state.get("escalation_reason"),
            retry_count=state.get("retry_count", 0),
            tool_calls_log=tool_log,
            error_log=error_log,
        )
        tool_log.append("send_reply")
    except SupportPilotError as e:
        logger.error(f"Send/save failed: {e}")
        error_log.append(f"send_reply: {e}")
        tool_log.append("send_reply[FAILED]")

    return {"tool_calls_log": tool_log, "error_log": error_log}


# ── Routing logic ─────────────────────────────────────────────────────────────

def route_after_draft(state: TicketState) -> str:
    """
    Decides what to do after drafting:
    - confidence >= threshold → resolve
    - retries remaining       → retry (back to draft node)
    - retries exhausted       → escalate
    """
    confidence = state.get("confidence", 0.0) or 0.0
    retry_count = state.get("retry_count", 0) or 0
    max_retries = int(os.getenv("MAX_RETRIES", 2))
    threshold = float(os.getenv("CONFIDENCE_THRESHOLD", 0.80))

    logger.info(
        f"[ROUTE] confidence={confidence:.2f} threshold={threshold} "
        f"retry={retry_count}/{max_retries}"
    )

    if confidence >= threshold:
        logger.info("[ROUTE] → resolve")
        return "resolve"

    if retry_count < max_retries:
        logger.info(f"[ROUTE] → retry (attempt {retry_count + 1})")
        return "retry"

    logger.warning("[ROUTE] → escalate (retries exhausted)")
    return "escalate"


def node_resolve(state: TicketState) -> dict:
    """Marks ticket as resolved."""
    logger.info(f"[NODE] resolve | ticket_id={state['ticket_id']}")
    return {"status": "resolved", "escalation_reason": None}


def node_retry(state: TicketState) -> dict:
    """Increments retry counter and clears the previous draft."""
    retry_count = (state.get("retry_count") or 0) + 1
    logger.info(f"[NODE] retry | ticket_id={state['ticket_id']} new_count={retry_count}")
    return {
        "retry_count": retry_count,
        "draft_reply": None,
        "confidence":  None,
    }


def node_escalate(state: TicketState) -> dict:
    """Marks ticket as escalated with a reason."""
    confidence = state.get("confidence", 0.0) or 0.0
    reason = (
        f"Confidence {confidence:.2f} below threshold after "
        f"{state.get('retry_count', 0)} retries"
    )
    logger.warning(f"[NODE] escalate | ticket_id={state['ticket_id']} | {reason}")
    return {"status": "escalated", "escalation_reason": reason}


# ── Graph construction ─────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """Constructs and compiles the LangGraph StateGraph."""
    logger.info("Building LangGraph StateGraph")

    builder = StateGraph(TicketState)

    # Register nodes
    builder.add_node("classify",  node_classify)
    builder.add_node("search_kb", node_search_kb)
    builder.add_node("get_order", node_get_order)
    builder.add_node("draft",     node_draft)
    builder.add_node("resolve",   node_resolve)
    builder.add_node("retry",     node_retry)
    builder.add_node("escalate",  node_escalate)
    builder.add_node("send",      node_send)

    # Linear flow up to draft
    builder.add_edge(START,       "classify")
    builder.add_edge("classify",  "search_kb")
    builder.add_edge("search_kb", "get_order")
    builder.add_edge("get_order", "draft")

    # Conditional routing after draft
    builder.add_conditional_edges(
        "draft",
        route_after_draft,
        {
            "resolve":  "resolve",
            "retry":    "retry",
            "escalate": "escalate",
        },
    )

    # Retry loops back to draft
    builder.add_edge("retry",   "draft")

    # Both resolve and escalate go to send
    builder.add_edge("resolve",  "send")
    builder.add_edge("escalate", "send")

    # Send is the terminal node
    builder.add_edge("send", END)

    graph = builder.compile()
    logger.info("LangGraph StateGraph compiled successfully")
    return graph


# Module-level compiled graph (initialised once)
def get_graph():
    init_db()
    return build_graph()
