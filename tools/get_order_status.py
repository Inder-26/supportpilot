"""
tools/get_order_status.py — Agent tool 3.

Mock order status lookup. In production this would call a real
ecommerce API (Shopify, WooCommerce, etc).

Returns: dict with order details or None if not found
"""

from __future__ import annotations
import re
from datetime import datetime, timedelta

from logger import get_logger
from exceptions import SupportPilotError

logger = get_logger("tools.get_order_status")

# Mock order database
_MOCK_ORDERS: dict[str, dict] = {
    "ORD-1001": {
        "order_id": "ORD-1001",
        "status": "delivered",
        "item": "Wireless Headphones",
        "placed_on": (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d"),
        "delivered_on": (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d"),
        "tracking": "TRK99281827",
        "amount": 2499.00,
    },
    "ORD-1002": {
        "order_id": "ORD-1002",
        "status": "in_transit",
        "item": "Mechanical Keyboard",
        "placed_on": (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d"),
        "delivered_on": None,
        "tracking": "TRK88192738",
        "estimated_delivery": (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d"),
        "amount": 4999.00,
    },
    "ORD-1003": {
        "order_id": "ORD-1003",
        "status": "processing",
        "item": "USB-C Hub",
        "placed_on": datetime.now().strftime("%Y-%m-%d"),
        "delivered_on": None,
        "tracking": None,
        "amount": 1299.00,
    },
    "ORD-1004": {
        "order_id": "ORD-1004",
        "status": "refund_initiated",
        "item": "Laptop Stand",
        "placed_on": (datetime.now() - timedelta(days=15)).strftime("%Y-%m-%d"),
        "delivered_on": (datetime.now() - timedelta(days=8)).strftime("%Y-%m-%d"),
        "tracking": "TRK77361829",
        "amount": 1899.00,
        "refund_status": "processing — 3–5 business days",
    },
}


def _extract_order_id(text: str) -> str | None:
    """Extracts order ID pattern (ORD-XXXX) from free text."""
    match = re.search(r"ORD-\d{4,}", text.upper())
    return match.group(0) if match else None


def get_order_status(ticket_body: str) -> dict | None:
    """
    Extracts an order ID from the ticket body and looks it up.

    Args:
        ticket_body: full text of the customer's message

    Returns:
        dict with order details, or None if no order ID found

    Raises:
        SupportPilotError: on unexpected lookup failure
    """
    logger.info("Attempting order ID extraction from ticket body")

    order_id = _extract_order_id(ticket_body)

    if not order_id:
        logger.info("No order ID found in ticket body")
        return None

    logger.info(f"Looking up order | order_id={order_id}")

    order = _MOCK_ORDERS.get(order_id)

    if order:
        logger.info(f"Order found | order_id={order_id} status={order['status']}")
    else:
        logger.warning(f"Order not found in mock DB | order_id={order_id}")
        return {"order_id": order_id, "status": "not_found"}

    return order
