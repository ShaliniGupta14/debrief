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

## 2026-07-15 — CORS caught by actually driving the browser, not by tests

The pytest suite (25 tests, all passing) never caught that the API had no CORS middleware, because `httpx.ASGITransport` calls the app in-process and skips the browser-side preflight check entirely. Only running the real frontend against the real backend in a headless browser surfaced it. Lesson encoded here, not just fixed: an API with a separate frontend origin needs at least one browser-driven smoke check, because "all tests green" doesn't mean "a browser can talk to it."

## 2026-07-15 — `NEXT_PUBLIC_*` is a build-time value, not a runtime one

`NEXT_PUBLIC_API_URL` gets inlined into the client JS bundle at `next build`, not read from the environment when the container starts. Setting it under `docker-compose`'s `environment:` for the `web` service would silently do nothing — it has to be a Docker build `arg`, consumed in the Dockerfile's build stage before `pnpm build` runs. Confirmed on Vercel too: changing the env var alone did nothing until a fresh `vercel deploy --prod` rebuilt the bundle.

## 2026-07-15 — CLI login isn't the same as deploy authorization

`gh`/`railway`/`vercel` CLI login only authenticates *me* to each platform. Linking a service to a GitHub repo needs Railway's GitHub App to additionally have repo access — a separate consent step the CLI can't complete non-interactively (`railway add --repo` failed with "Unauthorized" despite `railway whoami` succeeding). Sidestepped it: `railway up ./backend --path-as-root --service api` uploads and builds the local directory directly, no GitHub App involved. Fine for a single-command deploy; would need the GitHub App step for autodeploy-on-push later.

## 2026-07-15 — Deploying surfaced two Dockerfile bugs pytest and local dev couldn't

Neither of these showed up until the actual `docker build` ran in CI: (1) `frontend/Dockerfile`'s deps layer copied only `package.json`+`pnpm-lock.yaml` for cache efficiency, silently excluding `pnpm-workspace.yaml` — the file holding the `unrs-resolver` build-script approval — so the container re-hit the exact `ERR_PNPM_IGNORED_BUILDS` block I'd already fixed locally, just invisibly. (2) The Dockerfile's generic multi-stage template assumed a `public/` directory that this project never had (favicon.ico lives under `app/` via the App Router convention instead). Both are "verified locally" gaps: `pnpm build` and `pnpm dev` never exercise a clean-room `COPY` the way a Docker build does. Installed `actionlint` for the workflow YAML itself after a duplicate-key edit slipped past `yaml.safe_load` (valid YAML, invalid GitHub Actions schema) and failed a whole run with zero jobs listed.

## 2026-07-15 — Worst-regressions matches on exact prompt text, not true per-call pairing

The spec says "biggest per-call score drops on similar prompts," but without a client-supplied correlation key, individual call pairing is ambiguous whenever multiple calls share a prompt — the normal case here, not an edge case (the seed data has 60+ calls per unique prompt per app). Naively joining every A-version call to every B-version call sharing a prompt is a combinatorial explosion, not a matching strategy: 60×65 "pairs" for one prompt alone. Instead: group by exact prompt text, compare mean score per version, sort by delta. Statistically meaningful ("this prompt does worse on average with v2"), but not literally per-call. True per-call pairing would need a client-supplied `metadata.test_case_id` at ingest time — a reasonable "what I'd build next," not something to fake with an arbitrary pairing that would just add noise.

## 2026-07-15 — Regression = the whole CI is below zero, not just a lower mean

`GET /v1/compare` uses a percentile bootstrap (2000 resamples) on the mean score delta between versions, and only flags a regression when the *entire* 95% CI of that delta sits below zero. A naive `mean_b < mean_a` check would flag noise as regression constantly on small samples. Tested this distinction directly, not just that the function returns a number: a fixed-seed case with a tiny true difference (0.75 vs 0.72) on 12 noisy synthetic samples asserts the CI straddles zero and `regressed` is `False` — the exact case a naive comparison gets wrong.

## 2026-07-16 — Request-scoped logging via `contextvars`, not a threaded parameter

