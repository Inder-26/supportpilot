"""
tools/classify_ticket.py — Agent tool 1.

Uses Groq (llama-3.3-70b-versatile) with JSON structured output
to classify an incoming support ticket.

Returns: category, priority, sentiment
"""

from __future__ import annotations
import os
import json

from groq import Groq
from dotenv import load_dotenv

from logger import get_logger
from exceptions import GroqAPIError, ClassificationError, InvalidModelResponseError

load_dotenv()
logger = get_logger("tools.classify_ticket")

VALID_CATEGORIES  = {"billing", "technical", "shipping", "general", "refund", "account"}
VALID_PRIORITIES  = {"low", "medium", "high", "urgent"}
VALID_SENTIMENTS  = {"positive", "neutral", "negative", "angry"}

SYSTEM_PROMPT = """You are a customer support ticket classifier.
Analyse the ticket and respond ONLY with a valid JSON object — no markdown, no extra text.

JSON schema:
{
  "category":  one of ["billing","technical","shipping","refund","account","general"],
  "priority":  one of ["low","medium","high","urgent"],
  "sentiment": one of ["positive","neutral","negative","angry"],
  "reasoning": "one sentence explaining your classification"
}

Priority guide:
- urgent: system down, payment failed, account locked
- high:   order not received, billing dispute
- medium: product questions, tracking queries
- low:    general enquiries, feedback
"""


def classify_ticket(subject: str, body: str) -> dict:
    """
    Classifies a support ticket using Groq.

    Args:
        subject: ticket subject line
        body:    ticket body text

    Returns:
        dict with keys: category, priority, sentiment, reasoning

    Raises:
        GroqAPIError: if the API call fails
        InvalidModelResponseError: if JSON cannot be parsed
        ClassificationError: if required fields are missing
    """
    logger.info(f"Classifying ticket | subject='{subject[:60]}'")

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise GroqAPIError("GROQ_API_KEY not set in environment")

    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    client = Groq(api_key=api_key)

    user_message = f"Subject: {subject}\n\nBody:\n{body}"

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_message},
            ],
            temperature=0.1,
            max_tokens=256,
            response_format={"type": "json_object"},
        )
    except Exception as e:
        logger.error(f"Groq API call failed: {e}")
        raise GroqAPIError(f"Groq API call failed: {e}", details={"model": model}) from e

    raw = response.choices[0].message.content
    logger.debug(f"Groq raw response: {raw}")

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"Could not parse Groq JSON response: {raw}")
        raise InvalidModelResponseError(
            "Groq returned non-JSON output",
            details={"raw": raw}
        ) from e

    # Validate fields
    missing = [f for f in ("category", "priority", "sentiment") if f not in result]
    if missing:
        raise ClassificationError(
            f"Classifier response missing fields: {missing}",
            details={"result": result}
        )

    # Normalise to known values
    result["category"]  = result["category"].lower()  if result["category"].lower()  in VALID_CATEGORIES else "general"
    result["priority"]  = result["priority"].lower()  if result["priority"].lower()  in VALID_PRIORITIES else "medium"
    result["sentiment"] = result["sentiment"].lower() if result["sentiment"].lower() in VALID_SENTIMENTS else "neutral"

    logger.info(
        f"Classification done | category={result['category']} "
        f"priority={result['priority']} sentiment={result['sentiment']}"
    )
    return result
