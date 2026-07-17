"""Prometheus metrics. Uses the client's default global registry, which only
aggregates correctly for a single process -- fine for this deployment (one
uvicorn worker per container), but multi-worker/multi-instance would need
the multiprocess collector (a shared directory) or a push gateway instead.
Worth knowing, not worth building for a scale this project isn't at.
"""

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

http_requests_total = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "path", "status_code"]
)
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds", "HTTP request duration in seconds", ["method", "path"]
)
llm_calls_ingested_total = Counter(
    "llm_calls_ingested_total", "Total LLM calls ingested", ["status"]
)
eval_jobs_processed_total = Counter(
    "eval_jobs_processed_total", "Total eval jobs processed by the worker"
)


def render_metrics() -> bytes:
    return generate_latest()


METRICS_CONTENT_TYPE = CONTENT_TYPE_LATEST
