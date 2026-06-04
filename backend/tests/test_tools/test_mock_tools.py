"""Tests for the mock execution tools (availability, booking, delivery).

These tools are deterministic in structure (the random parts only pick among a
fixed set of shapes), so we assert on the contract: return envelope, required
fields, and confirmation/order-id formats. Tools are @tool-decorated, so they are
invoked the same way the orchestrator calls them: ``tool.ainvoke({...})``.
"""

import re

from app.tools.availability import check_availability
from app.tools.booking import _generate_confirmation_code, make_reservation
from app.tools.delivery import _estimate_price, _generate_order_id, order_delivery

CONFIRMATION_CODE_RE = re.compile(r"^BK-\d{8}-\d{3}$")
ORDER_ID_RE = re.compile(r"^DL-\d{8}-\d{4}$")


async def test_check_availability_returns_success_envelope() -> None:
    result = await check_availability.ainvoke({"venue_name": "绿茶餐厅", "party_size": 4})

    assert result["status"] == "success"
    data = result["data"]
    assert data["venue_name"] == "绿茶餐厅"
    assert data["party_size"] == 4
    assert isinstance(data["available"], bool)
    assert isinstance(data["wait_minutes"], int)
    assert data["wait_minutes"] >= 0
    assert isinstance(data["message"], str) and data["message"]
    assert data["checked_at"] == "just_now"


async def test_check_availability_passes_through_venue_id() -> None:
    result = await check_availability.ainvoke(
        {"venue_name": "蓝色港湾", "venue_id": "B0FF123", "party_size": 2}
    )

    assert result["status"] == "success"
    assert result["data"]["venue_id"] == "B0FF123"


async def test_make_reservation_success_or_full_fallback() -> None:
    # 95% success path; the failure path is a structured error, not an exception.
    # Either way the envelope must be well-formed.
    result = await make_reservation.ainvoke(
        {
            "venue_name": "绿茶餐厅",
            "time_slot": "14:00",
            "party_size": 2,
            "special_requests": "靠窗位置",
        }
    )

    assert result["status"] in {"success", "error"}
    if result["status"] == "success":
        data = result["data"]
        assert CONFIRMATION_CODE_RE.match(data["confirmation_code"])
        assert data["venue_name"] == "绿茶餐厅"
        assert data["time_slot"] == "14:00"
        assert data["party_size"] == 2
        assert data["special_requests"] == "靠窗位置"
        assert data["status"] == "confirmed"
        assert data["message"]
        assert data["notes"]
    else:
        assert result["fallback"] == "suggest_alternatives"
        assert "已满" in result["message"]


async def test_make_reservation_confirmation_code_format_is_stable() -> None:
    # Drive enough iterations that we exercise the success path at least once
    # (~95% per call) and assert every confirmation code matches the contract.
    seen_success = False
    for _ in range(50):
        result = await make_reservation.ainvoke({"venue_name": "测试餐厅", "time_slot": "12:30"})
        if result["status"] == "success":
            seen_success = True
            assert CONFIRMATION_CODE_RE.match(result["data"]["confirmation_code"])
    assert seen_success, "expected at least one successful reservation in 50 attempts"


async def test_order_delivery_returns_success_envelope() -> None:
    result = await order_delivery.ainvoke(
        {
            "item_type": "flowers",
            "item_description": "红玫瑰花束",
            "delivery_address": "望京SOHO",
            "delivery_time": "15:00",
            "recipient": "老婆",
            "message_card": "节日快乐",
        }
    )

    assert result["status"] == "success"
    data = result["data"]
    assert ORDER_ID_RE.match(data["order_id"])
    assert data["item_type"] == "flowers"
    assert data["item_description"] == "红玫瑰花束"
    assert data["delivery_address"] == "望京SOHO"
    assert data["recipient"] == "老婆"
    assert data["message_card"] == "节日快乐"
    assert data["status"] == "accepted"
    assert 30 <= data["eta_minutes"] <= 60
    assert data["price_yuan"] > 0


async def test_order_delivery_defaults_item_description() -> None:
    result = await order_delivery.ainvoke({"item_type": "cake"})

    assert result["status"] == "success"
    assert result["data"]["item_description"] == "精选cake"


def test_generate_confirmation_code_format() -> None:
    code = _generate_confirmation_code()
    assert CONFIRMATION_CODE_RE.match(code)


def test_generate_order_id_format() -> None:
    order_id = _generate_order_id()
    assert ORDER_ID_RE.match(order_id)


def test_estimate_price_within_known_ranges() -> None:
    ranges = {
        "flowers": (99.0, 299.0),
        "cake": (128.0, 268.0),
        "gift": (59.0, 199.0),
    }
    for item_type, (low, high) in ranges.items():
        price = _estimate_price(item_type)
        assert low <= price <= high


def test_estimate_price_unknown_type_uses_default_range() -> None:
    price = _estimate_price("balloon")
    assert 50.0 <= price <= 200.0
