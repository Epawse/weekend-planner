export type Scenario = "family" | "friends";

export interface Activity {
  order: number;
  type: "play" | "eat" | "extra";
  venue_name: string;
  display_name?: string;
  venue_address: string;
  venue_coords: [number, number];
  start_time: string;
  duration_minutes: number;
  travel_to_next_minutes: number | null;
  action: "book" | "reserve" | "order_delivery" | "no_action";
  action_details: Record<string, unknown>;
  reason: string;
  user_description?: string;
  debug_description?: string;
  evidence_ids?: string[];
  validated_evidence_claims?: string[];
  family_features?: Record<string, unknown>;
  friend_features?: Record<string, unknown>;
  poi_type?: string;
  typecode?: string;
  tags?: string[];
  biz_type?: string[];
  source?: "amap_real_poi" | "showcase_curated" | "fallback_generated" | string;
  trust_level?: string;
}

export interface FamilyProfile {
  scenario: Scenario;
  party_size: number;
  adults: number;
  children: number;
  child_age: number;
  child_age_band: string;
  diet_goal: string;
  nearby_preference: boolean;
  start_time: string;
  max_total_minutes: number;
  max_drive_minutes: number;
  max_walk_minutes: number;
  max_queue_minutes: number;
  min_total_minutes?: number;
  target_total_minutes?: number;
  prefer_indoor: boolean;
  need_child_seat: boolean;
  risk_level: string;
  strong_child_intent?: boolean;
  prefer_eat_first?: boolean;
}

export interface FamilyStrategy {
  title: string;
  summary?: string;
  non_negotiables?: string[];
  priorities?: string[];
  compensations?: string[];
}

export type FamilyCheckStatus = "pass" | "warn" | "fail";

export interface FamilyCheck {
  id: string;
  label: string;
  status: FamilyCheckStatus;
  detail: string;
}

export interface FriendProfile {
  scenario: Scenario;
  party_size: number;
  group_composition: string;
  preferences: string[];
  nearby_preference: boolean;
  chat_preference: boolean;
  photo_preference: boolean;
  start_time: string;
  min_total_minutes: number;
  target_total_minutes: number;
  max_total_minutes: number;
  max_drive_minutes: number;
  max_queue_minutes: number;
  dinner_window: string;
  risk_level: string;
}

export interface FriendStrategy {
  title: string;
  summary?: string;
  non_negotiables?: string[];
  priorities?: string[];
  compensations?: string[];
}

export type FriendCheck = FamilyCheck;

export interface EvidenceItem {
  id: string;
  claim: string;
  evidence: string;
  source:
    | "real_api"
    | "keyword_rule"
    | "mock_business_api"
    | "amap_real_poi"
    | "showcase_curated"
    | "fallback_generated"
    | string;
  confidence: "high" | "medium" | "simulated" | string;
  venue_name: string;
}

export interface AlternativePlan {
  id: string;
  title: string;
  fatigue_score: number | null;
  reason: string;
  checks: FamilyCheck[];
}

export interface RejectedOption {
  label: string;
  reasons: string[];
  score: number;
}

export interface Plan {
  title: string;
  duration_hours: number;
  activities: Activity[];
  total_travel_minutes: number;
  share_text: string;
  route_geojson?: RouteGeoJSON | null;
  walkability_score?: number;
  family_profile?: FamilyProfile | null;
  family_strategy?: FamilyStrategy | null;
  family_checks?: FamilyCheck[];
  fatigue_score?: number | null;
  fatigue_level?: "low" | "medium" | "high" | "unknown";
  family_summary?: string;
  friend_profile?: FriendProfile | null;
  friend_strategy?: FriendStrategy | null;
  friend_checks?: FriendCheck[];
  social_score?: number | null;
  friend_fit_level?: string | null;
  friend_summary?: string;
  evidence?: EvidenceItem[];
  degradations?: string[];
  alternatives?: AlternativePlan[];
  rejected_options?: RejectedOption[];
  pre_departure_tips?: string[];
}

