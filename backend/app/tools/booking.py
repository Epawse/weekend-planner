"""Mock booking/reservation tool — simulates making reservations."""

import random
import string
from datetime import datetime

import structlog
from langchain_core.tools import tool

logger = structlog.get_logger()


def _generate_confirmation_code() -> str:
    """Generate a realistic-looking confirmation code."""
    prefix = "BK"
    date_part = datetime.now().strftime("%Y%m%d")
    random_part = "".join(random.choices(string.digits, k=3))
    return f"{prefix}-{date_part}-{random_part}"


@tool
async def make_reservation(
    venue_name: str,
    venue_id: str = "",
    time_slot: str = "",
    party_size: int = 2,
    special_requests: str = "",
) -> dict:
    """Make a reservation at a venue (MOCK).

    Simulates booking confirmation. Interface matches future real API contract.

    Args:
        venue_name: Name of the venue to book.
        venue_id: Optional venue ID.
        time_slot: Desired time, e.g. "14:00".
        party_size: Number of people.
        special_requests: Any special requirements (e.g. "靠窗位置", "儿童座椅").

    Returns:
        Dict with status and reservation confirmation details.
    """
    try:
        # Simulate 95% success rate
        success = random.random() < 0.95

        if not success:
            return {
                "status": "error",
                "message": f"{venue_name} 该时段已满，建议更换时间或场所",
                "fallback": "suggest_alternatives",
            }

        confirmation = {
            "confirmation_code": _generate_confirmation_code(),
            "venue_name": venue_name,
            "venue_id": venue_id,
            "time_slot": time_slot,
            "party_size": party_size,
            "special_requests": special_requests,
            "status": "confirmed",
            "message": f"已成功预订 {venue_name}，{time_slot}，{party_size}人",
            "notes": "请提前10分钟到达，超时15分钟将自动取消",
        }

        logger.info(
            "reservation_mock_success",
            venue=venue_name,
            code=confirmation["confirmation_code"],
        )
        return {"status": "success", "data": confirmation}

    except Exception as e:
        logger.error("reservation_mock_error", error=str(e))
        return {"status": "error", "message": f"Reservation failed: {str(e)}"}
