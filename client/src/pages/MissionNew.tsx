import { useNavigate } from "react-router-dom";
import { MissionForm } from "@/components/mission/MissionForm";
import { apiPost } from "@/lib/api";
import type { Mission, MissionCreatePayload } from "@/types";

export function MissionNew() {
  const navigate = useNavigate();

  const onSubmit = async (payload: MissionCreatePayload) => {
    const mission = await apiPost<Mission>("/missions", payload);
    navigate(`/missions/${mission.id}`);
  };

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h2 className="text-xl font-bold text-navy-900 dark:text-white">Create New Mission</h2>
        <p className="text-sm text-muted-foreground">
          Enter the aircraft telemetry and last known position. The system calculates the search area, probability
          zones, patterns and sectors automatically.
        </p>
      </div>
      <MissionForm onSubmit={onSubmit} />
    </div>
  );
}
