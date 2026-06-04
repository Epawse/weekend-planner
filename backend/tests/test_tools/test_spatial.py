"""Tests for the deterministic spatial-analysis helpers in app.services.spatial.

Only the pure, network-free helpers are covered here: haversine distance,
point-in-polygon filtering, deduplication, brute-force TSP ordering, travel-time
estimation, and candidate-plan construction. The async ``analyze`` pipeline
depends on external APIs and is intentionally out of scope.
"""

import math

from shapely.geometry import Polygon

from app.services.spatial import (
    _build_candidate_plan,
    _build_fallback_isochrone,
    _deduplicate_venues,
    _estimate_travel_minutes,
    _filter_venues_in_polygon,
    _haversine_distance,
    _tsp_brute_force,
)


def test_haversine_distance_zero_for_identical_points() -> None:
    assert _haversine_distance([116.481, 39.998], [116.481, 39.998]) == 0.0


def test_haversine_distance_matches_known_value() -> None:
    # Roughly 1 degree of latitude ~= 111 km near these coordinates.
    dist = _haversine_distance([116.0, 39.0], [116.0, 40.0])
    assert math.isclose(dist, 111_195, rel_tol=0.01)


def test_haversine_distance_is_symmetric() -> None:
    a = [116.481, 39.998]
    b = [116.454, 39.937]
    assert math.isclose(_haversine_distance(a, b), _haversine_distance(b, a), rel_tol=1e-9)


def test_build_fallback_isochrone_is_closed_ring_marked_fallback() -> None:
    center = [116.481, 39.998]
    iso = _build_fallback_isochrone(center, radius_km=5.0)

    assert iso["type"] == "Feature"
    assert iso["geometry"]["type"] == "Polygon"
    assert iso["properties"]["fallback"] is True

    ring = iso["geometry"]["coordinates"][0]
    # 32 points + closing point that repeats the first vertex.
    assert len(ring) == 33
    assert ring[0] == ring[-1]


def test_build_fallback_isochrone_contains_center() -> None:
    center = [116.481, 39.998]
    iso = _build_fallback_isochrone(center, radius_km=5.0)
    polygon = Polygon(iso["geometry"]["coordinates"][0])
    from shapely.geometry import Point

    assert polygon.contains(Point(center[0], center[1]))


def test_filter_venues_in_polygon_keeps_only_inside() -> None:
    # Unit square around the origin.
    square = Polygon([(0, 0), (0, 1), (1, 1), (1, 0), (0, 0)])
    venues = [
        {"name": "inside", "coords": [0.5, 0.5]},
        {"name": "outside", "coords": [2.0, 2.0]},
        {"name": "edge-out", "coords": [1.5, 0.5]},
    ]

    filtered = _filter_venues_in_polygon(venues, square)
    names = {v["name"] for v in filtered}
    assert names == {"inside"}


def test_filter_venues_in_polygon_handles_missing_coords() -> None:
    square = Polygon([(0, 0), (0, 1), (1, 1), (1, 0), (0, 0)])
    venues = [{"name": "no-coords"}]  # defaults to [0, 0], which is on the boundary

    # Should not raise; [0, 0] is a boundary point and contains() excludes the boundary.
    filtered = _filter_venues_in_polygon(venues, square)
    assert filtered == []


def test_deduplicate_venues_by_id() -> None:
    venues = [
        {"id": "A", "name": "first"},
        {"id": "A", "name": "duplicate-of-first"},
        {"id": "B", "name": "second"},
    ]
    unique = _deduplicate_venues(venues)
    assert [v["id"] for v in unique] == ["A", "B"]


def test_deduplicate_venues_by_name_address_when_no_id() -> None:
    venues = [
        {"name": "Cafe", "address": "Street 1"},
        {"name": "Cafe", "address": "Street 1"},
        {"name": "Cafe", "address": "Street 2"},
    ]
    unique = _deduplicate_venues(venues)
    assert len(unique) == 2


