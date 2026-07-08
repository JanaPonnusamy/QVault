"""Tests for the login contract (/api/auth/login).

Locks in the OAuth2 password-grant contract: the endpoint takes
`application/x-www-form-urlencoded` fields `username`/`password` (via
`OAuth2PasswordRequestForm`), not a JSON body. Sending a JSON body or a raw
form-encoded string to a JSON-`Body()` endpoint produces FastAPI's
`model_attributes_type` error ("Input should be a valid dictionary or object to
extract fields from") -- these tests guard against that regression and verify
the full flow: login -> JWT -> `/api/auth/me` -> protected endpoints.
"""
from fastapi.testclient import TestClient

from app.core.app import app
from app.config.settings import settings

client = TestClient(app)


def test_valid_login_returns_token():
    r = client.post(
        "/api/auth/login",
        data={"username": settings.admin_username, "password": settings.admin_password},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_valid_login_token_authenticates_me_and_protected_endpoints():
    r = client.post(
        "/api/auth/login",
        data={"username": settings.admin_username, "password": settings.admin_password},
    )
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["username"] == settings.admin_username
    assert "*" in me.json()["permissions"] or me.json()["permissions"]

    protected = client.get("/api/users", headers=headers)
    assert protected.status_code == 200


def test_invalid_password_returns_401():
    r = client.post(
        "/api/auth/login",
        data={"username": settings.admin_username, "password": "wrong-password"},
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid username or password"


def test_invalid_username_returns_401():
    r = client.post(
        "/api/auth/login",
        data={"username": "no-such-user", "password": "whatever"},
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid username or password"


def test_missing_fields_returns_422_field_required():
    r = client.post("/api/auth/login", data={})
    assert r.status_code == 422
    detail = r.json()["detail"]
    fields = {d["loc"][-1] for d in detail}
    assert fields == {"username", "password"}
    assert all(d["type"] == "missing" for d in detail)


def test_json_body_is_rejected_as_missing_form_fields_not_500():
    """A JSON body (legacy/mismatched client) must fail as a normal 422, never a 500."""
    r = client.post(
        "/api/auth/login",
        json={"username": settings.admin_username, "password": settings.admin_password},
    )
    assert r.status_code == 422


def test_malformed_body_never_raises_model_attributes_type_error():
    """Regression guard: no login request shape should surface the JSON-Body
    'dictionary or object' pydantic error -- that error only occurs when the
    endpoint's parameter is bound via Body()/a plain BaseModel, not Form()."""
    r = client.post(
        "/api/auth/login",
        content=b"not even close to a valid body {{{",
        headers={"Content-Type": "text/plain"},
    )
    assert r.status_code == 422
    for item in r.json()["detail"]:
        assert item["type"] != "model_attributes_type"
