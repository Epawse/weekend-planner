export type Scenario = "family" | "friends";

export interface Activity {
  order: number;
  type: "play" | "eat" | "extra";
  venue_name: string;
  venue_address: string;
  venue_coords: [number, number];
  start_time: string;
  duration_minutes: number;
  travel_to_next_minutes: number | null;
  action: "book" | "reserve" | "order_delivery" | "no_action";
  action_details: Record<string, unknown>;
  reason: string;
}

export interface Plan {
  title: string;
  duration_hours: number;
  activities: Activity[];
  total_travel_minutes: number;
  share_text: string;
  walkability_score?: number;
}

export type PlanEventType =
  | "session"
  | "thinking"
  | "tool_calling"
  | "tool_result"
  | "plan_generated"
  | "plan_ready"
  | "interrupted"
  | "node_complete"
  | "step_start"
  | "step_complete"
  | "step_failed"
  | "all_complete"
  | "done"
  | "error"
  | "unknown";

export interface PlanEvent {
  type: PlanEventType;
  timestamp: string;
  data: Record<string, unknown>;
}

export interface PlanCreateRequest {
  message: string;
  scenario: Scenario;
  home_location: [number, number];
}

export interface PlanApproveRequest {
  session_id: string;
  approved: boolean;
}

export type PlanStatus =
  | "idle"
  | "planning"
  | "plan_ready"
  | "executing"
  | "done"
  | "error";

export interface GeoJSONPolygon {
  type: "Feature";
  geometry: {
    type: "Polygon";
    coordinates: number[][][];
  };
  properties: Record<string, unknown>;
}

export interface RouteGeoJSON {
  type: "Feature";
  geometry: {
    type: "LineString";
    coordinates: number[][];
  };
  properties: Record<string, unknown>;
}

/**
 * Raw venue data from the backend spatial analysis engine.
 * These are all venues found within the isochrone, not just the selected plan venues.
 */
export interface SpatialVenue {
  id: string;
  name: string;
  address: string;
  coords: [number, number];
  category: string;
  rating: number | null;
  distance?: number;
  business_area?: string;
}

export interface PlanMapData {
  isochrone: GeoJSONPolygon | null;
  route: RouteGeoJSON | null;
  venues: Activity[];
  spatialVenues: SpatialVenue[];
  home_location: [number, number];
}
