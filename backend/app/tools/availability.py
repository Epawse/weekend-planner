"""Mock availability tools — simulate queue, seat, family, and friends availability."""

import hashlib
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


def _stable_bucket(value: str, modulo: int) -> int:
    """Return a deterministic small integer for mock API repeatability."""
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % modulo


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


@tool
async def check_family_availability(
    venue_name: str,
    activity_type: str,
    party_size: int = 3,
    child_age: int = 5,
    diet_goal: str = "",
) -> dict:
    """Check family-specific availability for a venue (MOCK).

    This simulates a future business API contract for demo scope. It returns
    queue estimates, reservation/ticket availability, child-seat availability,
    and low-fat/light-meal support where relevant.
    """
    try:
        normalized = f"{venue_name} {activity_type} {diet_goal}".lower()
        queue_seed = _stable_bucket(normalized, 6)

        busy_keywords = ["网红", "火锅", "烧烤", "热门", "排队"]
        diet_keywords = ["轻食", "沙拉", "健康", "低卡", "低脂", "素食", "简餐"]
        family_keywords = ["亲子", "家庭", "儿童", "商场", "中心", "馆"]

        is_busy = _contains_any(normalized, busy_keywords)
        is_diet_friendly = _contains_any(normalized, diet_keywords)
        is_family_place = _contains_any(normalized, family_keywords)

        if activity_type == "eat":
            queue_minutes = 6 + queue_seed * 3
            if is_busy:
                queue_minutes += 24
            table_available = queue_minutes <= 25
            child_seat_available = is_family_place or queue_seed != 5
            low_fat_options = is_diet_friendly or not is_busy
            reservation_required = queue_minutes > 10
            data = {
                "venue_name": venue_name,
                "activity_type": activity_type,
                "party_size": party_size,
                "child_age": child_age,
                "available": table_available,
                "table_available": table_available,
                "queue_minutes": queue_minutes,
                "child_seat_available": child_seat_available,
                "low_fat_options": low_fat_options,
                "can_note_less_oil": True,
                "reservation_required": reservation_required,
                "time_slot": "17:00",
                "source": "mock_business_api",
                "message": (
                    f"17:00 {'有位' if table_available else '暂满'}，"
                    f"预计排队{queue_minutes}分钟，"
                    f"{'可备注儿童椅' if child_seat_available else '儿童椅需到店确认'}"
                ),
            }
        else:
            queue_minutes = 5 + queue_seed * 2
            if is_busy:
                queue_minutes += 18
            tickets_available = queue_minutes <= 25
            data = {
                "venue_name": venue_name,
                "activity_type": activity_type,
                "party_size": party_size,
                "child_age": child_age,
                "available": tickets_available,
                "tickets_available": tickets_available,
                "queue_minutes": queue_minutes,
                "reservation_required": True,
                "age_supported": child_age <= 8 or "儿童" in normalized or "亲子" in normalized,
                "source": "mock_business_api",
                "message": (
                    f"亲子活动{'余票充足' if tickets_available else '余票紧张'}，"
                    f"预计排队{queue_minutes}分钟"
                ),
            }

        logger.info(
            "family_availability_mock",
            venue=venue_name,
            activity_type=activity_type,
            queue=data["queue_minutes"],
            available=data["available"],
        )
        return {"status": "success", "data": data}
    except Exception as e:
        logger.error("family_availability_error", venue=venue_name, error=str(e))
        return {"status": "error", "message": f"Family availability check failed: {str(e)}"}


@tool
async def check_friends_availability(
    venue_name: str,
    activity_type: str,
    party_size: int = 4,
    preferences: list[str] | None = None,
) -> dict:
    """Check friends-specific availability for a venue (MOCK).

    This simulates future business APIs for group dining and social activities:
    table availability, queue pressure, chat ambience, group suitability, and
    after-dinner extension support.
    """
    try:
        del preferences
        normalized = f"{venue_name} {activity_type}".lower()
        queue_seed = _stable_bucket(normalized, 6)

        busy_keywords = ["网红", "热门", "排队", "火锅", "烧烤", "酒吧", "ktv"]
        chat_keywords = ["咖啡", "茶", "日料", "西餐", "小馆", "餐厅", "酒馆", "清吧", "书店"]
        social_keywords = ["剧本杀", "密室", "桌游", "ktv", "展览", "市集", "拍照", "艺术", "清吧"]
        photo_keywords = ["展览", "艺术", "美术", "市集", "景观", "网红", "夜景", "咖啡"]

        is_busy = _contains_any(normalized, busy_keywords)
        is_chat_friendly = _contains_any(normalized, chat_keywords) and "ktv" not in normalized
        is_social = _contains_any(normalized, social_keywords)
        is_photo = _contains_any(normalized, photo_keywords)

        if activity_type == "eat":
            queue_minutes = 8 + queue_seed * 4
            if is_busy:
                queue_minutes += 16
            table_for_4 = party_size <= 4 and queue_minutes <= 28
            data = {
                "venue_name": venue_name,
                "activity_type": activity_type,
                "party_size": party_size,
                "available": table_for_4,
                "table_for_4": table_for_4,
                "queue_minutes": queue_minutes,
                "chat_friendly": is_chat_friendly or not is_busy,
                "ambience_score": max(55, 88 - queue_minutes),
                "food_variety": "high" if "火锅" in normalized or "烧烤" in normalized else "medium",
                "reservation_required": queue_minutes > 12,
                "time_slot": "18:00",
                "source": "mock_business_api",
                "message": (
                    f"18:00 {'可订4人桌' if table_for_4 else '4人桌紧张'}，"
                    f"预计排队{queue_minutes}分钟，"
                    f"{'适合聊天' if is_chat_friendly or not is_busy else '聊天氛围一般'}"
                ),
            }
        elif activity_type == "extra":
            queue_minutes = 5 + queue_seed * 3
            if is_busy:
                queue_minutes += 12
            data = {
                "venue_name": venue_name,
                "activity_type": activity_type,
                "party_size": party_size,
                "available": queue_minutes <= 28,
                "queue_minutes": queue_minutes,
                "after_dinner_friendly": True,
                "can_continue_chat": is_chat_friendly or "清吧" in normalized or "咖啡" in normalized,
                "optional_extension": True,
                "reservation_required": queue_minutes > 15,
                "source": "mock_business_api",
                "message": f"饭后可续摊，预计排队{queue_minutes}分钟，可根据状态跳过",
            }
        else:
            queue_minutes = 6 + queue_seed * 3
            if is_busy:
                queue_minutes += 14
            data = {
                "venue_name": venue_name,
                "activity_type": activity_type,
                "party_size": party_size,
                "available": queue_minutes <= 28,
                "queue_minutes": queue_minutes,
                "group_suitable": is_social or is_photo or party_size <= 4,
                "photo_friendly": is_photo,
                "social_friendly": is_social,
                "reservation_required": queue_minutes > 12,
                "source": "mock_business_api",
                "message": (
                    f"适合{party_size}人体验，预计排队{queue_minutes}分钟，"
                    f"{'适合拍照' if is_photo else '互动体验为主' if is_social else '轻松活动'}"
                ),
            }

        logger.info(
            "friends_availability_mock",
            venue=venue_name,
            activity_type=activity_type,
            queue=data["queue_minutes"],
            available=data["available"],
        )
        return {"status": "success", "data": data}
    except Exception as e:
        logger.error("friends_availability_error", venue=venue_name, error=str(e))
        return {"status": "error", "message": f"Friends availability check failed: {str(e)}"}
