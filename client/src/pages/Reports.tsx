import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Download, FileText, Loader2, Mail, RefreshCw } from "lucide-react";
import { apiError, apiGet, apiPost } from "@/lib/api";
import type { MissionListItem, Report } from "@/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { fmt, fmtDate, statusStyles } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

export function Reports() {
  const [missions, setMissions] = useState<MissionListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [reports, setReports] = useState<Array<{ mission: MissionListItem; report: Report }>>([]);
  const [emailTarget, setEmailTarget] = useState<{ missionId: number; reportId: number } | null>(null);
  const [emailTo, setEmailTo] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const ms = await apiGet<MissionListItem[]>("/missions");
      setMissions(ms);
      // Collect recent reports from the 6 most recent missions
      const collected: Array<{ mission: MissionListItem; report: Report }> = [];
      for (const m of ms.slice(0, 6)) {
        try {
          const rs = await apiGet<Report[]>(`/missions/${m.id}/reports`);
          rs.forEach((r) => collected.push({ mission: m, report: r }));
        } catch {
          /* skip */
        }
      }
      setReports(collected.slice(0, 12));
      setError("");
    } catch (e) {
      setError(apiError(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const generate = async (id: number) => {
    setBusyId(id);
    try {
      await apiPost(`/missions/${id}/reports`);
      await load();
    } catch (e) {
      setError(apiError(e));
    } finally {
      setBusyId(null);
    }
  };

  const sendEmail = async () => {
    if (!emailTarget || !emailTo) return;
    try {
      await apiPost(`/missions/${emailTarget.missionId}/reports/${emailTarget.reportId}/email?to=${encodeURIComponent(emailTo)}`);
      setEmailTarget(null);
      setEmailTo("");
    } catch (e) {
      setError(apiError(e));
    }
  };

  const downloadUrl = (reportId: number) =>
    `${import.meta.env.VITE_API_URL || "/api/v1"}/missions/reports/${reportId}/download`;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-navy-900 dark:text-white">Reports &amp; Documents</h2>
          <p className="text-sm text-muted-foreground">Generate professional PDF analysis reports for any mission</p>
        </div>
        <Button variant="outline" size="sm" onClick={load}>
          <RefreshCw className="mr-1 h-4 w-4" /> Refresh
        </Button>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">{error}</div>
      )}

      <Card className="glass">
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Generate Reports</CardTitle>
          <CardDescription>Each report includes mission details, map, search parameters, probability, pattern, weather and sectors</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Mission</TableHead>
                <TableHead className="hidden md:table-cell">Aircraft</TableHead>
                <TableHead className="hidden lg:table-cell">Radius</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={5} className="py-8 text-center text-muted-foreground">Loading…</TableCell>
                </TableRow>
              ) : (
                missions.map((m) => (
                  <TableRow key={m.id}>
                    <TableCell>
                      <Link to={`/missions/${m.id}`} className="font-medium hover:text-primary">{m.mission_name}</Link>
                      <span className="block text-xs text-muted-foreground">{fmtDate(m.last_contact_time)}</span>
                    </TableCell>
                    <TableCell className="hidden md:table-cell">{m.aircraft_name ?? "—"}</TableCell>
                    <TableCell className="hidden lg:table-cell">{fmt(m.search_radius_nm)} nm</TableCell>
                    <TableCell>
                      <Badge variant="secondary" className="gap-1.5">
                        <span className={`h-1.5 w-1.5 rounded-full ${statusStyles[m.status]?.dot}`} />
                        {statusStyles[m.status]?.label}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button size="sm" variant="outline" onClick={() => generate(m.id)} disabled={busyId === m.id}>
                        {busyId === m.id ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <FileText className="mr-1 h-3.5 w-3.5" />}
                        Generate PDF
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card className="glass">
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Recent Reports</CardTitle>
        </CardHeader>
        <CardContent>
          {reports.length === 0 && !loading ? (
            <p className="py-4 text-sm text-muted-foreground">No reports generated yet.</p>
          ) : (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {reports.map(({ mission, report }) => (
                <div key={report.id} className="flex items-center justify-between rounded-lg border p-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{report.title}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {mission.mission_name} · {fmtDate(report.created_at)}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-1.5">
                    <Button size="icon" variant="ghost" asChild title="Download">
                      <a href={downloadUrl(report.id)} target="_blank" rel="noreferrer">
                        <Download className="h-4 w-4" />
                      </a>
                    </Button>
                    <Button size="icon" variant="ghost" title="Email" onClick={() => setEmailTarget({ missionId: mission.id, reportId: report.id })}>
                      <Mail className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={!!emailTarget} onOpenChange={(o) => !o && setEmailTarget(null)}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Email report</DialogTitle>
            <DialogDescription>Send this PDF to a recipient (SMTP required).</DialogDescription>
          </DialogHeader>
          <input
            value={emailTo}
            onChange={(e) => setEmailTo(e.target.value)}
            placeholder="officer@aai.gov.in"
            className="h-9 w-full rounded-md border bg-transparent px-3 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setEmailTarget(null)}>Cancel</Button>
            <Button onClick={sendEmail} disabled={!emailTo}>Send</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
