"use client";

import Link from "next/link";
import { useState } from "react";
import { apiGet, ApiError } from "@/lib/api-client";
import { useApiKey } from "@/lib/api-key-context";
import type { CompareResponse } from "@/lib/types";

function DeltaCell({ delta, regressed }: { delta: number | null; regressed: boolean }) {
  if (delta === null) return <span className="text-[var(--text-muted)]">—</span>;
  const color = regressed
    ? "var(--status-critical)"
    : delta > 0
      ? "var(--status-good)"
      : "var(--text-secondary)";
  const sign = delta > 0 ? "+" : "";
  return (
    <span style={{ color }} className="[font-variant-numeric:tabular-nums]">
      {sign}
      {delta.toFixed(3)}
    </span>
  );
}

export default function ComparePage() {
  const { apiKey, ready } = useApiKey();
  const [versionA, setVersionA] = useState("v1");
  const [versionB, setVersionB] = useState("v2");
  const [result, setResult] = useState<CompareResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function runCompare() {
    if (!apiKey) return;
    setLoading(true);
    setError(null);
    apiGet<CompareResponse>("/v1/compare", apiKey, { version_a: versionA, version_b: versionB })
      .then(setResult)
      .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "Failed to compare"))
      .finally(() => setLoading(false));
  }

  if (!ready) return null;

  return (
    <main className="mx-auto max-w-4xl px-6 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <Link href="/" className="text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
            ← Dashboard
          </Link>
          <h1 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">Compare versions</h1>
        </div>
      </div>

      {!apiKey ? (
        <p className="text-sm text-[var(--text-muted)]">Enter a project API key on the dashboard first.</p>
      ) : (
        <>
          <form
            className="mb-6 flex items-end gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              runCompare();
            }}
          >
            <label className="flex flex-col gap-1 text-sm text-[var(--text-secondary)]">
              Baseline (A)
              <input
                value={versionA}
                onChange={(e) => setVersionA(e.target.value)}
                className="rounded border border-[var(--border)] bg-[var(--surface-1)] px-2 py-1.5 text-[var(--text-primary)] outline-none focus:border-[var(--series-1)]"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm text-[var(--text-secondary)]">
              Candidate (B)
              <input
                value={versionB}
                onChange={(e) => setVersionB(e.target.value)}
                className="rounded border border-[var(--border)] bg-[var(--surface-1)] px-2 py-1.5 text-[var(--text-primary)] outline-none focus:border-[var(--series-1)]"
              />
            </label>
            <button
              type="submit"
              disabled={loading}
              className="rounded bg-[var(--series-1)] px-4 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
            >
              {loading ? "Comparing..." : "Compare"}
            </button>
          </form>

          {error && <p className="text-sm text-[var(--status-critical)]">{error}</p>}

          {result && (
            <div className="flex flex-col gap-6">
              {result.any_regression && (
                <div
                  className="flex items-center gap-2 rounded border px-4 py-3 text-sm"
                  style={{
                    borderColor: "var(--status-critical)",
                    color: "var(--status-critical)",
                    backgroundColor: "color-mix(in srgb, var(--status-critical) 8%, transparent)",
                  }}
                >
                  <span aria-hidden>⚠</span>
                  <span>
                    Regression detected: {result.version_b} scores significantly worse than{" "}
                    {result.version_a} on at least one eval.
                  </span>
                </div>
              )}

              <section>
                <h2 className="mb-3 text-sm font-medium text-[var(--text-primary)]">Evals</h2>
                <div className="overflow-x-auto rounded border border-[var(--border)]">
                  <table className="w-full min-w-[600px] text-left text-sm">
                    <thead>
                      <tr className="border-b border-[var(--border)] text-[var(--text-muted)]">
                        <th className="px-3 py-2 font-medium">Eval</th>
                        <th className="px-3 py-2 text-right font-medium">Mean A</th>
                        <th className="px-3 py-2 text-right font-medium">Mean B</th>
                        <th className="px-3 py-2 text-right font-medium">Delta</th>
                        <th className="px-3 py-2 text-right font-medium">95% CI</th>
                        <th className="px-3 py-2 font-medium">n (A / B)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.evals.map((ev) => (
                        <tr key={ev.eval_definition_id} className="border-b border-[var(--border)] last:border-0">
                          <td className="px-3 py-2 text-[var(--text-primary)]">{ev.eval_name}</td>
                          <td className="px-3 py-2 text-right [font-variant-numeric:tabular-nums]">
                            {ev.mean_score_a?.toFixed(3) ?? "—"}
                          </td>
                          <td className="px-3 py-2 text-right [font-variant-numeric:tabular-nums]">
                            {ev.mean_score_b?.toFixed(3) ?? "—"}
                          </td>
                          <td className="px-3 py-2 text-right">
                            <DeltaCell delta={ev.delta} regressed={ev.regressed} />
                          </td>
                          <td className="px-3 py-2 text-right text-[var(--text-secondary)] [font-variant-numeric:tabular-nums]">
                            {ev.ci_low !== null && ev.ci_high !== null
                              ? `[${ev.ci_low.toFixed(3)}, ${ev.ci_high.toFixed(3)}]`
                              : "—"}
                          </td>
                          <td className="px-3 py-2 text-[var(--text-secondary)] [font-variant-numeric:tabular-nums]">
                            {ev.n_calls_a} / {ev.n_calls_b}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>

              <section>
                <h2 className="mb-3 text-sm font-medium text-[var(--text-primary)]">
                  Worst regressions (by prompt)
                </h2>
                {result.worst_regressions.length === 0 ? (
                  <p className="text-sm text-[var(--text-muted)]">No shared prompts to compare.</p>
                ) : (
                  <div className="overflow-x-auto rounded border border-[var(--border)]">
                    <table className="w-full min-w-[600px] text-left text-sm">
                      <thead>
                        <tr className="border-b border-[var(--border)] text-[var(--text-muted)]">
                          <th className="px-3 py-2 font-medium">Prompt</th>
                          <th className="px-3 py-2 font-medium">Eval</th>
                          <th className="px-3 py-2 text-right font-medium">Mean A</th>
                          <th className="px-3 py-2 text-right font-medium">Mean B</th>
                          <th className="px-3 py-2 text-right font-medium">Delta</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.worst_regressions.map((r, i) => (
                          <tr key={i} className="border-b border-[var(--border)] last:border-0">
                            <td
                              className="max-w-xs truncate px-3 py-2 text-[var(--text-secondary)]"
                              title={r.prompt}
                            >
                              {r.prompt}
                            </td>
                            <td className="px-3 py-2 text-[var(--text-secondary)]">{r.eval_name}</td>
                            <td className="px-3 py-2 text-right [font-variant-numeric:tabular-nums]">
                              {r.mean_score_a.toFixed(3)}
                            </td>
                            <td className="px-3 py-2 text-right [font-variant-numeric:tabular-nums]">
                              {r.mean_score_b.toFixed(3)}
                            </td>
                            <td className="px-3 py-2 text-right">
                              <DeltaCell delta={r.delta} regressed={r.delta < 0} />
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
        </>
      )}
    </main>
  );
}
