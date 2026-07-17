import datetime
from decimal import Decimal

from app.models import ModelPrice

VALID_CALL = {
    "model": "claude-sonnet-5",
    "prompt": "hello",
    "response": "hi there",
    "input_tokens": 10,
    "output_tokens": 5,
    "latency_ms": 100,
}


async def test_metrics_endpoint_returns_prometheus_exposition_format(client):
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    body = response.text
    assert "http_requests_total" in body
    assert "http_request_duration_seconds" in body


async def test_metrics_records_route_template_not_interpolated_path(client, project):
    _, raw_key = project
    # Two distinct call IDs hitting the same route template.
    await client.get(
        f"/v1/calls/{'a' * 8}-0000-0000-0000-{'0' * 12}", headers={"X-API-Key": raw_key}
    )
    await client.get(
        f"/v1/calls/{'b' * 8}-0000-0000-0000-{'0' * 12}", headers={"X-API-Key": raw_key}
    )

    body = (await client.get("/metrics")).text
    assert 'path="/v1/calls/{call_id}"' in body
    # Neither raw UUID should leak into a metric label -- that's the whole point.
    assert "aaaaaaaa" not in body
    assert "bbbbbbbb" not in body


async def test_ingest_increments_llm_calls_ingested_counter(client, project, db_session):
    _, raw_key = project
    db_session.add(
        ModelPrice(
            model="claude-sonnet-5",
            input_price_per_mtok=Decimal("3"),
            output_price_per_mtok=Decimal("15"),
            effective_date=datetime.date(2026, 1, 1),
        )
    )
    await db_session.commit()

    before = (await client.get("/metrics")).text
    before_count = _extract_counter(before, 'llm_calls_ingested_total{status="ok"}')

    await client.post("/v1/ingest", json=[VALID_CALL], headers={"X-API-Key": raw_key})

    after = (await client.get("/metrics")).text
    after_count = _extract_counter(after, 'llm_calls_ingested_total{status="ok"}')
    assert after_count == before_count + 1


def _extract_counter(body: str, prefix: str) -> float:
    for line in body.splitlines():
        if line.startswith(prefix):
            return float(line.split()[-1])
    return 0.0