export type CanvasStatus = "plan_ready" | "feedback_applied" | "executing" | "done";
export type CanvasActionStatus = "pending" | "running" | "done" | "failed" | "skipped";
export type ToolTaskStatus = "pending" | "running" | "done" | "warn" | "failed";

export interface CanvasMetrics {
  total_duration_text: string;
  travel_time_text: string;
  end_time_text: string;
  fit_label: string;
  route_label: string;
}

export interface CanvasTimelineItem {
  id: string;
  step: number;
  time: string;
  end_time: string;
  duration_text: string;
  display_name: string;
  category_label: string;
  user_description: string;
  address: string;
  map_marker_id: string;
  evidence_ids: string[];
  actions: string[];
}

export interface CanvasCheck {
  id: string;
  label: string;
  detail: string;
  status: "pass" | "warn" | "fail";
}

export interface CanvasChecks {
  passed: CanvasCheck[];
  warnings: CanvasCheck[];
  failed: CanvasCheck[];
}

export interface EvidenceCardItem {
  id: string;
  title: string;
  source_label: string;
  subject: string;
  detail: string;
  related_timeline_ids: string[];
  related_marker_ids: string[];
}

export interface RejectedCanvasOption {
  id: string;
  name: string;
  reason: string;
  source_label: string;
}

export interface CanvasMapMarker {
  id: string;
  timeline_item_id: string;
  step: number;
  type: "home" | "play" | "eat" | "extra";
  coordinates: [number, number];
  display_name: string;
  category_label: string;
  user_description: string;
  address: string;
  source_label: string;
  schedule_text: string;
  next_leg_text: string | null;
  business_status: string | null;
  actions: string[];
}

export interface CanvasMapState {
  home_marker_id: string;
  home_location: [number, number];
  markers: CanvasMapMarker[];
  route_geojson: RouteGeoJSON | null;
  route_notice: string;
}

export interface CanvasFeedbackHistoryItem {
  id: string;
  label: string;
  user_text: string;
  result_message: string;
}

export interface FeedbackChangeSummary {
  title: string;
  result: string;
  before: string;
  after: string;
  preserved: string[];
  changed: string[];
  note: string | null;
}

export interface CanvasFeedback {
  quick_actions: string[];
  history: CanvasFeedbackHistoryItem[];
  change_summary: FeedbackChangeSummary | null;
}

export interface ToolTask {
  id: string;
  label: string;
  status: ToolTaskStatus;
  detail: string;
}

export interface ExecutionAction {
  id: string;
  label: string;
  status: CanvasActionStatus;
  target: string;
  detail: string | null;
  confirmation: string | null;
  scheduled_time: string | null;
  party_size: number | null;
  note: string | null;
  next_step: string | null;
}

export interface PlanCanvasState {
  canvas_id: string;
  scenario: Scenario;
  status: CanvasStatus;
  title: string;
  summary: string;
  metrics: CanvasMetrics;
  timeline: CanvasTimelineItem[];
  checks: CanvasChecks;
  evidence_cards: EvidenceCardItem[];
  rejected_options: RejectedCanvasOption[];
  map: CanvasMapState;
  feedback: CanvasFeedback;
  tool_tasks: ToolTask[];
  pending_actions: ExecutionAction[];
  execution_results: ExecutionAction[];
  share_text: string;
  modification_notice: string | null;
}

export type PlanEventType =
  | "session"
  | "thinking"
  | "tool_calling"
  | "tool_result"
  | "plan_generated"
  | "family_profile"
  | "family_strategy"
  | "family_filter_result"
  | "friend_profile"
  | "friend_strategy"
  | "friend_filter_result"
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

export interface PlanFeedbackRequest {
  session_id: string;
  message: string;
  quick_action?: string | null;
}

export interface PlanFeedbackResponse {
  session_id: string;
  message: string;
  plan: Plan;
  plan_canvas: PlanCanvasState;
}

