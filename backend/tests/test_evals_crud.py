VALID_REGEX_EVAL = {"name": "phone-format", "type": "regex", "config": {"pattern": r"\d{3}-\d{4}"}}


async def test_create_eval_happy_path(client, project):
    _, raw_key = project
    response = await client.post("/v1/evals", json=VALID_REGEX_EVAL, headers={"X-API-Key": raw_key})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "phone-format"
    assert body["type"] == "regex"
    assert body["enabled"] is True
    assert body["calibration_report"] is None


async def test_create_eval_rejects_missing_required_config_key(client, project):
    _, raw_key = project
    response = await client.post(
        "/v1/evals",
        json={"name": "bad-regex", "type": "regex", "config": {}},
        headers={"X-API-Key": raw_key},
    )
    assert response.status_code == 422


async def test_create_eval_rejects_length_with_no_bounds(client, project):
    _, raw_key = project
    response = await client.post(
        "/v1/evals",
        json={"name": "bad-length", "type": "length", "config": {}},
        headers={"X-API-Key": raw_key},
    )
    assert response.status_code == 422


async def test_create_eval_rejects_duplicate_name(client, project):
    _, raw_key = project
    headers = {"X-API-Key": raw_key}
    first = await client.post("/v1/evals", json=VALID_REGEX_EVAL, headers=headers)
    assert first.status_code == 201
    second = await client.post("/v1/evals", json=VALID_REGEX_EVAL, headers=headers)
    assert second.status_code == 409


async def test_list_evals_returns_only_this_projects_evals(client, project, db_session):
    from app.models import Project as ProjectModel

    proj, raw_key = project
    other = ProjectModel(name="other", api_key_hash="other-hash-evals", api_key_prefix="other")
    db_session.add(other)
    await db_session.commit()

    await client.post("/v1/evals", json=VALID_REGEX_EVAL, headers={"X-API-Key": raw_key})

    response = await client.get("/v1/evals", headers={"X-API-Key": raw_key})
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["name"] == "phone-format"


async def test_list_evals_rejects_missing_auth(client):
    response = await client.get("/v1/evals")
    assert response.status_code == 401
