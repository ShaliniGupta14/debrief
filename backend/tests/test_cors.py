async def test_cors_allows_configured_frontend_origin(client):
    response = await client.options(
        "/v1/calls",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "x-api-key",
        },
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


async def test_cors_rejects_unconfigured_origin(client):
    response = await client.options(
        "/v1/calls",
        headers={
            "Origin": "http://evil.example.com",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "x-api-key",
        },
    )
    assert "access-control-allow-origin" not in response.headers
