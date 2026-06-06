"use client";

import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import type { CanvasMapMarker, PlanCanvasState, PlanMapData, SpatialVenue } from "@/lib/types";
import { cn } from "@/lib/utils";

interface MapViewProps {
  mapData: PlanMapData | null;
  planCanvas?: PlanCanvasState | null;
  selectedMarkerId?: string | null;
  onSelectMarker?: (markerId: string) => void;
  className?: string;
}

const AMAP_KEY = process.env.NEXT_PUBLIC_AMAP_KEY || "";

type ScriptState = { loaded: boolean; error: string | null };
let scriptState: ScriptState = { loaded: false, error: null };
const SERVER_SNAPSHOT: ScriptState = { loaded: false, error: null };
const listeners = new Set<() => void>();

function getMarkerColor(type: CanvasMapMarker["type"]): string {
  switch (type) {
    case "play":
      return "#16a34a";
    case "eat":
      return "#f97316";
    case "extra":
      return "#7c3aed";
    case "home":
      return "#dc2626";
    default:
      return "#52525b";
  }
}

function getSpatialVenueColor(venue: SpatialVenue): string {
  const cat = (venue.category || "").toLowerCase();
  if (cat.includes("餐") || cat.includes("美食") || cat.includes("火锅") || cat.includes("烧烤")) {
    return "#fdba74";
  }
  if (cat.includes("乐园") || cat.includes("公园") || cat.includes("游乐") || cat.includes("展览") || cat.includes("密室")) {
    return "#86efac";
  }
  return "#c4b5fd";
}

function getSnapshot(): ScriptState {
  return scriptState;
}

function getServerSnapshot(): ScriptState {
  return SERVER_SNAPSHOT;
}

function subscribe(callback: () => void): () => void {
  listeners.add(callback);
  return () => listeners.delete(callback);
}

function loadAmapScript() {
  if (typeof window === "undefined") return;
  if (scriptState.loaded || scriptState.error) return;

  if (window.AMap) {
    scriptState = { loaded: true, error: null };
    listeners.forEach((cb) => cb());
    return;
  }

  if (!AMAP_KEY) {
    scriptState = { loaded: false, error: "Missing NEXT_PUBLIC_AMAP_KEY" };
    listeners.forEach((cb) => cb());
    return;
  }

  const existing = document.querySelector(`script[src*="webapi.amap.com"]`);
  if (existing) return;

  const script = document.createElement("script");
  script.src = `https://webapi.amap.com/maps?v=2.0&key=${AMAP_KEY}`;
  script.async = true;
  script.onload = () => {
    scriptState = { loaded: true, error: null };
    listeners.forEach((cb) => cb());
  };
  script.onerror = () => {
    scriptState = { loaded: false, error: "Failed to load AMap SDK" };
    listeners.forEach((cb) => cb());
  };
  document.head.appendChild(script);
}

function fallbackMarkers(mapData: PlanMapData | null): CanvasMapMarker[] {
  if (!mapData) return [];
  return mapData.venues.map((venue) => ({
    id: `marker_${venue.order}`,
    timeline_item_id: `timeline_${venue.order}`,
    step: venue.order,
    type: venue.type,
    coordinates: venue.venue_coords,
    display_name: venue.display_name || venue.venue_name,
    category_label: venue.type === "play" ? "游玩" : venue.type === "eat" ? "用餐" : "收尾",
    user_description: venue.user_description || venue.reason,
    address: venue.venue_address,
    source_label: "计划地点",
    schedule_text: venue.start_time,
    next_leg_text: venue.travel_to_next_minutes == null ? null : `下一站约${venue.travel_to_next_minutes}分钟`,
    business_status: null,
    actions: [],
  }));
}