def test_tsp_brute_force_single_or_empty_returns_input() -> None:
    assert _tsp_brute_force([], [0, 0]) == []
    single = [{"name": "only", "coords": [1, 1]}]
    assert _tsp_brute_force(single, [0, 0]) == single


def test_tsp_brute_force_picks_known_optimal_order() -> None:
    # Home at origin. Venues laid out so the optimal visiting order is near -> far
    # along the +x axis: near (0.01) -> mid (0.02) -> far (0.03).
    home = [0.0, 0.0]
    near = {"name": "near", "coords": [0.01, 0.0]}
    mid = {"name": "mid", "coords": [0.02, 0.0]}
    far = {"name": "far", "coords": [0.03, 0.0]}

    # Feed them in a deliberately suboptimal order.
    ordered = _tsp_brute_force([far, near, mid], home)
    assert [v["name"] for v in ordered] == ["near", "mid", "far"]


def test_tsp_brute_force_returns_valid_permutation() -> None:
    home = [116.0, 39.0]
    venues = [
        {"name": "a", "coords": [116.01, 39.01]},
        {"name": "b", "coords": [116.02, 39.00]},
        {"name": "c", "coords": [116.00, 39.02]},
        {"name": "d", "coords": [116.03, 39.03]},
    ]
    ordered = _tsp_brute_force(venues, home)
    assert sorted(v["name"] for v in ordered) == ["a", "b", "c", "d"]
    assert len(ordered) == len(venues)


def test_estimate_travel_minutes_driving_vs_walking() -> None:
    a = [116.0, 39.0]
    b = [116.0, 39.05]  # ~5.5 km north

    driving = _estimate_travel_minutes(a, b, mode="driving")
    walking = _estimate_travel_minutes(a, b, mode="walking")

    # Walking (5 km/h) is much slower than driving (25 km/h).
    assert walking > driving
    assert driving >= 1


def test_estimate_travel_minutes_floor_is_one() -> None:
    a = [116.0, 39.0]
    assert _estimate_travel_minutes(a, a) == 1


def test_build_candidate_plan_structure_and_ordering() -> None:
    home = [0.0, 0.0]
    play = {"name": "Park", "coords": [0.01, 0.0], "address": "Park Rd", "rating": 4.8}
    eat = {"name": "Bistro", "coords": [0.02, 0.0], "address": "Food St", "rating": 4.5}
    extra = {"name": "Dessert", "coords": [0.03, 0.0], "address": "Sweet Ave", "rating": 4.2}
    cluster = {
        "anchor": play,
        "eat": eat,
        "extra": extra,
        "venues": [play, eat, extra],
    }

    plan = _build_candidate_plan(cluster, home, start_time_hour=14, start_time_minute=0)

    activities = plan["activities"]
    assert len(activities) == 3
    # Optimal order near->far means play -> eat -> extra; types and actions follow.
    assert [a["type"] for a in activities] == ["play", "eat", "extra"]
    assert [a["action"] for a in activities] == ["book", "reserve", "no_action"]
    assert [a["order"] for a in activities] == [1, 2, 3]

    # Start times are strictly increasing and well-formed HH:MM strings.
    times = [a["start_time"] for a in activities]
    assert times == sorted(times)
    for t in times:
        hh, mm = t.split(":")
        assert len(hh) == 2 and len(mm) == 2

    assert plan["total_travel_minutes"] >= 0
    assert plan["total_duration_minutes"] > 0
    assert 0.0 <= plan["walkability_score"] <= 1.0
    assert plan["route_geojson"]["geometry"]["type"] == "LineString"
    # Route starts at home and visits every venue.
    assert plan["route_geojson"]["geometry"]["coordinates"][0] == home
    assert len(plan["route_geojson"]["geometry"]["coordinates"]) == 1 + len(activities)
    assert plan["label"]
    assert plan["spatial_summary"]