Every log call needs the current request ID, but threading it through every function signature (or every log call) pollutes call sites that have nothing to do with logging. A `contextvars.ContextVar` set once in middleware and read by the log formatter gets the same result — request ID shows up on every line for free — without changing a single function signature elsewhere in the app.

## 2026-07-16 — Prometheus labels use the route template, not the interpolated path

`request.scope["route"].path` gives `/v1/calls/{call_id}`; the raw ASGI path gives `/v1/calls/53c3...`. Labeling metrics with the latter creates one new time series per UUID ever seen — unbounded cardinality that will eventually take down whatever's scraping `/metrics`. Middleware reads the matched route's template specifically so `http_requests_total` stays a small, fixed set of series regardless of traffic volume. A dedicated test asserts a raw UUID never appears in a label value, not just that the counter increments.

## 2026-07-16 — Rate limiting is one atomic Lua script, not a Redis pipeline

The obvious first design — `ZCARD` to check the count, then `ZADD` if under the limit — has a check-then-act race: two concurrent requests can both read "4 of 5 used" before either writes, and both get admitted. `EVAL`s a single script that does the prune/check/record atomically inside Redis, so there's no window between "check" and "act" for another request to land in. Proved this isn't just theoretical: a test fires 20 concurrent requests at a limit of 5 via `asyncio.gather` and asserts exactly 5 succeed — a sequential test loop wouldn't have caught the race at all.

## 2026-07-16 — Demo mode blocks writes via a dependency, not a per-route `if` check

`require_writable_project` wraps `get_current_project` and 403s if `project.is_demo`; write routes depend on it, read routes keep depending on `get_current_project` directly. FastAPI de-dupes dependencies within one request, so chaining `enforce_ingest_rate_limit -> require_writable_project -> get_current_project` costs one DB lookup, not three. The alternative — an `if project.is_demo: raise` at the top of every mutating handler — is the kind of check that's easy to forget on the next new write route; encoding it in the dependency graph means a route is either wired to the read-only guard or it isn't, visible at the signature.

## 2026-07-16 — The demo project's API key is fixed, not randomly generated

Every other seeded project gets a random key (`generate_api_key()`); the demo project gets a hardcoded constant instead, committed in `.env.example` with a comment explaining why it's safe to publish: mutations against it 403 unconditionally, regardless of who holds the key. A random key would break the "try the demo" button and the public README link every time `seed.py --reset` runs in production — the fixed key is what makes a public, stable, linkable demo possible at all.

## 2026-07-17 — `railway up` needs `--path-as-root`, even run from inside the subdirectory

Redeploying the `api`/`worker` services via `railway up backend --path-as-root` (see the 2026-07-15 entry on avoiding the GitHub App) worked before; running plain `railway up` again this time — including from *inside* `backend/`, expecting the CLI to use the CWD — instead uploaded the repo root and Railway's `railpack` builder tried to auto-detect a language, found no `start.sh` at the top level, and failed with zero useful hint that Docker was even in play. The CLI's upload root isn't "wherever you `cd`'d to" — it's the linked project's directory unless `--path-as-root <path>` is passed explicitly, every time, regardless of shell CWD. Cost two failed production deploys to rediscover; worth over-documenting.

## 2026-07-17 — Docker Desktop's daemon never finished local first-launch setup in this environment

`docker compose up` was never exercised end-to-end on this machine: Docker Desktop's backend process runs, but `~/.docker/run/docker.sock` never gets created, and its own logs show it endlessly re-checking CLI-plugin symlinks rather than starting the VM — consistent with being stuck behind a first-run GUI prompt (EULA/sign-in) that requires manual interaction the agent driving this build can't perform headlessly. Rather than claim untested success, this is the actual state: `docker compose config` validates the compose file's syntax and interpolation, and CI's `docker-build` job builds both `backend/Dockerfile` and `frontend/Dockerfile` from scratch on every push (green as of this writing) — so the images themselves are proven to build. What's *not* independently verified on this machine is the full `docker compose up` orchestration (service health-check ordering, inter-container networking). The Railway deploy of the same `backend/Dockerfile` + `docker-entrypoint.sh` succeeded in production and is live, which exercises the same image under real conditions, just not via `docker compose` specifically.
