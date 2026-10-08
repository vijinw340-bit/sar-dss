import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge Tailwind class names safely. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Format a number to a fixed decimal place. */
export function fmt(n: number | null | undefined, digits = 1): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return n.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

/** Format an ISO datetime to a readable local string. */
export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Elapsed hours between now and an ISO timestamp. */
export function elapsedHours(iso: string | null | undefined): number {
  if (!iso) return 0;
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return 0;
  return Math.max(0, (Date.now() - t) / 3_600_000);
}

/** Format elapsed hours as "Xh Ym". */
export function fmtElapsed(hours: number): string {
  const h = Math.floor(hours);
  const m = Math.round((hours - h) * 60);
  if (h === 0) return `${m}m`;
  return `${h}h ${m.toString().padStart(2, "0")}m`;
}

/** Map a risk score to a tone color class. */
export function riskTone(score: number): {
  label: string;
  text: string;
  bg: string;
  bar: string;
} {
  if (score >= 75)
    return { label: "CRITICAL", text: "text-red-600 dark:text-red-400", bg: "bg-red-100 dark:bg-red-900/30", bar: "bg-red-500" };
  if (score >= 50)
    return { label: "HIGH", text: "text-orange-600 dark:text-orange-400", bg: "bg-orange-100 dark:bg-orange-900/30", bar: "bg-orange-500" };
  if (score >= 30)
    return { label: "MODERATE", text: "text-yellow-600 dark:text-yellow-400", bg: "bg-yellow-100 dark:bg-yellow-900/30", bar: "bg-yellow-500" };
  return { label: "LOW", text: "text-green-600 dark:text-green-400", bg: "bg-green-100 dark:bg-green-900/30", bar: "bg-green-500" };
}

export const statusStyles: Record<string, { dot: string; label: string }> = {
  active: { dot: "bg-emerald-500", label: "Active" },
  paused: { dot: "bg-amber-500", label: "Paused" },
  completed: { dot: "bg-blue-500", label: "Completed" },
  cancelled: { dot: "bg-slate-400", label: "Cancelled" },
  draft: { dot: "bg-slate-300", label: "Draft" },
};

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
