"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { apiGet, ApiError } from "@/lib/api-client";
import { useApiKey } from "@/lib/api-key-context";
import type { CallDetail } from "@/lib/types";

function EvalBadge({ passed }: { passed: boolean | null }) {
  if (passed === null) {
    return <span className="text-sm text-[var(--text-muted)]">—</span>;
  }
  const color = passed ? "var(--status-good)" : "var(--status-critical)";
  return (
    <span className="inline-flex items-center gap-1.5 text-sm" style={{ color }}>
      <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ backgroundColor: color }} />
      {passed ? "passed" : "failed"}
    </span>
  );
}

export default function CallDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { apiKey, ready } = useApiKey();
  const [call, setCall] = useState<CallDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!apiKey) return;
    apiGet<CallDetail>(`/v1/calls/${id}`, apiKey)
      .then(setCall)
      .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "Failed to load call"));
  }, [apiKey, id]);

  if (!ready) return null;
  if (!apiKey) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-8">
        <p className="text-sm text-[var(--text-muted)]">Enter a project API key on the dashboard first.</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-3xl px-6 py-8">
      <Link href="/" className="text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
        ← Dashboard
      </Link>

      {error && <p className="mt-4 text-sm text-[var(--status-critical)]">{error}</p>}

      {!call && !error && <p className="mt-4 text-sm text-[var(--text-muted)]">Loading...</p>}

      {call && (
        <div className="mt-4 flex flex-col gap-6">
          <div>
            <h1 className="text-lg font-semibold text-[var(--text-primary)]">{call.model}</h1>
            <p className="text-sm text-[var(--text-muted)]">
              {call.prompt_version ? `version ${call.prompt_version} · ` : ""}
              {new Date(call.created_at).toLocaleString()}
            </p>
          </div>

          <section className="rounded border border-[var(--border)] bg-[var(--surface-1)] p-4">
            <h2 className="mb-2 text-sm font-medium text-[var(--text-primary)]">Prompt</h2>
            <p className="whitespace-pre-wrap text-sm text-[var(--text-secondary)]">{call.prompt}</p>
          </section>

          <section className="rounded border border-[var(--border)] bg-[var(--surface-1)] p-4">
            <h2 className="mb-2 text-sm font-medium text-[var(--text-primary)]">Response</h2>
            <p className="whitespace-pre-wrap text-sm text-[var(--text-secondary)]">
              {call.response || <span className="text-[var(--status-critical)]">{call.error_message}</span>}
            </p>
          </section>

          <section className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
            <div>
              <div className="text-[var(--text-muted)]">Cost</div>
              <div className="[font-variant-numeric:tabular-nums]">
                {call.cost_usd ? `$${Number(call.cost_usd).toFixed(4)}` : "—"}
              </div>
            </div>
            <div>
              <div className="text-[var(--text-muted)]">Latency</div>
              <div className="[font-variant-numeric:tabular-nums]">{call.latency_ms}ms</div>
            </div>
            <div>
              <div className="text-[var(--text-muted)]">Tokens</div>
              <div className="[font-variant-numeric:tabular-nums]">
                {call.input_tokens} in / {call.output_tokens} out
              </div>
            </div>
            <div>
              <div className="text-[var(--text-muted)]">Status</div>
              <div>{call.status}</div>
            </div>
          </section>

          <section>
            <h2 className="mb-3 text-sm font-medium text-[var(--text-primary)]">Eval results</h2>
            {call.eval_results.length === 0 ? (
              <p className="text-sm text-[var(--text-muted)]">
                No evals have run for this call yet.
              </p>
            ) : (
              <div className="overflow-x-auto rounded border border-[var(--border)]">
                <table className="w-full min-w-[500px] text-left text-sm">
                  <thead>
                    <tr className="border-b border-[var(--border)] text-[var(--text-muted)]">
                      <th className="px-3 py-2 font-medium">Score</th>
                      <th className="px-3 py-2 font-medium">Result</th>
                      <th className="px-3 py-2 font-medium">Rationale</th>
                    </tr>
                  </thead>
                  <tbody>
                    {call.eval_results.map((er) => (
                      <tr key={er.id} className="border-b border-[var(--border)] last:border-0">
                        <td className="px-3 py-2 [font-variant-numeric:tabular-nums]">
                          {Number(er.score).toFixed(2)}
                        </td>
                        <td className="px-3 py-2">
                          <EvalBadge passed={er.passed} />
                        </td>
                        <td className="px-3 py-2 text-[var(--text-secondary)]">
                          {er.judge_rationale ?? "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>
      )}
    </main>
  );
}
