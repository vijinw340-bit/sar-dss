import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  ClipboardList,
  CloudSun,
  Loader2,
  MapPin,
  Plane,
  Radar,
  Wind,
} from "lucide-react";
import { apiGet, apiError } from "@/lib/api";
import type {
  ActivityItem,
  DashboardStats,
  MissionOverviewItem,
  Notification,
  WeatherLive,
} from "@/types";
import { MissionMap } from "@/components/map/MissionMap";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { fmt, fmtDate, fmtElapsed, riskTone, statusStyles } from "@/lib/utils";

function StatCard({
  label,
  value,
  icon: Icon,
  delay,
  accent,
}: {
  label: string;
  value: number | string;
  icon: React.ComponentType<{ className?: string }>;
  delay: number;
  accent: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay }}
    >
      <Card className="glass overflow-hidden">
        <CardContent className="flex items-center justify-between p-5">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
            <p className="mt-1 text-3xl font-bold text-navy-900 dark:text-white">{value}</p>
          </div>
          <div className={`flex h-12 w-12 items-center justify-center rounded-xl ${accent}`}>
            <Icon className="h-6 w-6" />
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}

export function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [missions, setMissions] = useState<MissionOverviewItem[]>([]);
  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [weather, setWeather] = useState<WeatherLive | null>(null);
  const [weatherLoading, setWeatherLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    apiGet<DashboardStats>("/dashboard/stats").then(setStats).catch((e) => setError(apiError(e)));
    apiGet<MissionOverviewItem[]>("/dashboard/missions-overview").then(setMissions).catch(() => undefined);
    apiGet<ActivityItem[]>("/dashboard/activities?limit=8").then(setActivities).catch(() => undefined);
    apiGet<Notification[]>("/dashboard/notifications").then(setNotifications).catch(() => undefined);
  }, []);

  const loadWeather = async (lat: number, lon: number) => {
    setWeatherLoading(true);
    try {
      const w = await apiGet<WeatherLive>(`/weather/live?lat=${lat}&lon=${lon}`);
      if (!w.error) setWeather(w);
    } catch {
      /* offline - ignore */
    } finally {
      setWeatherLoading(false);
    }
  };

  useEffect(() => {
    if (missions.length && !weather) loadWeather(missions[0].lkp_latitude, missions[0].lkp_longitude);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [missions.length]);

  const mapCenter: [number, number] =
    missions.length > 0 ? [missions[0].lkp_latitude, missions[0].lkp_longitude] : [0, 0];

  return (
    <div className="space-y-6">
      {error && (
        <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">{error}</div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Total Missions" value={stats?.total_missions ?? "—"} icon={ClipboardList} delay={0} accent="bg-sky-100 text-sky-600 dark:bg-sky-900/40 dark:text-sky-300" />
        <StatCard label="Active Missions" value={stats?.active_missions ?? "—"} icon={Radar} delay={0.05} accent="bg-emerald-100 text-emerald-600 dark:bg-emerald-900/40 dark:text-emerald-300" />
        <StatCard label="Completed" value={stats?.completed_missions ?? "—"} icon={Activity} delay={0.1} accent="bg-blue-100 text-blue-600 dark:bg-blue-900/40 dark:text-blue-300" />
        <StatCard label="Missing Today" value={stats?.aircraft_missing_today ?? "—"} icon={AlertTriangle} delay={0.15} accent="bg-red-100 text-red-600 dark:bg-red-900/40 dark:text-red-300" />
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        {/* Live map */}
        <Card className="glass xl:col-span-2">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base">Live Mission Map</CardTitle>
                <CardDescription>Active and paused missions with search areas</CardDescription>
              </div>
              <Button asChild variant="outline" size="sm">
                <Link to="/missions">All missions <ArrowRight className="h-3.5 w-3.5" /></Link>
              </Button>
            </div>
          </CardHeader>
          <CardContent className="p-3 pt-0">
            <div className="h-[420px] w-full overflow-hidden rounded-xl">
              <MissionMap
                center={mapCenter}
                radiusNm={missions[0]?.search_radius_nm}
                showZones={false}
                showSectors={false}
                showPattern={false}
                showGrid
                showNearbyAirports
                missionName={missions[0]?.mission_name}
                flightNumber=""
                heading={missions[0]?.heading_deg}
              />
            </div>
            <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
              {missions.slice(0, 4).map((m) => (
                <Link
                  key={m.id}
                  to={`/missions/${m.id}`}
                  className="flex items-center justify-between rounded-lg border bg-card p-3 transition-colors hover:bg-accent"
                >
                  <div className="flex items-center gap-2">
                    <Plane className="h-4 w-4 text-primary" />
                    <div>
                      <p className="text-sm font-medium">{m.mission_name}</p>
                      <p className="text-xs text-muted-foreground">
                        {fmtElapsed(m.elapsed_hours)} ago · {fmt(m.search_radius_nm)} nm
                      </p>
                    </div>
                  </div>
                  <Badge variant="secondary" className={statusStyles[m.status]?.dot ? "gap-1.5" : ""}>
                    <span className={`h-1.5 w-1.5 rounded-full ${statusStyles[m.status]?.dot}`} />
                    {statusStyles[m.status]?.label}
                  </Badge>
                </Link>
              ))}
              {missions.length === 0 && (
                <p className="col-span-full py-6 text-center text-sm text-muted-foreground">
                  No active missions. <Link className="text-primary hover:underline" to="/missions/new">Create one →</Link>
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        <div className="space-y-6">
          {/* Weather widget */}
          <Card className="glass">
            <CardHeader className="pb-3">
              <div className="flex items-center gap-2">
                <CloudSun className="h-4 w-4 text-primary" />
                <CardTitle className="text-base">Weather at LKP</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              {weatherLoading && !weather ? (
                <div className="space-y-2">
                  <Skeleton className="h-8 w-24" />
                  <Skeleton className="h-4 w-full" />
                </div>
              ) : weather ? (
                <div>
                  <div className="flex items-end gap-3">
                    <p className="text-4xl font-bold text-navy-900 dark:text-white">
                      {weather.temperature_c !== null && weather.temperature_c !== undefined ? `${Math.round(weather.temperature_c)}°C` : "—"}
                    </p>
                    <div className="pb-1">
                      <p className="text-sm font-medium">{weather.conditions ?? "Unknown"}</p>
                      <p className="text-xs text-muted-foreground">{weather.source}</p>
                    </div>
                  </div>
                  <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
                    <div className="flex items-center gap-2 rounded-lg bg-muted/50 p-2.5">
                      <Wind className="h-4 w-4 text-primary" />
                      <div>
                        <p className="text-xs text-muted-foreground">Wind</p>
                        <p className="font-medium">{weather.wind_speed_kts ?? 0} kt @ {weather.wind_direction_deg ?? 0}°</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 rounded-lg bg-muted/50 p-2.5">
                      <MapPin className="h-4 w-4 text-primary" />
                      <div>
                        <p className="text-xs text-muted-foreground">Visibility</p>
                        <p className="font-medium">{weather.visibility_km ? `${fmt(weather.visibility_km, 0)} km` : "—"}</p>
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">Weather unavailable.</p>
              )}
            </CardContent>
          </Card>

          {/* Notifications */}
          <Card className="glass">
            <CardHeader className="pb-3">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-amber-500" />
                <CardTitle className="text-base">Notifications</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-2">
              {notifications.length === 0 && <p className="text-sm text-muted-foreground">Loading…</p>}
              {notifications.map((n, i) => (
                <div
                  key={i}
                  className={`rounded-lg border p-2.5 text-xs ${
                    n.level === "critical"
                      ? "border-red-300 bg-red-50 text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300"
                      : n.level === "warning"
                        ? "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-300"
                        : "border-border bg-muted/40 text-muted-foreground"
                  }`}
                >
                  {n.message}
                </div>
              ))}
            </CardContent>
          </Card>

          {/* Risk ranking */}
          <Card className="glass">
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Priority Ranking</CardTitle>
              <CardDescription>By computed risk score</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {missions.slice(0, 5).map((m, i) => {
                const tone = riskTone(m.risk_score);
                return (
                  <Link key={m.id} to={`/missions/${m.id}`} className="block">
                    <div className="flex items-center justify-between text-sm">
                      <span className="flex items-center gap-2 truncate">
                        <span className="font-bold text-muted-foreground">#{i + 1}</span>
                        <span className="truncate font-medium">{m.mission_name}</span>
                      </span>
                      <span className={`text-xs font-semibold ${tone.text}`}>{Math.round(m.risk_score)}</span>
                    </div>                    <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-secondary">
                      <div className={`h-full ${tone.bar}`} style={{ width: `${Math.min(100, m.risk_score)}%` }} />
                    </div>
                  </Link>
                );
              })}
              {missions.length === 0 && <p className="text-sm text-muted-foreground">No active missions.</p>}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Recent activity */}
      <Card className="glass">
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Recent Activity</CardTitle>
        </CardHeader>
        <CardContent>
          {activities.length === 0 ? (
            <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading…
            </div>
          ) : (
            <div className="space-y-0">
              {activities.map((a) => (
                <div key={a.id} className="flex items-start gap-3 border-b py-2.5 last:border-0">
                  <div className="mt-0.5 flex h-7 w-7 items-center justify-center rounded-full bg-primary/10">
                    <Activity className="h-3.5 w-3.5 text-primary" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm">
                      <span className="font-medium capitalize">{a.action.replace(/_/g, " ")}</span>
                      {a.description && <span className="text-muted-foreground"> — {a.description}</span>}
                    </p>
                    <p className="text-xs text-muted-foreground">{fmtDate(a.created_at)}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
