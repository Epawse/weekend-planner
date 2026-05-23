"""Mock delivery order tool — simulates flower/cake delivery scheduling."""

import random
import string
from datetime import datetime

import structlog
from langchain_core.tools import tool

logger = structlog.get_logger()


def _generate_order_id() -> str:
    """Generate a realistic-looking order ID."""
    prefix = "DL"
    date_part = datetime.now().strftime("%Y%m%d")
    random_part = "".join(random.choices(string.digits, k=4))
    return f"{prefix}-{date_part}-{random_part}"


@tool
async def order_delivery(
    item_type: str,
    item_description: str = "",
    delivery_address: str = "",
    delivery_time: str = "",
    recipient: str = "",
    message_card: str = "",
) -> dict:
    """Place a delivery order for flowers, cake, or gifts (MOCK).

    Simulates delivery order placement. Interface matches future real API contract.

    Args:
        item_type: Type of item - "flowers", "cake", "gift"
        item_description: Specific item, e.g. "红玫瑰花束", "草莓蛋糕6寸"
        delivery_address: Delivery destination address.
        delivery_time: Desired delivery time, e.g. "15:00"
        recipient: Recipient name.
        message_card: Optional message card text.

    Returns:
        Dict with status and order confirmation including ETA.
    """
    try:
        # Simulate delivery time (30-60 minutes from order)
        eta_minutes = random.randint(30, 60)

        order_data = {
            "order_id": _generate_order_id(),
            "item_type": item_type,
            "item_description": item_description or f"精选{item_type}",
            "delivery_address": delivery_address,
            "delivery_time": delivery_time,
            "recipient": recipient,
            "message_card": message_card,
            "status": "accepted",
            "eta_minutes": eta_minutes,
            "price_yuan": _estimate_price(item_type),
            "message": f"订单已确认，预计{eta_minutes}分钟内送达",
        }

        logger.info(
            "delivery_order_mock_success",
            order_id=order_data["order_id"],
            item_type=item_type,
            eta=eta_minutes,
        )
        return {"status": "success", "data": order_data}

    except Exception as e:
        logger.error("delivery_order_mock_error", error=str(e))
        return {"status": "error", "message": f"Delivery order failed: {str(e)}"}


def _estimate_price(item_type: str) -> float:
    """Generate a realistic price based on item type."""
    price_ranges = {
        "flowers": (99.0, 299.0),
        "cake": (128.0, 268.0),
        "gift": (59.0, 199.0),
    }
    low, high = price_ranges.get(item_type, (50.0, 200.0))
    return round(random.uniform(low, high), 0)
