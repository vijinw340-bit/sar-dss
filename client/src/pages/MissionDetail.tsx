import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  ArrowLeft,
  Calculator,
  CheckCircle2,
  Download,
  FileText,
  Grid3x3,
  Loader2,
  Mail,
  MapPin,
  Pause,
  Plane,
  Play,
  Radar,
  RefreshCw,
  Ruler,
  Trash2,
  Wind,
} from "lucide-react";
import { apiDelete, apiError, apiGet, apiPatch, apiPost } from "@/lib/api";
import { downloadBlob, fmt, fmtDate, fmtElapsed, riskTone, statusStyles } from "@/lib/utils";
import type {
  ActivityItem,
  Analysis,
  Mission,
  Report,
  SectorDetail,
} from "@/types";
import { MissionMap, type SectorDisplay, type ZoneDisplay } from "@/components/map/MissionMap";
import { geoToLatLng } from "@/components/map/airports";
import { ProbabilityPie } from "@/components/charts/ProbabilityPie";
import { SimulationChart } from "@/components/charts/SimulationChart";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useAuth } from "@/context/AuthContext";

const PATTERN_LABELS: Record<string, string> = {
  expanding_square: "Expanding Square",
  sector: "Sector Search",
  parallel_track: "Parallel Track",
  creeping_line: "Creeping Line",
  track_line: "Track Line",
};

function MetricCard({
  icon: Icon,
  label,
  value,
  sub,
  delay,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  sub?: string;
  delay: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay }}
    >
      <Card className="glass">
        <CardContent className="p-4">
          <div className="flex items-center gap-2 text-muted-foreground">
            <Icon className="h-4 w-4" />
            <span className="text-xs font-medium uppercase tracking-wide">{label}</span>
          </div>
          <p className="mt-2 text-2xl font-bold text-navy-900 dark:text-white">{value}</p>
          {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
        </CardContent>
      </Card>
    </motion.div>
  );
}

