"""Pydantic request/response models for the ticket classification API."""

from pydantic import BaseModel, Field

CATEGORIES = [
    "Login Issue",
    "Payment",
    "Account",
    "Delivery",
    "Technical Issue",
    "Others",
]


class TicketRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Raw support ticket text to classify")


class ClassificationResponse(BaseModel):
    category: str
    confidence: float
