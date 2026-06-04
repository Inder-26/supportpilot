"""
api/models.py — Pydantic schemas for FastAPI endpoints.
"""

from __future__ import annotations
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime


class TicketRequest(BaseModel):
    customer_email: str
    subject: str
    body: str
    source: str = "form"

    @field_validator("subject", "body")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()

    @field_validator("source")
    @classmethod
    def valid_source(cls, v: str) -> str:
        allowed = {"email", "form", "chat", "slack", "api"}
        if v.lower() not in allowed:
            raise ValueError(f"source must be one of {allowed}")
        return v.lower()


class TicketResponse(BaseModel):
    ticket_id: str
    status: str
    message: str


class TicketRecord(BaseModel):
    ticket_id: str
    customer_email: str
    subject: str
    body: Optional[str] = None
    source: str
    category: Optional[str]
    priority: Optional[str]
    sentiment: Optional[str]
    status: str
    confidence: Optional[float]
    draft_reply: Optional[str] = None
    escalation_reason: Optional[str]
    retry_count: int
    created_at: str
    resolved_at: Optional[str]


class TicketListResponse(BaseModel):
    total: int
    tickets: list[TicketRecord]


class ErrorResponse(BaseModel):
    error: str
    details: Optional[dict] = None