"use client";

import { useEffect, useRef, useSyncExternalStore } from "react";
import type { PlanMapData } from "@/lib/types";
import { cn } from "@/lib/utils";

interface MapViewProps {
  mapData: PlanMapData | null;
  className?: string;
}

const AMAP_KEY = process.env.NEXT_PUBLIC_AMAP_KEY || "";

function getMarkerColor(type: "play" | "eat" | "extra"): string {
  switch (type) {
    case "play":
      return "#22c55e";
    case "eat":
      return "#f97316";
    case "extra":
      return "#a855f7";
    default:
      return "#6b7280";
  }
}

// External store for AMap script loading state
type ScriptState = { loaded: boolean; error: string | null };
let scriptState: ScriptState = { loaded: false, error: "" };
const listeners = new Set<() => void>();

function getSnapshot(): ScriptState {
  return scriptState;
}

function getServerSnapshot(): ScriptState {
  return { loaded: false, error: null };
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

  // Check if script tag already exists
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

export function MapView({ mapData, className }: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<AMap.Map | null>(null);

  const { loaded, error } = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  // Trigger script loading
  useEffect(() => {
    loadAmapScript();
  }, []);

  // Initialize map
  useEffect(() => {
    if (!loaded || !containerRef.current) return;
    if (mapRef.current) return;

    const center = mapData?.home_location || [116.481, 39.998];

    mapRef.current = new window.AMap.Map(containerRef.current, {
      zoom: 13,
      center: center,
      mapStyle: "amap://styles/light",
    });

    // Add home marker
    new window.AMap.Marker({
      position: center,
      map: mapRef.current,
      label: {
        content: "<span style='font-size:12px;color:#dc2626;font-weight:bold;'>家</span>",
        offset: new window.AMap.Pixel(0, -30),
      },
    });
  }, [loaded, mapData?.home_location]);

  // Update map with plan data
  useEffect(() => {
    if (!mapRef.current || !mapData) return;

    const map = mapRef.current;

    // Clear existing overlays (except home marker)
    map.clearMap();

    // Re-add home marker
    const homeMarker = new window.AMap.Marker({
      position: mapData.home_location,
      map: map,
      label: {
        content: "<span style='font-size:12px;color:#dc2626;font-weight:bold;'>家</span>",
        offset: new window.AMap.Pixel(0, -30),
      },
    });

    const overlays: AMap.Overlay[] = [homeMarker];

    // Draw isochrone polygon
    if (mapData.isochrone?.geometry?.coordinates) {
      const paths = mapData.isochrone.geometry.coordinates[0].map(
        (coord) => new window.AMap.LngLat(coord[0], coord[1])
      );

      const polygon = new window.AMap.Polygon({
        path: paths,
        fillColor: "#00eeff",
        fillOpacity: 0.15,
        strokeColor: "#00bcd4",
        strokeWeight: 2,
        strokeOpacity: 0.6,
        map: map,
      });
      overlays.push(polygon);
    }

    // Draw route polyline
    if (mapData.route?.geometry?.coordinates) {
      const routePath = mapData.route.geometry.coordinates.map(
        (coord) => new window.AMap.LngLat(coord[0], coord[1])
      );

      const polyline = new window.AMap.Polyline({
        path: routePath,
        strokeColor: "#1d4ed8",
        strokeWeight: 4,
        strokeOpacity: 0.8,
        lineJoin: "round",
        lineCap: "round",
        map: map,
      });
      overlays.push(polyline);
    }

    // Add venue markers
    for (const venue of mapData.venues) {
      const color = getMarkerColor(venue.type);
      const marker = new window.AMap.Marker({
        position: venue.venue_coords,
        map: map,
        label: {
          content: `<span style="font-size:11px;color:${color};font-weight:600;background:white;padding:2px 6px;border-radius:4px;border:1px solid ${color};">${venue.order}. ${venue.venue_name}</span>`,
          offset: new window.AMap.Pixel(0, -35),
        },
      });
      overlays.push(marker);
    }

    // Fit map to show all overlays
    if (overlays.length > 1) {
      map.setFitView(overlays, false, [60, 60, 60, 60]);
    }
  }, [mapData]);

  if (error) {
    return (
      <div className={cn("flex items-center justify-center bg-zinc-100 rounded-xl", className)}>
        <div className="text-center p-6">
          <p className="text-sm text-zinc-500">{error}</p>
          <p className="mt-1 text-xs text-zinc-400">Please set NEXT_PUBLIC_AMAP_KEY in .env.local</p>
        </div>
      </div>
    );
  }

  if (!loaded) {
    return (
      <div className={cn("flex items-center justify-center bg-zinc-100 rounded-xl", className)}>
        <div className="text-center p-6">
          <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-zinc-300 border-t-zinc-600" />
          <p className="mt-2 text-sm text-zinc-500">Loading map...</p>
        </div>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={cn("rounded-xl overflow-hidden", className)}
      aria-label="Activity plan map"
    />
  );
}
