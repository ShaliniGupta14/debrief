# Debrief

Self-hostable flight recorder + quality grader for LLM applications.

> Under active development (Day 1 of 3). Full quickstart, architecture diagram, and demo land end of Day 3 — see [DECISIONS.md](./DECISIONS.md) for progress and reasoning in the meantime.

## What this will do

- Log every LLM call (prompt, response, model, tokens, latency, cost, metadata, prompt version) via a tiny SDK or raw HTTP
- Dashboards for spend, latency, and volume
- Full-text searchable call history
- Automated evals (regex / JSON-schema / length / contains / LLM-as-judge) that score outputs
- Side-by-side prompt version comparison with regression detection

## Stack

Python (FastAPI, SQLAlchemy, Pydantic v2) · Postgres 16 · Redis + arq · Next.js 14 · Docker Compose

See [DECISIONS.md](./DECISIONS.md) for the reasoning behind non-obvious choices.
