# Decisions

Non-obvious tradeoffs made while building Debrief, and why. Kept short (2-4 lines) on purpose — written for future-me in interviews, not as a design doc.

## 2026-07-15 — Product name: Debrief

Considered "Callsign" (pun on `llm_calls` + aviation theme) but it collides with an existing identity-verification company. "Debrief" keeps the aviation/mission-review theme — fits the "grader" half of the pitch specifically — and reads cleanly as a standalone brand.

## 2026-07-15 — Postgres full-text search over pgvector

The only search requirement in scope is "full-text searchable call history" — literal/lexical search, not semantic similarity. Native `tsvector` + GIN gets us that with zero new infra and no embedding generation cost/latency on ingest. pgvector would be the right call if we needed semantic "find similar prompts" search, but that's explicitly out of scope (and `compare`'s "similar prompts" matching starts with exact-match/metadata-key correlation, not embeddings).

## 2026-07-15 — Separate `projects` table instead of a raw `project_key` string column

The spec requires the API key to be "hashed at rest," which means the raw secret can never also be the value used for row-scoping/indexing — you can't efficiently filter millions of rows by re-hashing a secret per query, and a hot, constantly-selected column is the wrong place to keep something security-sensitive. `projects` stores `api_key_hash` (unique) for auth lookup; every other table references the resulting `project_id` (uuid). The API key is a credential; `project_id` is a relational identifier — different concerns, different columns.

## 2026-07-15 — `cost_usd` and `model_prices` rates as NUMERIC, not FLOAT

Money math on floats accumulates silent rounding error. NUMERIC(12,6) is exact; the extra storage is irrelevant at this scale.

## 2026-07-15 — Calibration runs don't live in `eval_results`

`eval_results` has `UNIQUE(call_id, eval_definition_id)` — one score per call per eval, which is what the dashboard and compare endpoint need. Judge calibration ("run the judge 3x on the same calibration set, report variance") needs *multiple* scores for the same call+eval pair, which would violate that constraint. Calibration is a property of the eval definition ("how consistent is this rubric"), not of any one call, so its output (sample scores, mean, stddev, timestamp) is stored as `eval_definitions.calibration_report` (jsonb) instead of a second results table.

## 2026-07-15 — arq over RQ for the eval worker

The backend is async end-to-end (FastAPI + asyncpg). arq is asyncio-native, so worker tasks reuse the same async DB session code as the API. RQ is sync/thread-based — it would work, but it would mean maintaining two different DB-access styles in one codebase for no real benefit.

## 2026-07-15 — model_prices priced at point-in-time, not "current price"

Cost calc looks up `WHERE model = ? AND effective_date <= call.created_at ORDER BY effective_date DESC LIMIT 1`, not "the latest row for this model." If Anthropic changes pricing, historical calls should keep reflecting the price that was actually in effect when they ran, not get silently repriced.
