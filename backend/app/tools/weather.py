"""Weather tool using QWeather (和风天气) API."""

import httpx
import structlog
from langchain_core.tools import tool

from app.config import settings

logger = structlog.get_logger()

def _get_qweather_url(path: str) -> str:
    return f"https://{settings.qweather_api_host}{path}"


@tool
async def get_weather(location: str) -> dict:
    """Get current weather for a location using QWeather API.

    Args:
        location: Location as "lng,lat" string (GCJ-02), e.g. "116.48,40.00"

    Returns:
        Dict with status and weather data including temperature, condition, wind.
    """
    try:
        # QWeather requires max 2 decimal places for coordinates
        parts = location.split(",")
        lng = f"{float(parts[0]):.2f}"
        lat = f"{float(parts[1]):.2f}"
        formatted_location = f"{lng},{lat}"

        headers = {
            "X-QW-Api-Key": settings.qweather_api_key,
        }
        params = {
            "location": formatted_location,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(_get_qweather_url("/v7/weather/now"), params=params, headers=headers)
            response.raise_for_status()
            data = response.json()

        if data.get("code") != "200":
            logger.warning("qweather_api_failed", code=data.get("code"))
            return {"status": "error", "message": f"QWeather API error: code {data.get('code')}"}

        now = data.get("now", {})
        weather_data = {
            "temperature": int(now.get("temp", 0)),
            "feels_like": int(now.get("feelsLike", 0)),
            "condition": now.get("text", "未知"),
            "wind_direction": now.get("windDir", ""),
            "wind_scale": now.get("windScale", ""),
            "humidity": int(now.get("humidity", 0)),
            "icon": now.get("icon", ""),
            "summary": f"{now.get('text', '未知')}，气温{now.get('temp', '?')}°C，体感{now.get('feelsLike', '?')}°C",
        }

        logger.info("qweather_success", condition=weather_data["condition"], temp=weather_data["temperature"])
        return {"status": "success", "data": weather_data}

    except httpx.HTTPError as e:
        logger.error("qweather_http_error", error=str(e))
        return {"status": "error", "message": f"HTTP error: {str(e)}"}
    except Exception as e:
        logger.error("qweather_unexpected_error", error=str(e))
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}
