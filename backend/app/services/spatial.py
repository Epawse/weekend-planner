"""Deterministic spatial analysis engine.

Performs all geospatial computation before LLM involvement.
The LLM never sees raw spatial data — only pre-validated candidate plans.

Pipeline:
  1. Compute isochrone (reachable area)
  2. Search POIs (AMap API)
  3. Spatial filter (point-in-polygon using shapely)
  4. Cluster venues into walkable groups
  5. Optimize visit order per cluster (TSP brute-force)
  6. Validate time budget
  7. Output 2-3 candidate plans that are mathematically feasible
"""

import math
from itertools import permutations

import structlog
from shapely.geometry import Point, Polygon, shape

from app.tools.isochrone import get_reachable_area
from app.tools.poi_search import search_venues
from app.tools.routing import calculate_route
from app.tools.weather import get_weather

logger = structlog.get_logger()

# Search queries by scenario
SCENARIO_QUERIES: dict[str, list[dict[str, str]]] = {
    "family": [
        {"query": "亲子乐园", "type": "play"},
        {"query": "儿童游乐", "type": "play"},
        {"query": "公园", "type": "play"},
        {"query": "亲子餐厅", "type": "eat"},
        {"query": "家庭餐厅", "type": "eat"},
        {"query": "甜品店", "type": "extra"},
    ],
    "friends": [
        {"query": "密室逃脱", "type": "play"},
        {"query": "剧本杀", "type": "play"},
        {"query": "展览", "type": "play"},
        {"query": "火锅", "type": "eat"},
        {"query": "烧烤", "type": "eat"},
        {"query": "酒吧", "type": "extra"},
        {"query": "甜品店", "type": "extra"},
    ],
}

# Fallback queries when primary eat search returns no results
EAT_FALLBACK_QUERIES: list[str] = ["餐厅", "美食"]

# Default activity durations (minutes)
DEFAULT_DURATIONS: dict[str, int] = {
    "play": 90,
    "eat": 75,
    "extra": 45,
}


def _haversine_distance(coord1: list[float], coord2: list[float]) -> float:
    """Calculate haversine distance between two [lng, lat] points in meters."""
    lng1, lat1 = math.radians(coord1[0]), math.radians(coord1[1])
    lng2, lat2 = math.radians(coord2[0]), math.radians(coord2[1])

    dlat = lat2 - lat1
    dlng = lng2 - lng1

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))

    # Earth radius in meters
    return 6371000 * c


def _build_fallback_isochrone(center: list[float], radius_km: float = 5.0) -> dict:
    """Build a circular polygon as fallback when ORS is unavailable.

    Creates a 32-point circle approximation around the center point.
    """
    lng, lat = center
    points = []
    num_points = 32
    # Approximate degrees per km at this latitude
    lat_per_km = 1 / 111.0
    lng_per_km = 1 / (111.0 * math.cos(math.radians(lat)))

    for i in range(num_points):
        angle = 2 * math.pi * i / num_points
        dx = radius_km * math.cos(angle) * lng_per_km
        dy = radius_km * math.sin(angle) * lat_per_km
        points.append([lng + dx, lat + dy])

    # Close the ring
    points.append(points[0])

    return {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [points],
        },
        "properties": {
            "center": center,
            "travel_minutes": 30,
            "profile": "driving-car",
            "fallback": True,
        },
    }


def _filter_venues_in_polygon(venues: list[dict], polygon: Polygon) -> list[dict]:
    """Filter venues that are within the isochrone polygon using shapely."""
    filtered = []
    for venue in venues:
        coords = venue.get("coords", [0, 0])
        point = Point(coords[0], coords[1])
        if polygon.contains(point):
            filtered.append(venue)
    return filtered


def _deduplicate_venues(venues: list[dict]) -> list[dict]:
    """Remove duplicate venues by ID or name+address."""
    seen: set[str] = set()
    unique = []
    for v in venues:
        key = v.get("id") or f"{v.get('name', '')}_{v.get('address', '')}"
        if key not in seen:
            seen.add(key)
            unique.append(v)
    return unique


