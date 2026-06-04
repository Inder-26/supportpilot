"""
tools/draft_reply.py — Agent tool 4.

Uses OpenRouter (OpenAI-compatible API) to draft a customer support reply.
Model is configurable via OPENROUTER_MODEL in .env.

Free models available:
  - moonshotai/kimi-k2.6:free
  - nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free

Returns: dict with reply text and confidence score
"""

from __future__ import annotations
import os
import re

from openai import OpenAI
from dotenv import load_dotenv

from logger import get_logger
from exceptions import GeminiAPIError, InvalidModelResponseError

load_dotenv()
logger = get_logger("tools.draft_reply")

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

SYSTEM_PROMPT = """You are a helpful, empathetic customer support agent.
Draft a professional reply to a customer ticket.

Rules:
- Be warm but concise (2-4 short paragraphs max)
- Use the provided knowledge base context and order info if available
- Never make up information not present in the context
- End with an offer to help further
- On the very last line of your response, output ONLY this exact format:
  CONFIDENCE: 0.85
  where the number is a float between 0.0 and 1.0
  1.0 = you are certain this fully resolves the issue
  0.0 = you have no relevant information at all

Example ending:
We hope this helps! Feel free to reach out if you need anything else.

CONFIDENCE: 0.90
"""


def draft_reply(
    subject: str,
    body: str,
    category: str,
    sentiment: str,
    retrieved_chunks: list[str],
    order_info: dict | None,
    retry_count: int = 0,
) -> dict:
    """
    Drafts a support reply using OpenRouter.

    Args:
        subject:          ticket subject
        body:             ticket body
        category:         classified category
        sentiment:        classified sentiment
        retrieved_chunks: relevant KB chunks
        order_info:       order lookup result or None
        retry_count:      how many times we've retried (affects prompt)

    Returns:
        dict with keys: reply (str), confidence (float)

    Raises:
        GeminiAPIError:            on API failure (reused for OpenRouter errors)
        InvalidModelResponseError: if response cannot be parsed
    """
    logger.info(
        f"Drafting reply | category={category} sentiment={sentiment} "
        f"chunks={len(retrieved_chunks)} retry={retry_count}"
    )

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise GeminiAPIError("OPENROUTER_API_KEY not set in environment")

    model_name = os.getenv("OPENROUTER_MODEL", "moonshotai/kimi-k2.6:free")

    client = OpenAI(
        api_key=api_key,
        base_url=OPENROUTER_BASE_URL,
    )

    # Build context block
    context_parts = []
    if retrieved_chunks:
        context_parts.append("--- Knowledge Base Context ---")
        for i, chunk in enumerate(retrieved_chunks, 1):
            context_parts.append(f"[{i}] {chunk}")

    if order_info:
        context_parts.append("\n--- Order Information ---")
        for k, v in order_info.items():
            if v is not None:
                context_parts.append(f"{k}: {v}")

    retry_note = ""
    if retry_count > 0:
        retry_note = (
            f"\nNote: This is retry #{retry_count}. "
            "The previous draft was not confident enough. "
            "Try a different angle or be more specific using the context provided."
        )

    user_prompt = f"""Customer ticket:
Subject: {subject}
Body: {body}
Category: {category}
Sentiment: {sentiment}
{retry_note}

Context:
{chr(10).join(context_parts) if context_parts else "No specific context available."}

Draft a reply. End your response with CONFIDENCE: <score between 0.0 and 1.0>"""

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=600,
        )
    except Exception as e:
        logger.error(f"OpenRouter API call failed: {e}")
        raise GeminiAPIError(
            f"OpenRouter API call failed: {e}",
            details={"model": model_name}
        ) from e

    raw = response.choices[0].message.content or ""
    logger.debug(f"OpenRouter raw response: {repr(raw[:200])}")

    if not raw.strip():
        logger.error("OpenRouter returned empty response")
        raise InvalidModelResponseError(
            "OpenRouter returned empty response",
            details={"model": model_name}
        )

    # Extract confidence — handles bold markdown **CONFIDENCE: 0.9** or plain
    confidence_match = re.search(
        r"\*{0,2}CONFIDENCE\*{0,2}:\s*\*{0,2}([\d.]+)\*{0,2}",
        raw,
        re.IGNORECASE,
    )

    if not confidence_match:
        logger.warning(f"No CONFIDENCE score in response — defaulting to 0.6 | raw tail: {repr(raw[-100:])}")
        confidence = 0.6
    else:
        try:
            confidence = float(confidence_match.group(1))
            confidence = max(0.0, min(1.0, confidence))
        except ValueError:
            confidence = 0.6

    # Strip confidence line from reply text
    reply_text = re.sub(r"\n?\*{0,2}CONFIDENCE\*{0,2}:\s*\*{0,2}[\d.]+\*{0,2}", "", raw).strip()

    logger.info(
        f"Reply drafted | model={model_name} confidence={confidence:.2f} "
        f"length={len(reply_text)} chars"
    )

    return {
        "reply":      reply_text,
        "confidence": confidence,
    }