import { useState } from "react";
import { Loader2, LocateFixed } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { apiError } from "@/lib/api";
import type { MissionCreatePayload } from "@/types";

interface MissionFormProps {
  onSubmit: (payload: MissionCreatePayload) => Promise<void>;
  submitLabel?: string;
}

function Field({
  label,
  required,
  children,
  className,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={className}>
      <Label className="mb-1.5 block text-xs font-medium text-muted-foreground">
        {label} {required && <span className="text-red-500">*</span>}
      </Label>
      {children}
    </div>
  );
}

const nowIso = () => new Date(Date.now() - 60 * 60 * 1000).toISOString().slice(0, 16);

export function MissionForm({ onSubmit, submitLabel = "Create Mission & Calculate" }: MissionFormProps) {
  const [form, setForm] = useState({
    mission_name: "",
    flight_number: "",
    aircraft_name: "",
    registration_number: "",
    aircraft_type: "",
    pilot_name: "",
    departure_airport: "",
    destination_airport: "",
    lkp_latitude: "",
    lkp_longitude: "",
    altitude_ft: "8000",
    ground_speed_kts: "120",
    heading_deg: "45",
    last_contact_time: nowIso(),
    fuel_remaining_hours: "2.5",
    wind_speed_kts: "12",
    wind_direction_deg: "240",
    weather_conditions: "Clear",
    visibility_nm: "8",
    remarks: "",
    lkp_accuracy: "medium",
    is_route_known: false,
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const set = (key: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    const lat = parseFloat(form.lkp_latitude);
    const lon = parseFloat(form.lkp_longitude);

    if (form.mission_name.trim().length < 3) return setError("Mission name must be at least 3 characters.");
    if (Number.isNaN(lat) || lat < -90 || lat > 90) return setError("Valid LKP latitude (-90 to 90) is required.");
    if (Number.isNaN(lon) || lon < -180 || lon > 180) return setError("Valid LKP longitude (-180 to 180) is required.");
    if (!form.last_contact_time) return setError("Time of last contact is required.");

    setLoading(true);
    try {
      await onSubmit({
        mission_name: form.mission_name.trim(),
        flight_number: form.flight_number.trim() || undefined,
        aircraft_name: form.aircraft_name.trim() || undefined,
        registration_number: form.registration_number.trim() || undefined,
        aircraft_type: form.aircraft_type.trim() || undefined,
        pilot_name: form.pilot_name.trim() || undefined,
        departure_airport: form.departure_airport.trim() || undefined,
        destination_airport: form.destination_airport.trim() || undefined,
        lkp_latitude: lat,
        lkp_longitude: lon,
        altitude_ft: parseFloat(form.altitude_ft) || 0,
        ground_speed_kts: parseFloat(form.ground_speed_kts) || 0,
        heading_deg: parseFloat(form.heading_deg) || 0,
        last_contact_time: new Date(form.last_contact_time).toISOString(),
        fuel_remaining_hours: parseFloat(form.fuel_remaining_hours) || 0,
        wind_speed_kts: parseFloat(form.wind_speed_kts) || 0,
        wind_direction_deg: parseFloat(form.wind_direction_deg) || 0,
        weather_conditions: form.weather_conditions,
        visibility_nm: parseFloat(form.visibility_nm) || 0,
        remarks: form.remarks.trim() || undefined,
        lkp_accuracy: form.lkp_accuracy as MissionCreatePayload["lkp_accuracy"],
        is_route_known: form.is_route_known,
      });
    } catch (err) {
      setError(apiError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <section className="rounded-xl border bg-card p-5">
        <h3 className="mb-4 text-sm font-semibold text-navy-800 dark:text-sky-300">Flight Information</h3>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="Mission Name" required>
            <Input value={form.mission_name} onChange={set("mission_name")} placeholder="AAI Flight SAR-001" />
          </Field>
          <Field label="Flight Number">
            <Input value={form.flight_number} onChange={set("flight_number")} placeholder="AAI-4120" />
          </Field>
          <Field label="Aircraft Name">
            <Input value={form.aircraft_name} onChange={set("aircraft_name")} placeholder="Cessna 172" />
          </Field>
          <Field label="Aircraft Type">
            <Input value={form.aircraft_type} onChange={set("aircraft_type")} placeholder="General Aviation" />
          </Field>
          <Field label="Registration Number">
            <Input value={form.registration_number} onChange={set("registration_number")} placeholder="VT-AAI" />
          </Field>
          <Field label="Pilot Name">
            <Input value={form.pilot_name} onChange={set("pilot_name")} placeholder="Capt. R. Sharma" />
          </Field>
          <Field label="Departure Airport">
            <Input value={form.departure_airport} onChange={set("departure_airport")} placeholder="VIDP" />
          </Field>
          <Field label="Destination Airport">
            <Input value={form.destination_airport} onChange={set("destination_airport")} placeholder="VIDN" />
          </Field>
          <Field label="Time of Last Contact" required>
            <Input
              type="datetime-local"
              value={form.last_contact_time}
              onChange={set("last_contact_time")}
            />
          </Field>
        </div>
      </section>

      <section className="rounded-xl border bg-card p-5">
        <h3 className="mb-4 text-sm font-semibold text-navy-800 dark:text-sky-300">
          Last Known Position &amp; Telemetry
        </h3>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="LKP Latitude (deg)" required>
            <Input value={form.lkp_latitude} onChange={set("lkp_latitude")} placeholder="28.9895" inputMode="decimal" />
          </Field>
          <Field label="LKP Longitude (deg)" required>
            <Input value={form.lkp_longitude} onChange={set("lkp_longitude")} placeholder="77.6748" inputMode="decimal" />
          </Field>
          <Field label="Altitude (ft)">
            <Input value={form.altitude_ft} onChange={set("altitude_ft")} type="number" />
          </Field>
          <Field label="Ground Speed (kts)">
            <Input value={form.ground_speed_kts} onChange={set("ground_speed_kts")} type="number" />
          </Field>
          <Field label="Heading (deg)">
            <Input value={form.heading_deg} onChange={set("heading_deg")} type="number" min={0} max={360} />
          </Field>
          <Field label="Fuel Remaining (hrs)">
            <Input value={form.fuel_remaining_hours} onChange={set("fuel_remaining_hours")} type="number" />
          </Field>
          <Field label="LKP Accuracy">
            <Select
              value={form.lkp_accuracy}
              onValueChange={(v) => setForm((f) => ({ ...f, lkp_accuracy: v }))}
            >
              <SelectTrigger className="h-9">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="high">High</SelectItem>
                <SelectItem value="medium">Medium</SelectItem>
                <SelectItem value="low">Low</SelectItem>
              </SelectContent>
            </Select>
          </Field>
          <div className="flex items-end pb-1">
            <label className="flex items-center gap-2 text-sm">
              <Switch
                checked={form.is_route_known}
                onCheckedChange={(v) => setForm((f) => ({ ...f, is_route_known: v }))}
              />
              Route known
            </label>
          </div>
        </div>
      </section>

      <section className="rounded-xl border bg-card p-5">
        <h3 className="mb-4 text-sm font-semibold text-navy-800 dark:text-sky-300">Environmental Conditions</h3>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Wind Speed (kts)">
            <Input value={form.wind_speed_kts} onChange={set("wind_speed_kts")} type="number" />
          </Field>
          <Field label="Wind Direction (deg)">
            <Input value={form.wind_direction_deg} onChange={set("wind_direction_deg")} type="number" />
          </Field>
          <Field label="Visibility (nm)">
            <Input value={form.visibility_nm} onChange={set("visibility_nm")} type="number" />
          </Field>
          <Field label="Weather">
            <Select
              value={form.weather_conditions}
              onValueChange={(v) => setForm((f) => ({ ...f, weather_conditions: v }))}
            >
              <SelectTrigger className="h-9">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {["Clear", "Partly Cloudy", "Overcast", "Rain", "Thunderstorm", "Heavy Rain", "Fog", "Snow", "Cyclone"].map((w) => (
                  <SelectItem key={w} value={w}>
                    {w}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
        </div>
      </section>

      <section className="rounded-xl border bg-card p-5">
        <h3 className="mb-4 text-sm font-semibold text-navy-800 dark:text-sky-300">Remarks</h3>
        <Field label="Additional Information">
          <Textarea
            value={form.remarks}
            onChange={set("remarks")}
            rows={3}
            placeholder="ATC notes, radar observations, emergency contacts…"
          />
        </Field>
      </section>

      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" size="lg" disabled={loading}>
          {loading ? <Loader2 className="animate-spin" /> : <LocateFixed />}
          {loading ? "Calculating search area…" : submitLabel}
        </Button>
        <p className="text-xs text-muted-foreground">
          All fields are validated. Search radius, area, probability zones and patterns are computed automatically.
        </p>
      </div>
    </form>
  );
}