function markerLabel(marker: CanvasMapMarker, selected: boolean): string {
  const color = getMarkerColor(marker.type);
  const border = selected ? "#111827" : color;
  const shadow = selected ? "0 4px 12px rgba(17,24,39,0.28)" : "0 1px 4px rgba(0,0,0,0.18)";
  const name = selected ? marker.display_name : "";
  const padding = selected ? "3px 7px" : "4px";
  return `<span style="display:inline-flex;align-items:center;gap:4px;font-size:11px;color:#18181b;font-weight:600;background:white;padding:${padding};border-radius:999px;border:2px solid ${border};box-shadow:${shadow};"><b style="display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:999px;background:${color};color:white;">${marker.step}</b>${name}</span>`;
}

export function MapView({
  mapData,
  planCanvas = null,
  selectedMarkerId = null,
  onSelectMarker,
  className,
}: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<AMap.Map | null>(null);
  const [showCandidates, setShowCandidates] = useState(false);
  const { loaded, error } = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  const markers = useMemo(
    () => planCanvas?.map.markers ?? fallbackMarkers(mapData),
    [mapData, planCanvas?.map.markers]
  );
  const selectedMarker = markers.find((marker) => marker.id === selectedMarkerId) ?? null;
  const homeLocation = useMemo<[number, number]>(
    () => planCanvas?.map.home_location ?? mapData?.home_location ?? [116.481, 39.998],
    [mapData?.home_location, planCanvas?.map.home_location]
  );
  const route = planCanvas?.map.route_geojson ?? mapData?.route ?? null;
  const routeNotice = planCanvas?.map.route_notice ?? null;
  const routeSource = route?.properties?.source;
  const isNavigationRoute = routeSource === "amap";

  useEffect(() => {
    loadAmapScript();
  }, []);

  useEffect(() => {
    if (!loaded || !containerRef.current || mapRef.current) return;

    mapRef.current = new window.AMap.Map(containerRef.current, {
      zoom: 13,
      center: homeLocation,
      mapStyle: "amap://styles/light",
    });
  }, [homeLocation, loaded]);

  useEffect(() => {
    if (!mapRef.current) return;

    const map = mapRef.current;
    map.clearMap();

    const homeMarker = new window.AMap.Marker({
      position: homeLocation,
      map,
      label: {
        content:
          "<span style='font-size:12px;color:#dc2626;font-weight:bold;background:white;padding:2px 6px;border-radius:4px;border:1px solid #dc2626;'>家</span>",
        offset: new window.AMap.Pixel(0, -30),
      },
    });

    const routeOverlays: AMap.Overlay[] = [homeMarker];

    if (mapData?.isochrone?.geometry?.coordinates) {
      const paths = mapData.isochrone.geometry.coordinates[0].map(
        (coord) => new window.AMap.LngLat(coord[0], coord[1])
      );

      new window.AMap.Polygon({
        path: paths,
        fillColor: "#00eeff",
        fillOpacity: 0.05,
        strokeColor: "#00bcd4",
        strokeWeight: 1,
        strokeOpacity: 0.18,
        map,
      });
    }

    if (showCandidates && mapData?.spatialVenues?.length) {
      for (const venue of mapData.spatialVenues) {
        if (!venue.coords) continue;
        const color = getSpatialVenueColor(venue);
        new window.AMap.Marker({
          position: venue.coords,
          map,
          label: {
            content: `<span style="font-size:9px;color:${color};background:white;padding:1px 4px;border-radius:3px;border:1px solid ${color};opacity:0.45;">${venue.name}</span>`,
            offset: new window.AMap.Pixel(0, -25),
          },
        });
      }
    }

    if (route?.geometry?.coordinates) {
      const routePath = route.geometry.coordinates.map((coord) => new window.AMap.LngLat(coord[0], coord[1]));
      const polyline = new window.AMap.Polyline({
        path: routePath,
        strokeColor: isNavigationRoute ? "#1d4ed8" : "#64748b",
        strokeWeight: isNavigationRoute ? 6 : 3,
        strokeOpacity: isNavigationRoute ? 0.9 : 0.45,
        lineJoin: "round",
        lineCap: "round",
        map,
      });
      routeOverlays.push(polyline);
    }

    for (const markerData of markers) {
      const marker = new window.AMap.Marker({
        position: markerData.coordinates,
        map,
        label: {
          content: markerLabel(markerData, markerData.id === selectedMarkerId),
          offset: new window.AMap.Pixel(0, -35),
        },
      });
      marker.on("click", () => onSelectMarker?.(markerData.id));
      routeOverlays.push(marker);
    }

    if (routeOverlays.length > 1) {
      map.setFitView(routeOverlays, false, [130, 160, 130, 160]);
    }
  }, [
    homeLocation,
    isNavigationRoute,
    mapData?.isochrone,
    mapData?.spatialVenues,
    markers,
    onSelectMarker,
    route,
    selectedMarkerId,
    showCandidates,
  ]);

  if (error) {
    return (
      <div className={cn("flex items-center justify-center rounded-lg bg-zinc-100", className)}>
        <div className="p-6 text-center">
          <p className="text-sm text-zinc-500">{error}</p>
          <p className="mt-1 text-xs text-zinc-400">Please set NEXT_PUBLIC_AMAP_KEY in .env.local</p>
        </div>
      </div>
    );
  }

  if (!loaded) {
    return (
      <div className={cn("flex items-center justify-center rounded-lg bg-zinc-100", className)}>
        <div className="p-6 text-center">
          <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-zinc-300 border-t-zinc-600" />
          <p className="mt-2 text-sm text-zinc-500">Loading map...</p>
        </div>
      </div>
    );
  }

  return (
    <div className={cn("relative overflow-hidden rounded-lg", className)}>
      {mapData?.spatialVenues?.length ? (
        <button
          className="absolute right-3 top-3 z-10 rounded-md border border-zinc-200 bg-white px-3 py-1.5 text-xs font-medium text-zinc-700 shadow-sm hover:bg-zinc-50"
          type="button"
          onClick={() => setShowCandidates((value) => !value)}
        >
          {showCandidates ? "隐藏候选地点" : "显示候选地点"}
        </button>
      ) : null}

      {route ? (
        <div
          className={cn(
            "absolute left-3 top-3 z-20 max-w-[310px] rounded-md border px-3 py-2 text-xs font-medium shadow-md",
            isNavigationRoute
              ? "border-green-200 bg-green-50/95 text-green-800"
              : "border-amber-200 bg-amber-50/95 text-amber-800"
          )}
        >
          {routeNotice ?? (isNavigationRoute ? "已按导航路线展示" : "示意路线：按活动顺序连接，实际导航以地图为准")}
        </div>
      ) : null}

      {selectedMarker && (
        <div className="absolute bottom-4 left-4 z-20 max-w-[340px] rounded-lg border border-zinc-200 bg-white p-4 shadow-xl">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-xs font-medium text-zinc-500">{selectedMarker.category_label}</div>
              <div className="mt-1 text-base font-semibold text-zinc-950">{selectedMarker.display_name}</div>
            </div>
            <div className="rounded-md bg-zinc-100 px-2 py-1 text-xs text-zinc-600">{selectedMarker.source_label}</div>
          </div>
          <div className="mt-2 text-sm leading-5 text-zinc-600">{selectedMarker.user_description}</div>
          <div className="mt-3 space-y-1 text-xs text-zinc-500">
            <div>{selectedMarker.schedule_text}</div>
            {selectedMarker.business_status && <div>{selectedMarker.business_status}</div>}
            {selectedMarker.next_leg_text && <div>{selectedMarker.next_leg_text}</div>}
            {selectedMarker.address && <div>{selectedMarker.address}</div>}
          </div>
          {selectedMarker.actions.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {selectedMarker.actions.map((action) => (
                <span key={action} className="rounded-md border border-zinc-200 px-2 py-1 text-xs text-zinc-600">
                  {action}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      <div ref={containerRef} className="h-full w-full" aria-label="Activity plan map" />
    </div>
  );
}
