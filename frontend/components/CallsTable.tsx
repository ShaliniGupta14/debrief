"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { apiGet, ApiError } from "@/lib/api-client";
import type { CallListResponse, CallSummary } from "@/lib/types";

function StatusBadge({ status }: { status: "ok" | "error" }) {
  const isOk = status === "ok";
  return (
    <span
      className="inline-flex items-center gap-1.5 text-sm"
      style={{ color: isOk ? "var(--status-good)" : "var(--status-critical)" }}
    >
      <span
        className="inline-block h-1.5 w-1.5 rounded-full"
        style={{ backgroundColor: isOk ? "var(--status-good)" : "var(--status-critical)" }}
      />
      {status}
    </span>
  );
}

function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function CallsTable({ apiKey }: { apiKey: string }) {
  const router = useRouter();
  const [items, setItems] = useState<CallSummary[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [initialLoad, setInitialLoad] = useState(true);

  function loadPage(cursor?: string) {
    setLoading(true);
    apiGet<CallListResponse>("/v1/calls", apiKey, { limit: "25", cursor })
      .then((res) => {
        setItems((prev) => (cursor ? [...prev, ...res.items] : res.items));
        setNextCursor(res.next_cursor);
        setError(null);
      })
      .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "Failed to load calls"))
      .finally(() => {
        setLoading(false);
        setInitialLoad(false);
      });
  }

  useEffect(() => {
    loadPage();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiKey]);

  if (error) {
    return <p className="text-sm text-[var(--status-critical)]">{error}</p>;
  }

  if (initialLoad) {
    return <p className="text-sm text-[var(--text-muted)]">Loading calls...</p>;
  }

  if (items.length === 0) {
    return <p className="text-sm text-[var(--text-muted)]">No calls logged yet for this project.</p>;
  }

  return (
    <div>
      <div className="overflow-x-auto rounded border border-[var(--border)]">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] text-[var(--text-muted)]">
              <th className="px-3 py-2 font-medium">Time</th>
              <th className="px-3 py-2 font-medium">Model</th>
              <th className="px-3 py-2 font-medium">Version</th>
              <th className="px-3 py-2 font-medium">Status</th>
              <th className="px-3 py-2 font-medium">Prompt</th>
              <th className="px-3 py-2 text-right font-medium">Cost</th>
              <th className="px-3 py-2 text-right font-medium">Latency</th>
            </tr>
          </thead>
          <tbody>
            {items.map((call) => (
              <tr
                key={call.id}
                onClick={() => router.push(`/calls/${call.id}`)}
                className="cursor-pointer border-b border-[var(--border)] last:border-0 hover:bg-[var(--gridline)]"
              >
                <td className="px-3 py-2 text-[var(--text-secondary)] [font-variant-numeric:tabular-nums]">
                  {formatTimestamp(call.created_at)}
                </td>
                <td className="px-3 py-2 text-[var(--text-primary)]">{call.model}</td>
                <td className="px-3 py-2 text-[var(--text-secondary)]">{call.prompt_version ?? "-"}</td>
                <td className="px-3 py-2">
                  <StatusBadge status={call.status} />
                </td>
                <td className="max-w-xs truncate px-3 py-2 text-[var(--text-secondary)]" title={call.prompt_preview}>
                  {call.prompt_preview}
                </td>
                <td className="px-3 py-2 text-right text-[var(--text-primary)] [font-variant-numeric:tabular-nums]">
                  {call.cost_usd ? `$${Number(call.cost_usd).toFixed(4)}` : "-"}
                </td>
                <td className="px-3 py-2 text-right text-[var(--text-secondary)] [font-variant-numeric:tabular-nums]">
                  {call.latency_ms}ms
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {nextCursor && (
        <button
          type="button"
          onClick={() => loadPage(nextCursor)}
          disabled={loading}
          className="mt-3 rounded border border-[var(--border)] px-3 py-1.5 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] disabled:opacity-50"
        >
          {loading ? "Loading..." : "Load more"}
        </button>
      )}
    </div>
  );
}