def _find_walkable_clusters(
    play_venues: list[dict],
    eat_venues: list[dict],
    extra_venues: list[dict],
    home_coords: list[float],
    max_walk_distance: float = 1500.0,
    max_clusters: int = 3,
) -> list[dict]:
    """Group venues into walkable clusters anchored by play venues.

    Strategy:
      - Pick a "play" venue as anchor
      - Find "eat" venues within max_walk_distance of anchor
      - Find "extra" venues within max_walk_distance of anchor or eat venue
      - This forms a "walkable cluster"
    """
    clusters = []

    # Sort play venues by distance from home (prefer closer ones)
    play_sorted = sorted(play_venues, key=lambda v: _haversine_distance(home_coords, v["coords"]))

    used_play_ids: set[str] = set()

    for play_venue in play_sorted:
        if len(clusters) >= max_clusters:
            break

        play_id = play_venue.get("id") or play_venue.get("name", "")
        if play_id in used_play_ids:
            continue
        used_play_ids.add(play_id)

        anchor_coords = play_venue["coords"]

        # Find nearby eat venues
        nearby_eat = [v for v in eat_venues if _haversine_distance(anchor_coords, v["coords"]) <= max_walk_distance]

        if not nearby_eat:
            # No restaurant nearby — skip this anchor
            continue

        # Pick best eat venue (by rating, then distance)
        nearby_eat.sort(key=lambda v: (-1 * (v.get("rating") or 0), _haversine_distance(anchor_coords, v["coords"])))
        best_eat = nearby_eat[0]

        # Find nearby extra venues (within walk distance of either play or eat)
        nearby_extra = []
        for v in extra_venues:
            dist_to_play = _haversine_distance(anchor_coords, v["coords"])
            dist_to_eat = _haversine_distance(best_eat["coords"], v["coords"])
            if min(dist_to_play, dist_to_eat) <= max_walk_distance:
                nearby_extra.append(v)

        # Pick best extra (optional)
        best_extra = None
        if nearby_extra:
            nearby_extra.sort(
                key=lambda v: (-1 * (v.get("rating") or 0), _haversine_distance(anchor_coords, v["coords"]))
            )
            best_extra = nearby_extra[0]

        cluster = {
            "anchor": play_venue,
            "eat": best_eat,
            "extra": best_extra,
            "venues": [play_venue, best_eat] + ([best_extra] if best_extra else []),
        }
        clusters.append(cluster)

    return clusters


def _build_fallback_clusters(
    play_venues: list[dict],
    eat_venues: list[dict],
    extra_venues: list[dict],
    home_coords: list[float],
    max_clusters: int = 3,
) -> list[dict]:
    """Build clusters when normal clustering fails (e.g. no eat venues due to rate limiting).

    Strategy:
      - If eat venues exist but weren't close enough, pair closest play+eat regardless of distance
      - If no eat venues at all, create play+extra clusters
      - Last resort: play-only clusters
    """
    clusters = []
    play_sorted = sorted(play_venues, key=lambda v: _haversine_distance(home_coords, v["coords"]))

    for play_venue in play_sorted[:max_clusters]:
        anchor_coords = play_venue["coords"]

        # Try to find any eat venue (ignore distance constraint)
        best_eat = None
        if eat_venues:
            eat_by_dist = sorted(eat_venues, key=lambda v: _haversine_distance(anchor_coords, v["coords"]))
            best_eat = eat_by_dist[0]

        # Try to find an extra venue nearby
        best_extra = None
        if extra_venues:
            extra_by_dist = sorted(extra_venues, key=lambda v: _haversine_distance(anchor_coords, v["coords"]))
            best_extra = extra_by_dist[0]

        # Build cluster with whatever we have
        venues_list = [play_venue]
        if best_eat:
            venues_list.append(best_eat)
        elif best_extra:
            # Promote extra to eat role if no eat venues available
            venues_list.append(best_extra)
            best_eat = best_extra
            best_extra = None

        if not best_eat:
            # Play-only cluster (minimum viable)
            best_eat = play_venue  # Use play venue as placeholder for label generation

        cluster = {
            "anchor": play_venue,
            "eat": best_eat,
            "extra": best_extra,
            "venues": venues_list + ([best_extra] if best_extra and best_extra not in venues_list else []),
        }
        clusters.append(cluster)

    return clusters


def _tsp_brute_force(venues: list[dict], home_coords: list[float]) -> list[dict]:
    """Find optimal visit order for venues using brute-force TSP.

    For 2-4 venues, brute-force is fast (max 24 permutations).
    Uses haversine distance as cost metric.
    """
    if len(venues) <= 1:
        return venues

    # For 2+ venues, try all permutations starting from home
    best_order: list[dict] | None = None
    best_distance = float("inf")

    for perm in permutations(venues):
        total_distance = _haversine_distance(home_coords, perm[0]["coords"])
        for i in range(len(perm) - 1):
            total_distance += _haversine_distance(perm[i]["coords"], perm[i + 1]["coords"])
        if total_distance < best_distance:
            best_distance = total_distance
            best_order = list(perm)

    return best_order or venues


