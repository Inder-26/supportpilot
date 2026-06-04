"""
tools/send_reply.py — Agent tool 5.

Persists the ticket result to SQLite.
In production this would also send an actual email/Slack message.
"""

from __future__ import annotations
import sqlite3
import os
from datetime import datetime
from pathlib import Path

from logger import get_logger
from exceptions import DatabaseError

logger = get_logger("tools.send_reply")

DB_PATH = Path(__file__).parent.parent / "supportpilot.db"


def _get_connection() -> sqlite3.Connection:
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        raise DatabaseError(f"Cannot connect to SQLite: {e}", details={"path": str(DB_PATH)}) from e


def init_db() -> None:
    """Creates the tickets table if it doesn't exist."""
    logger.info(f"Initialising database at {DB_PATH}")
    with _get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id       TEXT    NOT NULL UNIQUE,
                customer_email  TEXT    NOT NULL,
                subject         TEXT    NOT NULL,
                body            TEXT    NOT NULL,
                source          TEXT    NOT NULL,
                category        TEXT,
                priority        TEXT,
                sentiment       TEXT,
                draft_reply     TEXT,
                confidence      REAL,
                status          TEXT    NOT NULL DEFAULT 'pending',
                escalation_reason TEXT,
                retry_count     INTEGER DEFAULT 0,
                tool_calls_log  TEXT,
                error_log       TEXT,
                created_at      TEXT    NOT NULL,
                resolved_at     TEXT
            )
        """)
        conn.commit()
    logger.info("Database initialised")


def send_reply(
    ticket_id: str,
    customer_email: str,
    subject: str,
    body: str,
    source: str,
    category: str | None,
    priority: str | None,
    sentiment: str | None,
    draft_reply: str | None,
    confidence: float | None,
    status: str,
    escalation_reason: str | None,
    retry_count: int,
    tool_calls_log: list[str],
    error_log: list[str],
) -> dict:
    """
    Saves the final ticket state to SQLite.

    Args:
        All fields from TicketState.

    Returns:
        dict confirming the save with ticket_id and status.

    Raises:
        DatabaseError: on any SQLite failure.
    """
    logger.info(f"Saving ticket | ticket_id={ticket_id} status={status}")

    now = datetime.utcnow().isoformat()

    # Simulate sending email (log it)
    if status == "resolved" and draft_reply:
        logger.info(
            f"[SIMULATED EMAIL] To: {customer_email} | "
            f"Subject: Re: {subject} | "
            f"Confidence: {confidence:.2f}"
        )
    elif status == "escalated":
        logger.warning(
            f"[ESCALATED] ticket_id={ticket_id} | "
            f"reason={escalation_reason} | "
            f"customer={customer_email}"
        )

    try:
        with _get_connection() as conn:
            conn.execute(
                """
                INSERT INTO tickets (
                    ticket_id, customer_email, subject, body, source,
                    category, priority, sentiment,
                    draft_reply, confidence, status, escalation_reason,
                    retry_count, tool_calls_log, error_log,
                    created_at, resolved_at
                ) VALUES (
                    ?, ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?
                )
                ON CONFLICT(ticket_id) DO UPDATE SET
                    category         = excluded.category,
                    priority         = excluded.priority,
                    sentiment        = excluded.sentiment,
                    draft_reply      = excluded.draft_reply,
                    confidence       = excluded.confidence,
                    status           = excluded.status,
                    escalation_reason= excluded.escalation_reason,
                    retry_count      = excluded.retry_count,
                    tool_calls_log   = excluded.tool_calls_log,
                    error_log        = excluded.error_log,
                    resolved_at      = excluded.resolved_at
                """,
                (
                    ticket_id, customer_email, subject, body, source,
                    category, priority, sentiment,
                    draft_reply, confidence, status, escalation_reason,
                    retry_count,
                    ", ".join(tool_calls_log),
                    ", ".join(error_log),
                    now,
                    now if status in ("resolved", "escalated") else None,
                ),
            )
            conn.commit()
    except sqlite3.Error as e:
        logger.error(f"SQLite write failed: {e}")
        raise DatabaseError(
            f"Failed to save ticket {ticket_id}: {e}",
            details={"ticket_id": ticket_id}
        ) from e

    logger.info(f"Ticket saved | ticket_id={ticket_id} status={status}")
    return {"ticket_id": ticket_id, "status": status, "saved_at": now}
