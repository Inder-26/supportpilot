"""
LLM-based support ticket classifier.

Sends the ticket text to an LLM (Groq's `llama-3.3-70b-versatile` by default,
via Groq's free, OpenAI-compatible API) and asks it to return a category from a
fixed list plus a confidence score. Confidence below CONFIDENCE_THRESHOLD (or
any category outside the fixed list) is coerced to "Others".
"""

from __future__ import annotations

import json
import os

from dotenv import load_dotenv
from groq import Groq

from app.schemas import CATEGORIES

load_dotenv()

CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.6"))

SYSTEM_PROMPT = f"""You are a customer support ticket classifier.
Classify the ticket into exactly one of these categories:
{", ".join(CATEGORIES)}

Respond ONLY with a valid JSON object, no markdown, no extra text:
{{"category": "<one of the categories above, verbatim>", "confidence": <float between 0 and 1>}}

Guidelines:
- "Login Issue": trouble signing in, forgotten/incorrect password errors during login.
- "Payment": billing, charges, refunds, deductions, transaction failures.
- "Account": profile/account settings changes, e.g. changing password, email, personal details (not login failures).
- "Delivery": order shipping, tracking, or non-arrival of physical goods.
- "Technical Issue": app/website crashes, bugs, errors unrelated to login or payment.
- "Others": anything that doesn't clearly fit the above, or if you are unsure.
"""

_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set. Add it to your .env file.")
        _client = Groq(api_key=api_key)
    return _client


def _call_llm(text: str) -> dict:
    """Calls the LLM and returns the parsed JSON response. Raises on failure."""
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    client = _get_client()

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        temperature=0,
        max_tokens=100,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content
    return json.loads(raw)


def classify_ticket(text: str) -> dict:
    """
    Classifies a support ticket's text.

    Returns a dict: {"category": str, "confidence": float}.
    Falls back to {"category": "Others", "confidence": 0.0} if the input is
    empty or the LLM call/parse fails, so the API never crashes on a bad
    upstream response.
    """
    if not text or not text.strip():
        return {"category": "Others", "confidence": 0.0}

    try:
        result = _call_llm(text)
        category = result.get("category", "Others")
        confidence = float(result.get("confidence", 0.0))
    except Exception:
        return {"category": "Others", "confidence": 0.0}

    if category not in CATEGORIES:
        category = "Others"

    if confidence < CONFIDENCE_THRESHOLD:
        category = "Others"

    return {"category": category, "confidence": round(confidence, 2)}
