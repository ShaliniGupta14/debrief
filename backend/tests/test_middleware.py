import uuid


async def test_response_includes_a_generated_request_id(client):
    response = await client.get("/healthz")
    request_id = response.headers.get("x-request-id")
    assert request_id is not None
    uuid.UUID(request_id)  # raises if not a valid UUID


async def test_echoes_a_client_supplied_request_id(client):
    response = await client.get("/healthz", headers={"X-Request-ID": "my-custom-id"})
    assert response.headers.get("x-request-id") == "my-custom-id"


async def test_different_requests_get_different_generated_ids(client):
    first = await client.get("/healthz")
    second = await client.get("/healthz")
    assert first.headers["x-request-id"] != second.headers["x-request-id"]
