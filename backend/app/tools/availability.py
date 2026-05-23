"""Mock availability check tool — simulates queue/seat availability."""

import random

import structlog
from langchain_core.tools import tool

logger = structlog.get_logger()


@tool
async def check_availability(venue_name: str, venue_id: str = "", party_size: int = 2) -> dict:
    """Check queue and seat availability for a venue (MOCK).

    Simulates real-time availability data. Interface matches future real API contract.

    Args:
        venue_name: Name of the venue to check.
        venue_id: Optional venue ID for lookup.
        party_size: Number of people in the party.

    Returns:
        Dict with status and availability data including wait time and available slots.
    """
    try:
        # Simulate different availability scenarios
        scenarios = [
            {"available": True, "wait_minutes": 0, "message": "有空位，可直接入座"},
            {"available": True, "wait_minutes": 10, "message": "稍等片刻，约10分钟"},
            {"available": True, "wait_minutes": 20, "message": "当前排队约20分钟"},
            {"available": True, "wait_minutes": 30, "message": "高峰期，预计等待30分钟"},
            {"available": False, "wait_minutes": 60, "message": "当前已满，建议预约或换一家"},
        ]

        # Weighted random — most venues are available
        weights = [0.3, 0.25, 0.2, 0.15, 0.1]
        scenario = random.choices(scenarios, weights=weights, k=1)[0]

        availability_data = {
            "venue_name": venue_name,
            "venue_id": venue_id,
            "party_size": party_size,
            "available": scenario["available"],
            "wait_minutes": scenario["wait_minutes"],
            "message": scenario["message"],
            "checked_at": "just_now",
        }

        logger.info(
            "availability_check_mock",
            venue=venue_name,
            available=scenario["available"],
            wait=scenario["wait_minutes"],
        )
        return {"status": "success", "data": availability_data}

    except Exception as e:
        logger.error("availability_check_error", error=str(e))
        return {"status": "error", "message": f"Availability check failed: {str(e)}"}