def _estimate_travel_minutes(coord1: list[float], coord2: list[float], mode: str = "driving") -> int:
    """Estimate travel time between two points without API call.

    Uses haversine distance with average speed assumptions:
      - driving: 25 km/h (urban Beijing average with traffic)
      - walking: 5 km/h
    """
    distance_m = _haversine_distance(coord1, coord2)
    if mode == "walking":
        speed_mps = 5000 / 3600  # 5 km/h in m/s
    else:
        speed_mps = 25000 / 3600  # 25 km/h in m/s

    minutes = (distance_m / speed_mps) / 60
    return max(1, round(minutes))


def _build_candidate_plan(
    cluster: dict,
    home_coords: list[float],
    start_time_hour: int = 14,
    start_time_minute: int = 0,
) -> dict:
    """Build a candidate plan from a cluster with time validation.

    Returns a structured plan dict with activities, durations, and travel times.
    """
    ordered_venues = _tsp_brute_force(cluster["venues"], home_coords)

    activities = []
    current_minutes = start_time_hour * 60 + start_time_minute
    total_travel = 0
    prev_coords = home_coords

    for i, venue in enumerate(ordered_venues):
        # Determine activity type
        if venue == cluster["anchor"]:
            activity_type = "play"
        elif venue == cluster["eat"]:
            activity_type = "eat"
        else:
            activity_type = "extra"

        # Travel time from previous point
        travel_min = _estimate_travel_minutes(prev_coords, venue["coords"])
        total_travel += travel_min
        current_minutes += travel_min

        # Format start time
        hour = current_minutes // 60
        minute = current_minutes % 60
        start_time = f"{hour:02d}:{minute:02d}"

        duration = DEFAULT_DURATIONS[activity_type]

        # Determine action type
        if activity_type == "eat":
            action = "reserve"
        elif activity_type == "play":
            action = "book"
        else:
            action = "no_action"

        activities.append(
            {
                "order": i + 1,
                "type": activity_type,
                "venue_name": venue.get("name", ""),
                "venue_address": venue.get("address", ""),
                "venue_coords": venue["coords"],
                "start_time": start_time,
                "duration_minutes": duration,
                "travel_from_prev_minutes": travel_min,
                "action": action,
                "action_details": {},
                "category": venue.get("category", ""),
                "rating": venue.get("rating"),
                "distance_from_home": round(_haversine_distance(home_coords, venue["coords"])),
            }
        )

        current_minutes += duration
        prev_coords = venue["coords"]

    # Calculate total duration
    total_duration_minutes = current_minutes - (start_time_hour * 60 + start_time_minute)

    # Walkability score: fraction of inter-venue distances that are < 800m (walkable)
    walkable_segments = 0
    total_segments = 0
    prev = home_coords
    for venue in ordered_venues:
        dist = _haversine_distance(prev, venue["coords"])
        total_segments += 1
        if dist < 800:
            walkable_segments += 1
        prev = venue["coords"]

    walkability_score = walkable_segments / max(total_segments, 1)

    # Build route GeoJSON (LineString connecting all points in order)
    route_coords = [home_coords] + [v["coords"] for v in ordered_venues]
    route_geojson = {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": route_coords,
        },
        "properties": {
            "total_travel_minutes": total_travel,
        },
    }

    # Generate label
    play_name = cluster["anchor"].get("name", "活动")
    eat_name = cluster["eat"].get("name", "餐厅")
    area = cluster["anchor"].get("business_area") or cluster["eat"].get("business_area") or ""
    label = f"{area + ' | ' if area else ''}{play_name} + {eat_name}"

    # Spatial summary
    max_dist = max(_haversine_distance(ordered_venues[0]["coords"], v["coords"]) for v in ordered_venues)
    if max_dist < 500:
        spatial_summary = "所有活动在500米半径内，全程步行可达"
    elif max_dist < 1000:
        spatial_summary = "活动集中在1公里范围内，步行为主"
    elif max_dist < 2000:
        spatial_summary = "活动分布在2公里内，建议短途驾车"
    else:
        spatial_summary = f"活动分布较广（约{round(max_dist / 1000, 1)}公里），建议驾车前往"

    return {
        "label": label,
        "activities": activities,
        "total_duration_minutes": total_duration_minutes,
        "total_travel_minutes": total_travel,
        "walkability_score": round(walkability_score, 2),
        "spatial_summary": spatial_summary,
        "route_geojson": route_geojson,
    }


