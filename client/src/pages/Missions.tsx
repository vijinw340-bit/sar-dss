import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { Download, Plus, RefreshCw, Search, X } from "lucide-react";
import { apiGet, apiError } from "@/lib/api";
import { downloadBlob, fmt, fmtDate, fmtElapsed, riskTone, statusStyles } from "@/lib/utils";
import type { MissionListItem } from "@/types";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export function Missions() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [missions, setMissions] = useState<MissionListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const search = searchParams.get("search") ?? "";
  const status = searchParams.get("status") ?? "";

  const load = async () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (search) params.set("search", search);
    if (status) params.set("status", status);
    try {
      const data = await apiGet<MissionListItem[]>(`/missions?${params.toString()}`);
      setMissions(data);
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
  }, [searchParams]);

  const exportCsv = async () => {
    const res = await apiGet<Blob>(`/missions/export/csv`, { responseType: "blob" });
    downloadBlob(res, `missions_${new Date().toISOString().slice(0, 10)}.csv`);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-navy-900 dark:text-white">Mission Management</h2>
          <p className="text-sm text-muted-foreground">
            {missions.length} mission{missions.length !== 1 ? "s" : ""} · click a row to open the GIS workspace
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={exportCsv}>
            <Download className="mr-1 h-4 w-4" /> CSV
          </Button>
          <Button size="sm" asChild>
            <Link to="/missions/new">
              <Plus className="mr-1 h-4 w-4" /> New Mission
            </Link>
          </Button>
        </div>
      </div>

      {/* Filters */}
      <Card className="glass p-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative min-w-52 flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              placeholder="Search by name, flight no., registration…"
              className="pl-9"
              onChange={(e) => {
                const p = new URLSearchParams(searchParams);
                if (e.target.value) p.set("search", e.target.value);
                else p.delete("search");
                setSearchParams(p);
              }}
            />
          </div>
          <Select
            value={status || "all"}
            onValueChange={(v) => {
              const p = new URLSearchParams(searchParams);
              if (v !== "all") p.set("status", v);
              else p.delete("status");
              setSearchParams(p);
            }}
          >
            <SelectTrigger className="w-40">
              <SelectValue placeholder="All statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              <SelectItem value="active">Active</SelectItem>
              <SelectItem value="paused">Paused</SelectItem>
              <SelectItem value="completed">Completed</SelectItem>
              <SelectItem value="cancelled">Cancelled</SelectItem>
              <SelectItem value="draft">Draft</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="ghost" size="icon" onClick={load} title="Refresh">
            <RefreshCw className="h-4 w-4" />
          </Button>
          {(search || status) && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setSearchParams(new URLSearchParams())}
            >
              <X className="mr-1 h-3.5 w-3.5" /> Clear
            </Button>
          )}
        </div>
      </Card>

      {error && (
        <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">{error}</div>
      )}

      {/* Table */}
      <Card className="glass overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Priority</TableHead>
              <TableHead>Mission</TableHead>
              <TableHead>Flight</TableHead>
              <TableHead className="hidden md:table-cell">Last Contact</TableHead>
              <TableHead className="hidden lg:table-cell">Radius</TableHead>
              <TableHead className="hidden lg:table-cell">Area</TableHead>
              <TableHead>Risk</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={8} className="py-10 text-center text-muted-foreground">Loading missions…</TableCell>
              </TableRow>
            ) : missions.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} className="py-10 text-center text-muted-foreground">
                  No missions found. <Link className="text-primary hover:underline" to="/missions/new">Create one</Link>
                </TableCell>
              </TableRow>
            ) : (
              missions.map((m, i) => {
                const tone = riskTone(m.risk_score);
                return (
                  <TableRow key={m.id} className="cursor-pointer">
                    <TableCell>
                      <span className="text-sm font-bold text-muted-foreground">#{m.priority_rank || i + 1}</span>
                    </TableCell>
                    <TableCell>
                      <Link to={`/missions/${m.id}`} className="block">
                        <span className="font-medium hover:text-primary">{m.mission_name}</span>
                        {m.aircraft_name && (
                          <span className="block text-xs text-muted-foreground">{m.aircraft_name}</span>
                        )}
                      </Link>
                    </TableCell>
                    <TableCell className="text-sm">
                      {m.flight_number ?? "—"}
                      <span className="block text-xs text-muted-foreground">{m.registration_number ?? ""}</span>
                    </TableCell>
                    <TableCell className="hidden text-sm text-muted-foreground md:table-cell">
                      <span className="block">{fmtElapsed(m.elapsed_hours)} ago</span>
                      <span className="text-xs">{fmtDate(m.last_contact_time)}</span>
                    </TableCell>
                    <TableCell className="hidden lg:table-cell">{fmt(m.search_radius_nm)} nm</TableCell>
                    <TableCell className="hidden lg:table-cell">{fmt(m.search_area_sqnm, 0)} nm²</TableCell>
                    <TableCell>
                      <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: i * 0.02 }}
                      >
                        <Badge variant="outline" className={`${tone.bg} ${tone.text} border-0`}>
                          {tone.label} · {Math.round(m.risk_score)}
                        </Badge>
                      </motion.div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary" className="gap-1.5">
                        <span className={`h-1.5 w-1.5 rounded-full ${statusStyles[m.status]?.dot}`} />
                        {statusStyles[m.status]?.label}
                      </Badge>
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}
