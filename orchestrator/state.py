"""
orchestrator/state.py — shared state for the LangGraph pipeline.

Every agent node reads from and writes to this TypedDict.
LangGraph passes it through each node automatically.
"""

from __future__ import annotations
from typing import TypedDict, Optional


class TicketState(TypedDict):
    # ── Input ─────────────────────────────────────────────────────────────────
    ticket_id: str
    customer_email: str
    subject: str
    body: str
    source: str                        # "email" | "form" | "chat" | "slack"

    # ── Classifier output ────────────────────────────────────────────────────
    category: Optional[str]            # "billing" | "technical" | "shipping" | "general"
    priority: Optional[str]            # "low" | "medium" | "high" | "urgent"
    sentiment: Optional[str]           # "positive" | "neutral" | "negative" | "angry"

    # ── RAG output ───────────────────────────────────────────────────────────
    retrieved_chunks: Optional[list[str]]

    # ── Order tool output ────────────────────────────────────────────────────
    order_info: Optional[dict]

    # ── Resolver output ──────────────────────────────────────────────────────
    draft_reply: Optional[str]
    confidence: Optional[float]        # 0.0 → 1.0

    # ── Routing ──────────────────────────────────────────────────────────────
    retry_count: int
    status: Optional[str]              # "resolved" | "escalated" | "pending"
    escalation_reason: Optional[str]

    # ── Audit ────────────────────────────────────────────────────────────────
    tool_calls_log: list[str]          # ordered list of tool names called
    error_log: list[str]               # any non-fatal errors encountered
