"""
main.py — FastAPI application entry point.

Run with:
    uvicorn main:app --reload --port 8000
"""

from __future__ import annotations
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from api.routes import router
from exceptions import (
    SupportPilotError,
    TicketValidationError,
    ConfigurationError,
    DatabaseError,
)
from logger import get_logger

logger = get_logger("main")

app = FastAPI(
    title="SupportPilot",
    description="AI-powered customer support automation — multi-agent with RAG",
    version="1.0.0",
)

# ── Global exception handlers ─────────────────────────────────────────────────

@app.exception_handler(TicketValidationError)
async def validation_error_handler(request: Request, exc: TicketValidationError):
    logger.warning(f"Validation error: {exc}")
    return JSONResponse(status_code=422, content={"error": exc.message, "details": exc.details})


@app.exception_handler(ConfigurationError)
async def config_error_handler(request: Request, exc: ConfigurationError):
    logger.critical(f"Configuration error: {exc}")
    return JSONResponse(status_code=500, content={"error": "Server misconfiguration", "details": exc.details})


@app.exception_handler(DatabaseError)
async def db_error_handler(request: Request, exc: DatabaseError):
    logger.error(f"Database error: {exc}")
    return JSONResponse(status_code=500, content={"error": "Database error", "details": exc.details})


@app.exception_handler(SupportPilotError)
async def general_sp_error_handler(request: Request, exc: SupportPilotError):
    logger.error(f"SupportPilot error: {exc}")
    return JSONResponse(status_code=500, content={"error": exc.message, "details": exc.details})


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception on {request.url}: {exc}")
    return JSONResponse(status_code=500, content={"error": "Internal server error"})


# ── Routes ────────────────────────────────────────────────────────────────────

app.include_router(router, prefix="/api")


@app.get("/", include_in_schema=False)
async def serve_dashboard():
    return FileResponse(Path(__file__).parent / "dashboard" / "index.html")


@app.on_event("startup")
async def startup():
    logger.info("SupportPilot starting up")
    import os
    from dotenv import load_dotenv
    from tools.send_reply import init_db   # add this import
    load_dotenv()
    init_db()                              # add this line — creates table immediately
    if not os.getenv("GROQ_API_KEY"):
        logger.warning("GROQ_API_KEY not set — classifier will fail")
    if not os.getenv("GEMINI_API_KEY"):
        logger.warning("GEMINI_API_KEY not set — resolver will fail")
    logger.info("SupportPilot ready at http://localhost:8000")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
