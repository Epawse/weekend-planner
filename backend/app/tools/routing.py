"""Route calculation tool using AMap (高德) Direction API."""

import httpx
import structlog
from langchain_core.tools import tool

from app.config import settings

logger = structlog.get_logger()

AMAP_DRIVING_URL = "https://restapi.amap.com/v3/direction/driving"
AMAP_WALKING_URL = "https://restapi.amap.com/v3/direction/walking"


@tool
async def calculate_route(
    origin: str,
    destination: str,
    mode: str = "driving",
) -> dict:
    """Calculate route between two points using AMap Direction API.

    Args:
        origin: Start point as "lng,lat" string, e.g. "116.481,39.998"
        destination: End point as "lng,lat" string, e.g. "116.454,39.937"
        mode: Travel mode, either "driving" or "walking"

    Returns:
        Dict with status and route data including distance, duration, and polyline.
    """
    try:
        url = AMAP_DRIVING_URL if mode == "driving" else AMAP_WALKING_URL
        params = {
            "key": settings.amap_api_key,
            "origin": origin,
            "destination": destination,
            "extensions": "base",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        if data.get("status") != "1":
            logger.warning("amap_route_failed", info=data.get("info"))
            return {"status": "error", "message": f"AMap API error: {data.get('info')}"}

        route = data.get("route", {})
        paths = route.get("paths", [])

        if not paths:
            return {"status": "error", "message": "No route found"}

        # Use the first (optimal) path
        path = paths[0]
        distance_meters = int(path.get("distance", 0))
        duration_seconds = int(path.get("duration", 0))

        # Extract polyline coordinates from steps
        polyline_points: list[list[float]] = []
        for step in path.get("steps", []):
            polyline_str = step.get("polyline", "")
            for point in polyline_str.split(";"):
                if "," in point:
                    lng, lat = point.split(",")
                    polyline_points.append([float(lng), float(lat)])

        route_data = {
            "distance_meters": distance_meters,
            "distance_km": round(distance_meters / 1000, 1),
            "duration_seconds": duration_seconds,
            "duration_minutes": round(duration_seconds / 60),
            "mode": mode,
            "polyline": polyline_points,
            "summary": f"{mode}约{round(duration_seconds / 60)}分钟，{round(distance_meters / 1000, 1)}公里",
        }

        logger.info(
            "amap_route_success",
            mode=mode,
            distance_km=route_data["distance_km"],
            duration_min=route_data["duration_minutes"],
        )
        return {"status": "success", "data": route_data}

    except httpx.HTTPError as e:
        logger.error("amap_route_http_error", error=str(e))
        return {"status": "error", "message": f"HTTP error: {str(e)}"}
    except Exception as e:
        logger.error("amap_route_unexpected_error", error=str(e))
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}
