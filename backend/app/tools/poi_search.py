"""POI search tool using 高德 (AMap) API."""

import httpx
import structlog
from langchain_core.tools import tool

from app.config import settings

logger = structlog.get_logger()

AMAP_POI_URL = "https://restapi.amap.com/v3/place/around"
AMAP_TEXT_URL = "https://restapi.amap.com/v3/place/text"


@tool
async def search_venues(query: str, location: str, radius: int = 5000, types: str = "") -> dict:
    """Search for restaurants, attractions, or activities near a location using AMap POI API.

    Args:
        query: Search keyword, e.g. "亲子乐园", "火锅", "公园"
        location: Center point as "lng,lat" string, e.g. "116.481,39.998"
        radius: Search radius in meters (default 5000)
        types: Optional AMap POI type codes, e.g. "050000" for restaurants

    Returns:
        Dict with status and list of venue results.
    """
    try:
        params = {
            "key": settings.amap_api_key,
            "keywords": query,
            "location": location,
            "radius": radius,
            "offset": 10,
            "extensions": "all",
        }
        if types:
            params["types"] = types

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(AMAP_POI_URL, params=params)
            response.raise_for_status()
            data = response.json()

        if data.get("status") != "1":
            logger.warning("amap_poi_search_failed", info=data.get("info"))
            return {"status": "error", "message": f"AMap API error: {data.get('info')}"}

        pois = []
        for poi in data.get("pois", []):
            lng, lat = poi.get("location", "0,0").split(",")
            pois.append(
                {
                    "id": poi.get("id", ""),
                    "name": poi.get("name", ""),
                    "address": poi.get("address", ""),
                    "coords": [float(lng), float(lat)],
                    "category": poi.get("type", ""),
                    "rating": float(poi["biz_ext"].get("rating", 0)) if poi.get("biz_ext") else None,
                    "distance": int(poi.get("distance", 0)),
                    "tel": poi.get("tel", ""),
                    "business_area": poi.get("business_area", ""),
                }
            )

        logger.info("amap_poi_search_success", query=query, count=len(pois))
        return {"status": "success", "data": pois, "count": len(pois)}

    except httpx.HTTPError as e:
        logger.error("amap_poi_search_http_error", error=str(e))
        return {"status": "error", "message": f"HTTP error: {str(e)}"}
    except Exception as e:
        logger.error("amap_poi_search_unexpected_error", error=str(e))
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}
