"""
exceptions.py — custom exception hierarchy for SupportPilot.

All exceptions inherit from SupportPilotError so callers can
catch the base class or be specific.
"""


class SupportPilotError(Exception):
    """Base exception for all SupportPilot errors."""
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | details={self.details}"
        return self.message


# ── API / model errors ────────────────────────────────────────────────────────

class GroqAPIError(SupportPilotError):
    """Raised when the Groq API call fails."""


class GeminiAPIError(SupportPilotError):
    """Raised when the Gemini API call fails."""


class ModelTimeoutError(SupportPilotError):
    """Raised when a model call exceeds the allowed timeout."""


class InvalidModelResponseError(SupportPilotError):
    """Raised when a model returns a response that cannot be parsed."""


# ── RAG / knowledge base errors ───────────────────────────────────────────────

class KnowledgeBaseError(SupportPilotError):
    """Raised for any ChromaDB / knowledge-base failure."""


class KnowledgeBaseNotInitialisedError(KnowledgeBaseError):
    """Raised when the KB is queried before ingest has run."""


class NoRelevantChunksError(KnowledgeBaseError):
    """Raised when retrieval returns zero results above threshold."""


# ── Ticket / pipeline errors ──────────────────────────────────────────────────

class TicketValidationError(SupportPilotError):
    """Raised when an incoming ticket payload fails validation."""


class ClassificationError(SupportPilotError):
    """Raised when the classifier agent fails to produce a valid output."""


class ResolutionError(SupportPilotError):
    """Raised when the resolver cannot draft a reply after max retries."""


class EscalationError(SupportPilotError):
    """Raised when the escalation path itself fails (e.g. DB write error)."""


# ── Infrastructure errors ─────────────────────────────────────────────────────

class DatabaseError(SupportPilotError):
    """Raised for SQLite read/write failures."""


class ConfigurationError(SupportPilotError):
    """Raised when a required environment variable is missing or invalid."""