export type ParticipantId = "red" | "green" | "blue" | "pink" | "agent";
export type RoomMessageType = "user_message" | "agent_message" | "system_message";
export type RoomVoteType = "support" | "oppose";
export type RoomReactionType =
  | "like"
  | "neutral"
  | "veto"
  | "too_far"
  | "too_noisy"
  | "too_expensive"
  | "food_exclusion";

export interface ParticipantProfile {
  distance: string;
  budget: string;
  vibe: string;
  food_exclusions: string[];
  likes: string[];
}

export interface Participant {
  id: ParticipantId;
  name: string;
  color: string;
  avatar: string;
  role: "host" | "member" | "agent";
  status: "online" | "invited" | "agent";
  preference_profile: ParticipantProfile;
}

export interface SharedMessage {
  id: string;
  actor_id: ParticipantId;
  actor_name: string;
  actor_avatar: string;
  type: RoomMessageType;
  content: string;
  created_at: string;
  related_plan_id: string | null;
}

export interface Vote {
  participant_id: ParticipantId;
  target_type: "plan";
  target_id: string;
  vote_type: RoomVoteType;
  reason: string;
}

export interface Reaction {
  participant_id: ParticipantId;
  target_type: "venue";
  target_id: string;
  reaction_type: RoomReactionType;
  label: string;
  reason: string;
}

export interface GroupConflict {
  topic: string;
  supporters: ParticipantId[];
  opponents: ParticipantId[];
  resolution: string;
}

export interface GroupMemoryItem {
  round: number;
  summary: string;
}

export interface GroupMemory {
  confirmed_constraints: string[];
  soft_preferences: string[];
  conflicts: GroupConflict[];
  history: GroupMemoryItem[];
}

export interface PlanOptionScore {
  distance: number;
  budget: number;
  photo: number;
  indoor: number;
  consensus: number;
}

export interface PlanOptionVoteSummary {
  supporters: ParticipantId[];
  opponents: ParticipantId[];
  concerns: string[];
}

export interface PlanOption {
  option_id: string;
  label: string;
  positioning: string;
  plan_canvas: PlanCanvasState;
  vote_summary: PlanOptionVoteSummary;
  score: PlanOptionScore;
  is_recommended: boolean;
}

export interface ConsensusState {
  required_votes: number;
  current_votes: number;
  status: "collecting" | "split" | "consensus_reached";
  active_plan_id: string;
  summary: string;
}

export interface RoomExecutionState {
  status: "not_started" | "ready" | "executing" | "completed";
  host_can_execute: boolean;
  summary: string;
}

export interface RoomState {
  room_id: string;
  scenario: Scenario;
  host_user_id: ParticipantId;
  active_user_id: ParticipantId;
  participants: Participant[];
  messages: SharedMessage[];
  group_memory: GroupMemory;
  plan_options: PlanOption[];
  active_plan_id: string;
  votes: Vote[];
  reactions: Reaction[];
  consensus: ConsensusState;
  execution_state: RoomExecutionState;
}

export interface RoomMessageRequest {
  actor_id: ParticipantId;
  content: string;
}

export interface RoomVoteRequest {
  participant_id: ParticipantId;
  plan_id: string;
  reason?: string;
}

export interface RoomReactionRequest {
  participant_id: ParticipantId;
  venue_id: string;
  reaction_type: RoomReactionType;
  reason?: string;
}

export interface RoomExecuteRequest {
  actor_id: ParticipantId;
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
  poi_type?: string;
  typecode?: string;
  tags?: string[];
  biz_type?: string[];
  source?: "amap_real_poi" | "showcase_curated" | "fallback_generated" | string;
  trust_level?: string;
}

export interface PlanMapData {
  isochrone: GeoJSONPolygon | null;
  route: RouteGeoJSON | null;
  venues: Activity[];
  spatialVenues: SpatialVenue[];
  home_location: [number, number];
}
