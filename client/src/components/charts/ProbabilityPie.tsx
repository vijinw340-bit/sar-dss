import { Doughnut } from "react-chartjs-2";
import {
  ArcElement,
  Chart as ChartJS,
  Legend,
  Tooltip as ChartTooltip,
} from "chart.js";

ChartJS.register(ArcElement, ChartTooltip, Legend);

interface ProbabilityPieProps {
  high: number;
  medium: number;
  low: number;
}

export function ProbabilityPie({ high, medium, low }: ProbabilityPieProps) {
  return (
    <Doughnut
      data={{
        labels: ["High", "Medium", "Low"],
        datasets: [
          {
            data: [high, medium, low],
            backgroundColor: ["#ef4444", "#f97316", "#eab308"],
            borderWidth: 2,
            borderColor: "rgba(255,255,255,0.9)",
          },
        ],
      }}
      options={{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "bottom", labels: { boxWidth: 12, font: { size: 11 } } },
        },
        cutout: "62%",
      }}
    />
  );
}
