"use client";

import { ApiKeyBar } from "@/components/ApiKeyBar";
import { CallsTable } from "@/components/CallsTable";
import { SpendChart } from "@/components/SpendChart";
import { useApiKey } from "@/lib/api-key-context";

export default function DashboardPage() {
  const { apiKey, ready } = useApiKey();

  return (
    <main className="mx-auto max-w-5xl px-6 py-8">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-[var(--text-primary)]">Debrief</h1>
          <p className="text-sm text-[var(--text-muted)]">
            Flight recorder + quality grader for LLM applications.
          </p>
        </div>
        <ApiKeyBar />
      </div>

      {!ready ? null : !apiKey ? (
        <p className="rounded border border-[var(--border)] bg-[var(--surface-1)] px-4 py-6 text-center text-sm text-[var(--text-muted)]">
          Enter a project API key above to view its dashboard.
        </p>
      ) : (
        <div className="flex flex-col gap-8">
          <section className="rounded border border-[var(--border)] bg-[var(--surface-1)] p-4">
            <h2 className="mb-4 text-sm font-medium text-[var(--text-primary)]">Daily spend by model</h2>
            <SpendChart apiKey={apiKey} />
          </section>

          <section>
            <h2 className="mb-3 text-sm font-medium text-[var(--text-primary)]">Recent calls</h2>
            <CallsTable apiKey={apiKey} />
          </section>
        </div>
      )}
    </main>
  );
}
