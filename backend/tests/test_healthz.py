async def test_healthz_reports_dependency_status(client):
    response = await client.get("/healthz")
    assert response.status_code in (200, 503)
    body = response.json()
    assert set(body) == {"status", "db", "redis", "build_sha"}
