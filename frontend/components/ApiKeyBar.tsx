"use client";

import { useState } from "react";
import { useApiKey } from "@/lib/api-key-context";

const DEMO_API_KEY = process.env.NEXT_PUBLIC_DEMO_API_KEY;

export function ApiKeyBar() {
  const { apiKey, setApiKey, ready } = useApiKey();
  const [draft, setDraft] = useState("");

  if (!ready) return null;

  if (apiKey) {
    return (
      <div className="flex items-center gap-3 text-sm text-[var(--text-secondary)]">
        <span>
          Project key: <code className="text-[var(--text-primary)]">{apiKey.slice(0, 12)}...</code>
        </span>
        <button
          type="button"
          onClick={() => setApiKey("")}
          className="text-[var(--text-secondary)] underline decoration-[var(--border)] underline-offset-4 hover:text-[var(--text-primary)]"
        >
          change
        </button>
      </div>
    );
  }

  return (
    <form
      className="flex items-center gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        if (draft.trim()) setApiKey(draft.trim());
      }}
    >
      <label htmlFor="api-key" className="text-sm text-[var(--text-secondary)]">
        Project API key
      </label>
      <input
        id="api-key"
        type="password"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        placeholder="sk_..."
        className="rounded border border-[var(--border)] bg-[var(--surface-1)] px-3 py-1.5 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--series-1)]"
      />
      <button
        type="submit"
        className="rounded bg-[var(--series-1)] px-3 py-1.5 text-sm font-medium text-white hover:opacity-90"
      >
        Connect
      </button>
      {DEMO_API_KEY && (
        <button
          type="button"
          onClick={() => setApiKey(DEMO_API_KEY)}
          className="text-sm text-[var(--text-secondary)] underline decoration-[var(--border)] underline-offset-4 hover:text-[var(--text-primary)]"
        >
          try the demo
        </button>
      )}
    </form>
  );
}
