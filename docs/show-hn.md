# Show HN draft

**Title:** Show HN: Debrief – self-hostable LLM observability + eval platform, built in 3 days

**URL:** https://github.com/ShaliniGupta14/debrief

---

Hi HN,

I built Debrief over a 3-day sprint: log every call your LLM app makes, automatically grade the outputs (regex/JSON-schema/length/contains, or an LLM-as-judge rubric), and when you ship a new prompt version, get a straight answer — with a bootstrapped confidence interval, not just a lower average — on whether it actually regressed.

Live demo (read-only, seeded data, no signup): https://debrief-six-omega.vercel.app

The part I spent the most time on isn't the CRUD dashboard, it's `GET /v1/compare`. The naive way to detect a prompt regression is "did the mean score go down." On small samples that flags noise constantly — a version can look "worse" by pure luck. Instead it runs a percentile bootstrap (2000 resamples) on the score delta between two versions and only calls it a regression when the *entire* 95% confidence interval sits below zero. I wrote a test specifically for the case a naive check gets wrong: a tiny true difference (0.75 vs 0.72) on 12 noisy samples, asserting the CI straddles zero and `regressed` comes back `False`.

A few other things that were harder than expected:

- **LLM-as-judge without parsing JSON out of prose.** The judge uses Claude's tool-use API to force structured output, so a score never comes back as free text I have to regex out of a sentence. Judge rubrics also support calibration: run the same rubric N times against a fixed sample and report variance, so you know how noisy your own judge is before trusting it.
- **Rate limiting that's actually atomic.** The obvious Redis pipeline (check count, then write) has a check-then-act race under concurrency. Fixed with a single Lua script (`EVAL`) that does prune/check/record in one atomic step — and I wrote a test that fires 20 concurrent requests at a limit of 5 to prove it, since a sequential test loop wouldn't have caught the race at all.
- **Prometheus cardinality.** `/metrics` labels requests by route *template* (`/v1/calls/{call_id}`), not the interpolated path, so a year of traffic doesn't turn into a year of unique UUID-labeled time series.

Stack: FastAPI + SQLAlchemy 2.0 (async) + Postgres 16 for the API, Redis + arq for the eval worker queue, Next.js 14 for the dashboard. Self-hostable via `docker compose up`; the hosted demo runs on Railway (API + worker, same image, role selected by an env var) and Vercel (frontend).

Everything non-obvious I decided along the way — and why — is logged in [DECISIONS.md](https://github.com/ShaliniGupta14/debrief/blob/main/DECISIONS.md) as I went, including a few mistakes (CORS gaps a browser caught that an in-process test suite couldn't, a Prometheus/route-cardinality near-miss). "What I'd build next" is at the bottom of the README — the honest gaps, not just the finished parts.

Would love feedback, especially from anyone who's built eval infra for their own LLM app and hit a wall I haven't yet.
