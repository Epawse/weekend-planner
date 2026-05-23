"""Isochrone (reachable area) tool using OpenRouteService API."""

import httpx
import structlog
from langchain_core.tools import tool

from app.config import settings

logger = structlog.get_logger()

ORS_ISOCHRONE_URL = "https://api.openrouteservice.org/v2/isochrones/driving-car"


@tool
async def get_reachable_area(
    location: str,
    travel_minutes: int = 30,
    profile: str = "driving-car",
) -> dict:
    """Calculate the reachable area (isochrone) from a location within given travel time.

    Uses OpenRouteService to compute the actual road-network-based reachable polygon,
    which is more accurate than a simple radius circle.

    Args:
        location: Center point as "lng,lat" string, e.g. "116.481,39.998"
        travel_minutes: Maximum travel time in minutes (default 30)
        profile: Travel profile - "driving-car", "foot-walking", or "cycling-regular"

    Returns:
        Dict with status and GeoJSON polygon representing the reachable area.
    """
    try:
        lng, lat = location.split(",")
        url = f"https://api.openrouteservice.org/v2/isochrones/{profile}"

        headers = {
            "Authorization": settings.ors_api_key,
            "Content-Type": "application/json",
        }

        body = {
            "locations": [[float(lng), float(lat)]],
            "range": [travel_minutes * 60],  # Convert to seconds
            "range_type": "time",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=body, headers=headers)
            response.raise_for_status()
            data = response.json()

        if not data.get("features"):
            return {"status": "error", "message": "No isochrone features returned"}

        # Extract the polygon geometry
        feature = data["features"][0]
        geometry = feature.get("geometry", {})

        isochrone_data = {
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "center": [float(lng), float(lat)],
                "travel_minutes": travel_minutes,
                "profile": profile,
                "area_km2": round(feature.get("properties", {}).get("area", 0) / 1_000_000, 2),
            },
        }

        logger.info(
            "ors_isochrone_success",
            travel_minutes=travel_minutes,
            profile=profile,
            area_km2=isochrone_data["properties"]["area_km2"],
        )
        return {"status": "success", "data": isochrone_data}

    except httpx.HTTPError as e:
        logger.error("ors_isochrone_http_error", error=str(e))
        return {"status": "error", "message": f"HTTP error: {str(e)}"}
    except Exception as e:
        logger.error("ors_isochrone_unexpected_error", error=str(e))
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}