class SpatialAnalysisEngine:
    """Deterministic spatial reasoning engine.

    Performs all geospatial computation before LLM involvement.
    The LLM never sees raw spatial data -- only pre-validated candidate plans.
    """

    async def analyze(
        self,
        home_location: list[float],
        scenario: str,
        time_budget_hours: float = 4.5,
        travel_minutes: int = 30,
        profile: str = "driving-car",
    ) -> dict:
        """Run full spatial analysis pipeline.

        Args:
            home_location: [lng, lat] in GCJ-02 coordinate system.
            scenario: "family" or "friends".
            time_budget_hours: Maximum total time budget in hours.
            travel_minutes: Isochrone travel time limit.
            profile: Travel profile for isochrone.

        Returns:
            Dict with candidate plans, isochrone GeoJSON, and all venues.
        """
        location_str = f"{home_location[0]},{home_location[1]}"
        time_budget_minutes = int(time_budget_hours * 60)

        # Step 1: Compute isochrone
        logger.info("spatial_step_isochrone", location=location_str, travel_minutes=travel_minutes)
        isochrone_geojson = await self._get_isochrone(location_str, travel_minutes, profile)

        # Step 2: Get weather
        logger.info("spatial_step_weather", location=location_str)
        weather_data = await self._get_weather(location_str)

        # Step 3: Search POIs
        logger.info("spatial_step_poi_search", scenario=scenario)
        categorized_venues = await self._search_all_venues(location_str, scenario)

        # Step 4: Spatial filter (point-in-polygon)
        logger.info("spatial_step_filter")
        polygon = self._extract_polygon(isochrone_geojson)
        if polygon:
            for category in categorized_venues:
                categorized_venues[category] = _filter_venues_in_polygon(categorized_venues[category], polygon)

        # Deduplicate within each category
        for category in categorized_venues:
            categorized_venues[category] = _deduplicate_venues(categorized_venues[category])

        play_venues = categorized_venues.get("play", [])
        eat_venues = categorized_venues.get("eat", [])
        extra_venues = categorized_venues.get("extra", [])

        all_venues = play_venues + eat_venues + extra_venues

        logger.info(
            "spatial_filter_result",
            play=len(play_venues),
            eat=len(eat_venues),
            extra=len(extra_venues),
        )

        # Step 5: Cluster venues into walkable groups
        clusters = _find_walkable_clusters(
            play_venues=play_venues,
            eat_venues=eat_venues,
            extra_venues=extra_venues,
            home_coords=home_location,
            max_walk_distance=1500.0,
            max_clusters=3,
        )

        # If clustering found nothing, try with larger walk distance
        if not clusters:
            clusters = _find_walkable_clusters(
                play_venues=play_venues,
                eat_venues=eat_venues,
                extra_venues=extra_venues,
                home_coords=home_location,
                max_walk_distance=3000.0,
                max_clusters=3,
            )

        # Last resort: if still no clusters (e.g. no eat venues due to rate limiting),
        # create play-only or play+extra clusters
        if not clusters and play_venues:
            clusters = _build_fallback_clusters(
                play_venues=play_venues,
                eat_venues=eat_venues,
                extra_venues=extra_venues,
                home_coords=home_location,
                max_clusters=3,
            )

        logger.info("spatial_clusters_found", count=len(clusters))

        # Step 6: Build candidate plans with TSP optimization and time validation
        candidates = []
        for i, cluster in enumerate(clusters):
            plan = _build_candidate_plan(cluster, home_location)
            plan["id"] = f"plan_{chr(97 + i)}"  # plan_a, plan_b, plan_c

            # Time budget validation
            if plan["total_duration_minutes"] <= time_budget_minutes:
                candidates.append(plan)
            else:
                # Try removing extra activity to fit budget
                if len(plan["activities"]) > 2:
                    # Remove the extra activity
                    trimmed_cluster = {
                        "anchor": cluster["anchor"],
                        "eat": cluster["eat"],
                        "extra": None,
                        "venues": [cluster["anchor"], cluster["eat"]],
                    }
                    trimmed_plan = _build_candidate_plan(trimmed_cluster, home_location)
                    trimmed_plan["id"] = f"plan_{chr(97 + i)}"
                    if trimmed_plan["total_duration_minutes"] <= time_budget_minutes:
                        candidates.append(trimmed_plan)

        # Step 7: Try to get real route data for top candidate (optional enhancement)
        if candidates:
            top = candidates[0]
            route_data = await self._get_real_route(home_location, top["activities"])
            if route_data:
                top["route_geojson"] = route_data.get("route_geojson", top["route_geojson"])
                top["total_travel_minutes"] = route_data.get("total_travel_minutes", top["total_travel_minutes"])

        result = {
            "candidates": candidates,
            "isochrone_geojson": isochrone_geojson,
            "all_venues": all_venues,
            "weather": weather_data,
            "stats": {
                "total_venues_found": len(all_venues),
                "play_venues": len(play_venues),
                "eat_venues": len(eat_venues),
                "extra_venues": len(extra_venues),
                "clusters_formed": len(clusters),
                "valid_candidates": len(candidates),
            },
        }

        logger.info("spatial_analysis_complete", candidates=len(candidates), total_venues=len(all_venues))
        return result

    async def _get_isochrone(self, location_str: str, travel_minutes: int, profile: str) -> dict:
        """Get isochrone polygon, with fallback to radius circle."""
        try:
            result = await get_reachable_area.ainvoke(
                {"location": location_str, "travel_minutes": travel_minutes, "profile": profile}
            )
            if result.get("status") == "success":
                return result["data"]
        except Exception as e:
            logger.warning("isochrone_failed_using_fallback", error=str(e))

        # Fallback: 5km radius circle
        lng, lat = location_str.split(",")
        return _build_fallback_isochrone([float(lng), float(lat)], radius_km=5.0)

    async def _get_weather(self, location_str: str) -> dict | None:
        """Get weather data, returns None on failure."""
        try:
            result = await get_weather.ainvoke({"location": location_str})
            if result.get("status") == "success":
                return result["data"]
        except Exception as e:
            logger.warning("weather_fetch_failed", error=str(e))
        return None

    async def _search_all_venues(self, location_str: str, scenario: str) -> dict[str, list[dict]]:
        """Search all venue categories for the given scenario.

        Returns dict keyed by activity type: {"play": [...], "eat": [...], "extra": [...]}
        Includes fallback queries if primary eat search returns no results.
        """
        queries = SCENARIO_QUERIES.get(scenario, SCENARIO_QUERIES["family"])
        categorized: dict[str, list[dict]] = {"play": [], "eat": [], "extra": []}

        for query_info in queries:
            try:
                result = await search_venues.ainvoke(
                    {"query": query_info["query"], "location": location_str, "radius": 5000}
                )
                if result.get("status") == "success":
                    venues = result.get("data", [])
                    categorized[query_info["type"]].extend(venues)
            except Exception as e:
                logger.warning("poi_search_failed", query=query_info["query"], error=str(e))
                continue

        # Fallback: if no eat venues found, try generic restaurant queries
        if not categorized["eat"]:
            logger.info("eat_venues_empty_trying_fallback")
            for fallback_query in EAT_FALLBACK_QUERIES:
                try:
                    result = await search_venues.ainvoke(
                        {"query": fallback_query, "location": location_str, "radius": 5000}
                    )
                    if result.get("status") == "success":
                        venues = result.get("data", [])
                        categorized["eat"].extend(venues)
                        if categorized["eat"]:
                            break  # Got results, stop trying fallbacks
                except Exception as e:
                    logger.warning("eat_fallback_search_failed", query=fallback_query, error=str(e))
                    continue

        return categorized

    def _extract_polygon(self, isochrone_geojson: dict) -> Polygon | None:
        """Extract shapely Polygon from isochrone GeoJSON feature."""
        try:
            geometry = isochrone_geojson.get("geometry")
            if not geometry:
                return None
            return shape(geometry)
        except Exception as e:
            logger.warning("polygon_extraction_failed", error=str(e))
            return None

    async def _get_real_route(self, home_coords: list[float], activities: list[dict]) -> dict | None:
        """Get real route data from AMap for the planned sequence.

        Only called for the top candidate to save API quota.
        """
        if not activities:
            return None

        try:
            all_coords = [home_coords] + [a["venue_coords"] for a in activities]
            total_travel = 0
            polyline_points: list[list[float]] = [home_coords]

            for i in range(len(all_coords) - 1):
                origin = f"{all_coords[i][0]},{all_coords[i][1]}"
                destination = f"{all_coords[i + 1][0]},{all_coords[i + 1][1]}"

                result = await calculate_route.ainvoke(
                    {"origin": origin, "destination": destination, "mode": "driving"}
                )
                if result.get("status") == "success":
                    data = result["data"]
                    total_travel += data.get("duration_minutes", 0)
                    polyline = data.get("polyline", [])
                    if polyline:
                        polyline_points.extend(polyline)
                    else:
                        polyline_points.append(all_coords[i + 1])
                else:
                    polyline_points.append(all_coords[i + 1])

            route_geojson = {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": polyline_points,
                },
                "properties": {
                    "total_travel_minutes": total_travel,
                    "source": "amap",
                },
            }

            return {
                "route_geojson": route_geojson,
                "total_travel_minutes": total_travel,
            }
        except Exception as e:
            logger.warning("real_route_fetch_failed", error=str(e))
            return None
