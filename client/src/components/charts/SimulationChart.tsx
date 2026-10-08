import {
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip as ChartTooltip,
  Filler,
} from "chart.js";
import { Line } from "react-chartjs-2";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  ChartTooltip,
  Legend,
  Filler
);

export interface SimPoint {
  hours_from_now: number;
  elapsed_hours: number;
  radius_nm: number;
  area_sqnm: number;
}

interface SimulationChartProps {
  data: SimPoint[];
  metric?: "radius_nm" | "area_sqnm";
}

export function SimulationChart({ data, metric = "radius_nm" }: SimulationChartProps) {
  const label = metric === "radius_nm" ? "Search radius (nm)" : "Search area (nm²)";
  return (
    <Line
      data={{
        labels: data.map((d) => `+${d.hours_from_now}h`),
        datasets: [
          {
            label,
            data: data.map((d) => d[metric]),
            borderColor: "#1d4ed8",
            backgroundColor: "rgba(29, 78, 216, 0.12)",
            fill: true,
            tension: 0.35,
            pointBackgroundColor: "#0f2a4a",
            pointRadius: 3,
          },
        ],
      }}
      options={{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => `${(ctx.parsed.y ?? 0).toLocaleString()} ${metric === "radius_nm" ? "nm" : "nm²"}`,
            },
          },
        },
        scales: {
          y: { beginAtZero: true, grid: { color: "rgba(148,163,184,0.2)" } },
          x: { grid: { display: false } },
        },
      }}
    />
  );
}
