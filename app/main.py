"""FastAPI app: REST API + static web UI for support ticket classification."""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from app.classifier import classify_ticket
from app.logging_config import logger
from app.schemas import ClassificationResponse, TicketRequest

app = FastAPI(
    title="Support Ticket Classifier",
    description="Classifies customer support tickets into one of 6 categories using an LLM.",
    version="1.0.0",
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/classify", response_model=ClassificationResponse)
def classify(ticket: TicketRequest) -> dict:
    try:
        result = classify_ticket(ticket.text)
    except Exception as e:  # unexpected, non-LLM failure (e.g. misconfiguration)
        logger.info('INPUT="%s" | ERROR="%s"', ticket.text, e)
        raise HTTPException(status_code=500, detail=str(e)) from e

    logger.info(
        'INPUT="%s" | OUTPUT=category=%s confidence=%s',
        ticket.text, result["category"], result["confidence"],
    )
    return result


# Serve the web UI. Registered last so it doesn't shadow the API routes above.
app.mount("/", StaticFiles(directory="static", html=True), name="static")
