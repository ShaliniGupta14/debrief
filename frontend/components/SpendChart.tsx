"use client";

import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TooltipContentProps } from "recharts";
import { apiGet, ApiError } from "@/lib/api-client";
import type { StatsResponse } from "@/lib/types";

const LIGHT_SERIES = ["#2a78d6", "#008300", "#e87ba4", "#eda100"];
const DARK_SERIES = ["#3987e5", "#008300", "#d55181", "#c98500"];

function useIsDark(): boolean {
  const [isDark, setIsDark] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    setIsDark(mq.matches);
    const handler = (e: MediaQueryListEvent) => setIsDark(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);
  return isDark;
}

interface PivotedRow {
  bucket: string;
  [model: string]: string | number;
}

function pivot(stats: StatsResponse): { rows: PivotedRow[]; models: string[] } {
  const byBucket = new Map<string, PivotedRow>();
  const models = new Set<string>();

  for (const b of stats.buckets) {
    const key = b.group_key ?? "unknown";
    models.add(key);
    if (!byBucket.has(b.bucket)) byBucket.set(b.bucket, { bucket: b.bucket });
    byBucket.get(b.bucket)![key] = Number(b.spend_usd);
  }

  const rows = Array.from(byBucket.values()).sort((a, b) => a.bucket.localeCompare(b.bucket));
  return { rows, models: Array.from(models).sort() };
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function ChartTooltip({ active, payload, label }: TooltipContentProps) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded border border-[var(--border)] bg-[var(--surface-1)] px-3 py-2 text-sm shadow-sm">
      <div className="mb-1.5 text-[var(--text-muted)]">{formatDate(String(label))}</div>
      <div className="flex flex-col gap-1">
        {[...payload].reverse().map((entry) => {
          const seriesName = String(entry.dataKey);
          return (
            <div key={seriesName} className="flex items-center gap-2">
              <span className="inline-block h-0.5 w-3" style={{ backgroundColor: entry.color }} />
              <span className="font-medium text-[var(--text-primary)]">
                ${Number(entry.value).toFixed(2)}
              </span>
              <span className="text-[var(--text-secondary)]">{seriesName}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function SpendChart({ apiKey }: { apiKey: string }) {
  const [data, setData] = useState<{ rows: PivotedRow[]; models: string[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const isDark = useIsDark();
  const colors = isDark ? DARK_SERIES : LIGHT_SERIES;

  useEffect(() => {
    let cancelled = false;
    apiGet<StatsResponse>("/v1/stats", apiKey, { bucket: "day", group_by: "model" })
      .then((stats) => {
        if (!cancelled) setData(pivot(stats));
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Failed to load stats");
      });
    return () => {
      cancelled = true;
    };
  }, [apiKey]);

  if (error) {
    return <p className="text-sm text-[var(--status-critical)]">{error}</p>;
  }

  if (!data) {
    return <p className="text-sm text-[var(--text-muted)]">Loading spend...</p>;
  }

  if (data.rows.length === 0) {
    return <p className="text-sm text-[var(--text-muted)]">No calls logged yet for this project.</p>;
  }

  return (
    <ResponsiveContainer width="100%" height={320}>
      <BarChart data={data.rows} barCategoryGap="20%">
        <CartesianGrid vertical={false} stroke="var(--gridline)" />
        <XAxis
          dataKey="bucket"
          tickFormatter={formatDate}
          stroke="var(--baseline)"
          tick={{ fill: "var(--text-muted)", fontSize: 12 }}
          tickLine={false}
        />
        <YAxis
          tickFormatter={(v: number) => `$${v}`}
          stroke="var(--baseline)"
          tick={{ fill: "var(--text-muted)", fontSize: 12 }}
          tickLine={false}
          axisLine={false}
        />
        <Tooltip content={ChartTooltip} cursor={{ fill: "var(--gridline)", opacity: 0.4 }} />
        <Legend
          formatter={(value: string) => <span className="text-[var(--text-secondary)]">{value}</span>}
          iconType="rect"
          iconSize={10}
        />
        {data.models.map((model, i) => (
          <Bar
            key={model}
            dataKey={model}
            stackId="spend"
            fill={colors[i % colors.length]}
            maxBarSize={24}
            radius={i === data.models.length - 1 ? [4, 4, 0, 0] : 0}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}