export function MissionDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [mission, setMission] = useState<Mission | null>(null);
  const [sectors, setSectors] = useState<SectorDetail[]>([]);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [reports, setReports] = useState<Report[]>([]);
  const [selectedPattern, setSelectedPattern] = useState<string>("");
  const [showZones, setShowZones] = useState(true);
  const [showSectors, setShowSectors] = useState(true);
  const [showGrid, setShowGrid] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [emailTo, setEmailTo] = useState("");
  const [emailReport, setEmailReport] = useState<Report | null>(null);
  const [toast, setToast] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const m = await apiGet<Mission>(`/missions/${id}`);
      setMission(m);
      setSelectedPattern(m.patterns?.find((p) => p.recommended)?.pattern_type ?? m.patterns?.[0]?.pattern_type ?? "");
      const secs = await apiGet<SectorDetail[]>(`/missions/${id}/sectors`);
      setSectors(secs);
      const a = await apiGet<Analysis>(`/missions/${id}/analysis`);
      setAnalysis(a);
      const r = await apiGet<Report[]>(`/missions/${id}/reports`);
      setReports(r);
      setError("");
    } catch (e) {
      setError(apiError(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const recalculate = async () => {
    setBusy(true);
    try {
      const m = await apiPost<Mission>(`/missions/${id}/calculate`);
      setMission(m);
      setSelectedPattern(m.patterns?.find((p) => p.recommended)?.pattern_type ?? "");
      setToast("Search area recalculated.");
    } catch (e) {
      setError(apiError(e));
    } finally {
      setBusy(false);
    }
  };

  const setStatus = async (status: string) => {
    const m = await apiPatch<Mission>(`/missions/${id}`, { status });
    setMission(m);
    setToast(`Mission ${status}.`);
  };

  const generateReport = async () => {
    setBusy(true);
    try {
      const r = await apiPost<Report>(`/missions/${id}/reports`);
      setReports((prev) => [r, ...prev]);
      setToast("Report generated.");
    } catch (e) {
      setError(apiError(e));
    } finally {
      setBusy(false);
    }
  };

  const exportCsv = async () => {
    const blob = await apiGet<Blob>(`/missions/${id}/export/csv`, { responseType: "blob" });
    downloadBlob(blob, `mission_${id}.csv`);
  };

  const assignAircraft = async (sectorId: number, value: string) => {
    await apiPatch(`/missions/sectors/${sectorId}`, { assigned_aircraft: value });
    setSectors((prev) => prev.map((s) => (s.id === sectorId ? { ...s, assigned_aircraft: value } : s)));
    setToast("Sector assignment updated.");
  };

  const removeMission = async () => {
    await apiDelete(`/missions/${id}`);
    navigate("/missions");
  };

  const sendEmail = async () => {
    if (!emailReport || !emailTo) return;
    try {
      await apiPost(`/missions/${id}/reports/${emailReport.id}/email?to=${encodeURIComponent(emailTo)}`);
      setToast("Report emailed.");
      setEmailReport(null);
      setEmailTo("");
    } catch (e) {
      setError(apiError(e));
    }
  };

  const zones: ZoneDisplay[] = useMemo(() => {
    if (!mission?.zones?.length) return [];
    return mission.zones.map((z) => ({
      color: z.color,
      level: z.zone_level,
      probabilityPct: z.probability_pct,
      polygon: geoToLatLng((JSON.parse(z.polygon_geojson) as { coordinates: number[][][] }).coordinates[0]),
    }));
  }, [mission]);

  const sectorDisplays: SectorDisplay[] = useMemo(
    () =>
      sectors.map((s) => ({
        color: s.color,
        name: s.name,
        polygon: geoToLatLng((JSON.parse(s.polygon_geojson) as { coordinates: number[][][] }).coordinates[0]),
      })),
    [sectors]
  );

  const searchPolygon = useMemo(() => {
    if (!mission?.search_area) return undefined;
    const poly = JSON.parse(mission.search_area.polygon_geojson) as { coordinates: number[][][] };
    return geoToLatLng(poly.coordinates[0]);
  }, [mission?.search_area]);

  const patternWaypoints = useMemo(() => {
    const pat = mission?.patterns?.find((p) => p.pattern_type === selectedPattern);
    if (!pat) return undefined;
    const wp = JSON.parse(pat.waypoints_geojson) as { coordinates: number[][] };
    return geoToLatLng(wp.coordinates);
  }, [mission, selectedPattern]);

  const currentPattern = mission?.patterns?.find((p) => p.pattern_type === selectedPattern);
  const tone = riskTone(mission?.risk_score ?? 0);

  if (loading && !mission) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-72" />
        <Skeleton className="h-[420px] w-full rounded-xl" />
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {[...Array(4)].map((_, i) => (
            <Skeleton key={i} className="h-24 rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  if (!mission) {
    return <p className="py-16 text-center text-muted-foreground">{error || "Mission not found"}</p>;
  }

  return (
    <div className="space-y-6">
      {toast && (
        <div className="flex items-center gap-2 rounded-lg border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300">
          <CheckCircle2 className="h-4 w-4" /> {toast}
          <button onClick={() => setToast("")} className="ml-auto text-xs underline">dismiss</button>
        </div>
      )}
      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertTriangle className="h-4 w-4" /> {error}
          <button onClick={() => setError("")} className="ml-auto text-xs underline">dismiss</button>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link to="/missions" className="mb-2 flex items-center gap-1 text-xs text-muted-foreground hover:text-primary">
            <ArrowLeft className="h-3.5 w-3.5" /> Back to missions
          </Link>
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-xl font-bold text-navy-900 dark:text-white">{mission.mission_name}</h2>
            <Badge variant="secondary" className="gap-1.5">
              <span className={`h-1.5 w-1.5 rounded-full ${statusStyles[mission.status]?.dot}`} />
              {statusStyles[mission.status]?.label}
            </Badge>
            <Badge variant="outline" className={`${tone.bg} ${tone.text} border-0`}>{tone.label}</Badge>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Flight {mission.flight_number ?? "—"} · {mission.aircraft_name ?? "Aircraft"} ·{" "}
            {mission.registration_number ?? ""} · Created {fmtDate(mission.created_at)}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" size="sm" onClick={recalculate} disabled={busy}>
            {busy ? <Loader2 className="animate-spin" /> : <RefreshCw />} Recalculate
          </Button>
          <Button variant="outline" size="sm" onClick={exportCsv}>
            <Download /> CSV
          </Button>
          <Button variant="outline" size="sm" onClick={generateReport} disabled={busy}>
            <FileText /> Report
          </Button>
          {mission.status === "active" && (
            <Button variant="secondary" size="sm" onClick={() => setStatus("paused")}>
              <Pause /> Pause
            </Button>
          )}
          {mission.status === "paused" && (
            <Button variant="secondary" size="sm" onClick={() => setStatus("active")}>
              <Play /> Resume
            </Button>
          )}
          {mission.status !== "completed" && (
            <Button variant="default" size="sm" onClick={() => setStatus("completed")}>
              <CheckCircle2 /> Complete
            </Button>
          )}
          {user?.role === "admin" && (
            <Button variant="destructive" size="sm" onClick={() => setConfirmDelete(true)}>
              <Trash2 />
            </Button>
          )}
        </div>
      </div>

      {/* Map + metrics */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <Card className="glass xl:col-span-2">
          <CardHeader className="pb-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <CardTitle className="text-base">Search Area GIS Workspace</CardTitle>
                <CardDescription>LKP · radius · probability · pattern · sectors</CardDescription>
              </div>
              <div className="flex flex-wrap items-center gap-1.5">
                <Button size="sm" variant={showZones ? "default" : "outline"} onClick={() => setShowZones(!showZones)}>
                  <Radar className="mr-1 h-3.5 w-3.5" /> Zones
                </Button>
                <Button size="sm" variant={showSectors ? "default" : "outline"} onClick={() => setShowSectors(!showSectors)}>
                  <Grid3x3 className="mr-1 h-3.5 w-3.5" /> Sectors
                </Button>
                <Button size="sm" variant={showGrid ? "default" : "outline"} onClick={() => setShowGrid(!showGrid)}>
                  Grid
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-3 pt-0">
            <div className="h-[440px] w-full overflow-hidden rounded-xl">
              <MissionMap
                center={[mission.lkp_latitude, mission.lkp_longitude]}
                radiusNm={mission.search_radius_nm}
                searchPolygon={searchPolygon}
                zones={zones}
                sectors={sectorDisplays}
                patternWaypoints={patternWaypoints}
                predicted={
                  mission.predicted_latitude && mission.predicted_longitude
                    ? [mission.predicted_latitude, mission.predicted_longitude]
                    : null
                }
                heading={mission.heading_deg}
                showZones={showZones}
                showSectors={showSectors}
                showGrid={showGrid}
                showNearbyAirports
                missionName={mission.mission_name}
                flightNumber={mission.flight_number ?? undefined}
                aircraftName={mission.aircraft_name ?? undefined}
                height="100%"
              />
            </div>

            {/* Legend */}
            <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
              <span className="flex items-center gap-1.5">
                <span className="h-3 w-3 rounded-full bg-red-500" /> High prob
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-3 w-3 rounded-full bg-orange-500" /> Medium prob
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-3 w-3 rounded-full bg-yellow-500" /> Low prob
              </span>
              <span className="flex items-center gap-1.5">
                <span className="inline-block h-3 w-3 border-2 border-dashed border-blue-600" /> Radius
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-0.5 w-6 bg-orange-500" /> Pattern
              </span>
              <span className="flex items-center gap-1.5">
                <MapPin className="h-3 w-3 text-red-600" /> LKP
              </span>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-3">
            <MetricCard icon={Ruler} label="Search Radius" value={`${fmt(mission.search_radius_nm)} nm`} delay={0} />
            <MetricCard icon={Plane} label="Search Area" value={`${fmt(mission.search_area_sqnm, 0)} nm²`} delay={0.05} />
            <MetricCard icon={Calculator} label="Distance" value={`${fmt(mission.distance_nm)} nm`} sub={`${fmt(mission.ground_speed_kts, 0)} kt`} delay={0.1} />
            <MetricCard icon={RefreshCw} label="Elapsed" value={fmtElapsed(mission.elapsed_hours)} delay={0.15} />
            <MetricCard icon={AlertTriangle} label="Uncertainty" value={`${fmt(mission.uncertainty_nm)} nm`} delay={0.2} />
            <MetricCard icon={Wind} label="Wind" value={`${fmt(mission.wind_speed_kts)} kt`} sub={`${fmt(mission.wind_direction_deg, 0)}°`} delay={0.25} />
          </div>

          <Card className="glass">
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Desired Coverage</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold text-navy-900 dark:text-white">{fmt(mission.desired_coverage_pct)}%</p>
              <Progress value={Math.min(100, mission.desired_coverage_pct)} className="mt-3" />
              <p className="mt-2 text-xs text-muted-foreground">
                Sweepable area per sortie given track spacing of{" "}
                {fmt(mission.search_area?.track_spacing_nm ?? 2)} nm.
              </p>
            </CardContent>
          </Card>

          <Card className="glass">
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Probability Distribution</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-48">
                <ProbabilityPie
                  high={zones[0]?.probabilityPct ?? mission.zones?.find((z) => z.zone_level === "high")?.probability_pct ?? 0}
                  medium={zones[1]?.probabilityPct ?? mission.zones?.find((z) => z.zone_level === "medium")?.probability_pct ?? 0}
                  low={zones[2]?.probabilityPct ?? mission.zones?.find((z) => z.zone_level === "low")?.probability_pct ?? 0}
                />
              </div>
            </CardContent>
          </Card>

          <Card className="glass">
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Pattern Selector</CardTitle>
              <CardDescription>Choose which pattern to render</CardDescription>
            </CardHeader>
            <CardContent>
              <Select value={selectedPattern} onValueChange={setSelectedPattern}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {mission.patterns?.map((p) => (
                    <SelectItem key={p.pattern_type} value={p.pattern_type}>
                      {PATTERN_LABELS[p.pattern_type] ?? p.pattern_type} {p.recommended ? "★" : ""}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {currentPattern?.recommended && (
                <p className="mt-3 rounded-lg bg-primary/10 p-3 text-xs text-primary">{currentPattern.reason}</p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Tabs */}
      <Card className="glass">
        <CardContent className="p-4">
          <Tabs defaultValue="overview">
            <TabsList className="mb-4 flex-wrap h-auto">
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="sectors">Sectors</TabsTrigger>
              <TabsTrigger value="analysis">AI Analysis</TabsTrigger>
              <TabsTrigger value="simulation">Simulation</TabsTrigger>
              <TabsTrigger value="timeline">Timeline</TabsTrigger>
              <TabsTrigger value="reports">Reports</TabsTrigger>
            </TabsList>

            <TabsContent value="overview">
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                <div>
                  <h4 className="mb-3 text-sm font-semibold text-navy-900 dark:text-white">Flight Details</h4>
                  <Table>
                    <TableBody>
                      <TableRow><TableCell className="text-muted-foreground">Pilot</TableCell><TableCell className="font-medium">{mission.pilot_name ?? "—"}</TableCell></TableRow>
                      <TableRow><TableCell className="text-muted-foreground">Departure</TableCell><TableCell>{mission.departure_airport ?? "—"}</TableCell></TableRow>
                      <TableRow><TableCell className="text-muted-foreground">Destination</TableCell><TableCell>{mission.destination_airport ?? "—"}</TableCell></TableRow>
                      <TableRow><TableCell className="text-muted-foreground">Aircraft Type</TableCell><TableCell>{mission.aircraft_type ?? "—"}</TableCell></TableRow>
                      <TableRow><TableCell className="text-muted-foreground">Altitude</TableCell><TableCell>{fmt(mission.altitude_ft, 0)} ft</TableCell></TableRow>
                      <TableRow><TableCell className="text-muted-foreground">Fuel Remaining</TableCell><TableCell>{fmt(mission.fuel_remaining_hours)} h</TableCell></TableRow>
                      <TableRow><TableCell className="text-muted-foreground">Heading</TableCell><TableCell>{fmt(mission.heading_deg, 0)}°</TableCell></TableRow>
                    </TableBody>
                  </Table>
                </div>
                <div>
                  <h4 className="mb-3 text-sm font-semibold text-navy-900 dark:text-white">Position &amp; Environment</h4>
                  <Table>
                    <TableBody>
                      <TableRow><TableCell className="text-muted-foreground">LKP</TableCell><TableCell className="font-mono">{mission.lkp_latitude.toFixed(5)}, {mission.lkp_longitude.toFixed(5)}</TableCell></TableRow>
                      <TableRow><TableCell className="text-muted-foreground">Predicted</TableCell><TableCell className="font-mono">{mission.predicted_latitude ? `${mission.predicted_latitude.toFixed(5)}, ${mission.predicted_longitude?.toFixed(5)}` : "—"}</TableCell></TableRow>
                      <TableRow><TableCell className="text-muted-foreground">Weather</TableCell><TableCell>{mission.weather_conditions}</TableCell></TableRow>
                      <TableRow><TableCell className="text-muted-foreground">Visibility</TableCell><TableCell>{fmt(mission.visibility_nm)} nm</TableCell></TableRow>
                      <TableRow><TableCell className="text-muted-foreground">Weather Impact</TableCell><TableCell>{fmt(mission.weather_impact * 100, 0)}%</TableCell></TableRow>
                      <TableRow><TableCell className="text-muted-foreground">LKP Accuracy</TableCell><TableCell className="uppercase">{mission.lkp_accuracy}</TableCell></TableRow>
                      <TableRow><TableCell className="text-muted-foreground">Route Known</TableCell><TableCell>{mission.is_route_known ? "Yes" : "No"}</TableCell></TableRow>
                    </TableBody>
                  </Table>
                  {mission.remarks && (
                    <div className="mt-4 rounded-lg bg-muted/50 p-3 text-sm">
                      <p className="mb-1 text-xs font-semibold uppercase text-muted-foreground">Remarks</p>
                      {mission.remarks}
                    </div>
                  )}
                </div>
              </div>
            </TabsContent>

            <TabsContent value="sectors">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Sector</TableHead>
                    <TableHead>Angles</TableHead>
                    <TableHead className="hidden md:table-cell">Area (nm²)</TableHead>
                    <TableHead>Assigned Aircraft</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sectors.map((s) => (
                    <TableRow key={s.id}>
                      <TableCell>
                        <span className="flex items-center gap-2 font-semibold">
                          <span className="inline-block h-3 w-3 rounded-sm" style={{ backgroundColor: s.color }} />
                          {s.name}
                        </span>
                      </TableCell>
                      <TableCell className="text-sm">{Math.round(s.start_angle_deg)}° – {Math.round(s.end_angle_deg)}°</TableCell>
                      <TableCell className="hidden md:table-cell">{fmt(s.area_sqnm)}</TableCell>
                      <TableCell>
                        <Select
                          value={s.assigned_aircraft ?? "unassigned"}
                          onValueChange={(v) => assignAircraft(s.id, v === "unassigned" ? "" : v)}
                        >
                          <SelectTrigger className="h-8 w-56">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="unassigned">Unassigned</SelectItem>
                            {["ALH Dhruv", "Dornier 228", "HAL Chetak", "C-130J", "Beech King Air B350", "Search Helo-1", "Search Helo-2"].map((a) => (
                              <SelectItem key={a} value={a}>{a}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TabsContent>

            <TabsContent value="analysis">
              {analysis ? (
                <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                  <div>
                    <div className="flex items-center justify-between">
                      <h4 className="text-sm font-semibold text-navy-900 dark:text-white">Risk Analysis</h4>
                      <Badge className={`${tone.bg} ${tone.text} border-0`}>{analysis.risk.rating} · {Math.round(analysis.risk.score)}/100</Badge>
                    </div>
                    <p className="mt-2 text-sm text-muted-foreground">{analysis.risk.summary}</p>
                    <div className="mt-4 space-y-3">
                      {analysis.risk.factors.map((f) => (
                        <div key={f.name}>
                          <div className="flex justify-between text-xs">
                            <span className="font-medium">{f.name}</span>
                            <span className="text-muted-foreground">{f.value}/{f.max} · {f.severity}</span>
                          </div>
                          <Progress value={(f.value / f.max) * 100} className="mt-1" />
                        </div>
                      ))}
                    </div>
                  </div>
                  <div>
                    <h4 className="mb-3 text-sm font-semibold text-navy-900 dark:text-white">
                      Crash Location Prediction &amp; Weather Impact
                    </h4>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="rounded-lg bg-muted/50 p-3">
                        <p className="text-xs text-muted-foreground">Predicted crash</p>
                        <p className="mt-1 font-mono text-sm">{analysis.crash_prediction.latitude ? `${analysis.crash_prediction.latitude.toFixed(4)}, ${analysis.crash_prediction.longitude?.toFixed(4)}` : "—"}</p>
                        <p className="text-xs text-muted-foreground">Confidence ± {analysis.crash_prediction.confidence_nm} nm</p>
                      </div>
                      <div className="rounded-lg bg-muted/50 p-3">
                        <p className="text-xs text-muted-foreground">Terrain roughness</p>
                        <p className="mt-1 text-sm font-semibold">{Math.round(analysis.terrain_roughness * 100)}%</p>
                      </div>
                      <div className="rounded-lg bg-muted/50 p-3">
                        <p className="text-xs text-muted-foreground">Weather trend</p>
                        <p className="mt-1 text-sm font-semibold capitalize">{analysis.weather_impact.trend}</p>
                        <p className="text-xs text-muted-foreground">{analysis.weather_impact.severity}</p>
                      </div>
                      <div className="rounded-lg bg-muted/50 p-3">
                        <p className="text-xs text-muted-foreground">Track spacing rec.</p>
                        <p className="mt-1 text-sm font-semibold">{analysis.weather_impact.track_spacing_recommendation_nm} nm</p>
                      </div>
                    </div>
                    <h4 className="mb-2 mt-5 text-sm font-semibold text-navy-900 dark:text-white">Smart Recommendations</h4>
                    <div className="space-y-2">
                      {analysis.recommendations.map((r, i) => (
                        <div key={i} className="flex gap-2 rounded-lg border p-3 text-sm">
                          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
                          <div>
                            <p className="font-medium">{r.title}</p>
                            <p className="text-xs text-muted-foreground">{r.detail}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <Skeleton className="h-64 w-full rounded-xl" />
              )}
            </TabsContent>

            <TabsContent value="simulation">
              {analysis ? (
                <div className="h-80">
                  <SimulationChart data={analysis.simulation} metric="radius_nm" />
                </div>
              ) : (
                <Skeleton className="h-80 w-full rounded-xl" />
              )}
              <p className="mt-2 text-xs text-muted-foreground">
                Projected growth of the search radius over the next 6 hours if no aircraft is found.
              </p>
            </TabsContent>

            <TabsContent value="timeline">
              <div className="space-y-0">
                {(mission.logs ?? []).length === 0 && (
                  <p className="py-4 text-sm text-muted-foreground">No activity recorded for this mission.</p>
                )}
                {(mission.logs ?? []).map((log: ActivityItem) => (
                  <div key={log.id} className="flex items-start gap-3 border-b py-3 last:border-0">
                    <span className="mt-1 h-2.5 w-2.5 rounded-full bg-primary" />
                    <div>
                      <p className="text-sm font-medium capitalize">{log.action.replace(/_/g, " ")}</p>
                      {log.description && <p className="text-xs text-muted-foreground">{log.description}</p>}
                      <p className="text-[11px] text-muted-foreground/70">{fmtDate(log.created_at)}</p>
                    </div>
                  </div>
                ))}
              </div>
            </TabsContent>

            <TabsContent value="reports">
              <div className="space-y-2">
                {reports.length === 0 && (
                  <p className="py-4 text-sm text-muted-foreground">No reports yet. Click "Report" in the header.</p>
                )}
                {reports.map((r) => (
                  <div key={r.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border p-3">
                    <div>
                      <p className="text-sm font-medium">{r.title}</p>
                      <p className="text-xs text-muted-foreground">PDF · {fmtDate(r.created_at)}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button size="sm" variant="outline" asChild>
                        <a href={`${import.meta.env.VITE_API_URL || "/api/v1"}/missions/reports/${r.id}/download`} target="_blank" rel="noreferrer">
                          <Download className="mr-1 h-3.5 w-3.5" /> Download
                        </a>
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => setEmailReport(r)}>
                        <Mail className="mr-1 h-3.5 w-3.5" /> Email
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      {/* Delete confirm */}
      <Dialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Delete mission?</DialogTitle>
            <DialogDescription>
              This will permanently remove "{mission.mission_name}" and all its search data. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmDelete(false)}>Cancel</Button>
            <Button variant="destructive" onClick={removeMission}>Delete</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Email dialog */}
      <Dialog open={!!emailReport} onOpenChange={(o) => !o && setEmailReport(null)}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Email report</DialogTitle>
            <DialogDescription>Send this PDF report to a recipient (requires SMTP configuration).</DialogDescription>
          </DialogHeader>
          <div className="flex items-center gap-2">
            <Mail className="h-4 w-4 text-muted-foreground" />
            <input
              value={emailTo}
              onChange={(e) => setEmailTo(e.target.value)}
              placeholder="officer@aai.gov.in"
              className="h-9 w-full rounded-md border bg-transparent px-3 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEmailReport(null)}>Cancel</Button>
            <Button onClick={sendEmail} disabled={!emailTo}>Send</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
