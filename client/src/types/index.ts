/** Shared TypeScript domain types mirroring the backend API. */

export type Role = "admin" | "sar_officer";
export type MissionStatus =
  | "draft"
  | "active"
  | "paused"
  | "completed"
  | "cancelled";
export type LkpAccuracy = "high" | "medium" | "low";

export interface User {
  id: number;
  username: string;
  email: string;
  full_name: string;
  designation?: string | null;
  phone?: string | null;
  role: Role;
  is_active: boolean;
  created_at: string;
}

export interface UserBrief {
  id: number;
  username: string;
  full_name: string;
  role: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: UserBrief;
}

export interface DashboardStats {
  total_missions: number;
  active_missions: number;
  paused_missions: number;
  completed_missions: number;
  aircraft_missing_today: number;
  high_risk_missions: number;
  active_search_area_sqnm: number;
}

export interface SearchArea {
  id: number;
  center_latitude: number;
  center_longitude: number;
  radius_nm: number;
  area_sqnm: number;
  polygon_geojson: string;
  track_spacing_nm: number;
  desired_coverage_pct: number;
}

export interface SearchPattern {
  id: number;
  pattern_type: string;
  reason?: string | null;
  recommended: boolean;
  params_json: string;
  waypoints_geojson: string;
  track_spacing_nm: number;
}

export interface ProbabilityZone {
  id: number;
  zone_level: "high" | "medium" | "low";
  color: string;
  min_radius_nm: number;
  max_radius_nm: number;
  probability_pct: number;
  polygon_geojson: string;
}

export interface Sector {
  id: number;
  code: string;
  name: string;
  color: string;
  assigned_aircraft?: string | null;
}

export interface SectorDetail {
  id: number;
  mission_id: number;
  code: string;
  name: string;
  color: string;
  start_angle_deg: number;
  end_angle_deg: number;
  center_latitude: number;
  center_longitude: number;
  area_sqnm: number;
  assigned_aircraft?: string | null;
  polygon_geojson: string;
}

export interface Mission {
  id: number;
  mission_name: string;
  status: MissionStatus;
  flight_number?: string | null;
  aircraft_name?: string | null;
  registration_number?: string | null;
  aircraft_type?: string | null;
  pilot_name?: string | null;
  departure_airport?: string | null;
  destination_airport?: string | null;
  lkp_latitude: number;
  lkp_longitude: number;
  altitude_ft: number;
  ground_speed_kts: number;
  heading_deg: number;
  last_contact_time: string;
  fuel_remaining_hours: number;
  wind_speed_kts: number;
  wind_direction_deg: number;
  weather_conditions: string;
  visibility_nm: number;
  remarks?: string | null;
  lkp_accuracy: LkpAccuracy;
  is_route_known: boolean;
  elapsed_hours: number;
  distance_nm: number;
  search_radius_nm: number;
  search_area_sqnm: number;
  uncertainty_nm: number;
  weather_impact: number;
  risk_score: number;
  priority_rank: number;
  predicted_latitude?: number | null;
  predicted_longitude?: number | null;
  desired_coverage_pct: number;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
  search_area?: SearchArea | null;
  patterns?: SearchPattern[];
  zones?: ProbabilityZone[];
  sectors?: Sector[];
  logs?: ActivityItem[];
}

export interface MissionListItem {
  id: number;
  mission_name: string;
  status: MissionStatus;
  flight_number?: string | null;
  aircraft_name?: string | null;
  registration_number?: string | null;
  aircraft_type?: string | null;
  pilot_name?: string | null;
  lkp_latitude: number;
  lkp_longitude: number;
  last_contact_time: string;
  elapsed_hours: number;
  distance_nm: number;
  search_radius_nm: number;
  search_area_sqnm: number;
  risk_score: number;
  priority_rank: number;
  weather_conditions: string;
  created_at: string;
  completed_at?: string | null;
}

export interface MissionCreatePayload {
  mission_name: string;
  flight_number?: string;
  aircraft_name?: string;
  registration_number?: string;
  aircraft_type?: string;
  pilot_name?: string;
  departure_airport?: string;
  destination_airport?: string;
  lkp_latitude: number;
  lkp_longitude: number;
  altitude_ft?: number;
  ground_speed_kts?: number;
  heading_deg?: number;
  last_contact_time: string;
  fuel_remaining_hours?: number;
  wind_speed_kts?: number;
  wind_direction_deg?: number;
  weather_conditions?: string;
  visibility_nm?: number;
  remarks?: string;
  lkp_accuracy?: LkpAccuracy;
  is_route_known?: boolean;
}

export interface WeatherLive {
  temperature_c?: number | null;
  apparent_temperature_c?: number | null;
  humidity?: number | null;
  precipitation_mm?: number | null;
  wind_speed_kts?: number | null;
  wind_direction_deg?: number | null;
  pressure_hpa?: number | null;
  visibility_km?: number | null;
  conditions?: string | null;
  source?: string;
  forecast?: Array<{
    time: string;
    temperature_c: number | null;
    precipitation_mm: number;
    wind_speed_kts: number;
  }>;
  error?: boolean;
  detail?: string;
}

export interface Analysis {
  mission_id: number;
  risk: {
    score: number;
    rating: string;
    tone: string;
    factors: Array<{ name: string; value: number; max: number; severity: string }>;
    summary: string;
  };
  crash_prediction: {
    latitude: number | null;
    longitude: number | null;
    confidence_nm: number;
    drift_bearing: number;
  };
  weather_impact: {
    current_impact: number;
    severity: string;
    trend: string;
    recommendation: string;
    effective_visibility_nm: number;
    track_spacing_recommendation_nm: number;
  };
  terrain_roughness: number;
  recommendations: Array<{ type: string; title: string; detail: string }>;
  simulation: Array<{
    hours_from_now: number;
    elapsed_hours: number;
    radius_nm: number;
    area_sqnm: number;
  }>;
}

export interface ActivityItem {
  id: number;
  mission_id?: number | null;
  action: string;
  description?: string | null;
  created_at: string;
}

export interface MissionOverviewItem {
  id: number;
  mission_name: string;
  status: string;
  lkp_latitude: number;
  lkp_longitude: number;
  predicted_latitude?: number | null;
  predicted_longitude?: number | null;
  search_radius_nm: number;
  search_area_sqnm: number;
  risk_score: number;
  heading_deg: number;
  ground_speed_kts: number;
  elapsed_hours: number;
  weather_conditions: string;
  last_contact_time: string;
}

export interface Aircraft {
  id: number;
  name: string;
  registration_number: string;
  aircraft_type: string;
  operator?: string | null;
}

export interface Report {
  id: number;
  mission_id: number;
  report_type: string;
  title: string;
  created_at: string;
}

export interface Notification {
  level: "critical" | "warning" | "info";
  message: string;
}
