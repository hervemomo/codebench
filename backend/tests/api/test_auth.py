from uuid import uuid4

import pytest


def _unique_email(prefix: str) -> str:
    """Tests commit directly to a persistent dev DB (no rollback — the RQ job
    under test needs to see committed data from a different session), so
    every email must be unique per test invocation to survive repeat runs."""
    return f"{prefix}-{uuid4().hex[:10]}@example.com"


def test_login_wrong_password_returns_401(client, make_client):
    email = _unique_email("wrongpw")
    make_client(email=email, password="CorrectHorse123!")

    resp = client.post("/api/auth/login", json={"email": email, "password": "not-the-password"})

    assert resp.status_code == 401


def test_login_unknown_email_returns_401(client):
    resp = client.post("/api/auth/login", json={"email": _unique_email("nobody"), "password": "whatever123"})
    assert resp.status_code == 401


def test_session_cookie_is_http_only_and_signed(client):
    resp = client.post("/api/auth/register", json={"email": _unique_email("cookie"), "password": "Password123!", "org_name": "Cookie Org"})
    assert resp.status_code == 201, resp.text

    set_cookie = resp.headers.get("set-cookie", "")
    assert "cb_session=" in set_cookie
    assert "httponly" in set_cookie.lower()

    token = client.cookies.get("cb_session")
    assert token is not None
    assert token.count(".") == 2  # itsdangerous URLSafeTimedSerializer: payload.timestamp.signature


def test_me_reflects_logged_in_user(client):
    email = _unique_email("me")
    reg_resp = client.post("/api/auth/register", json={"email": email, "password": "Password123!", "org_name": "Me Org"})
    assert reg_resp.status_code == 201, reg_resp.text
    reg = reg_resp.json()

    resp = client.get("/api/auth/me")

    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == email
    assert body["org_id"] == reg["org_id"]
    assert body["role"] == "admin"


def test_me_without_session_is_401(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_logout_clears_session(client):
    reg_resp = client.post("/api/auth/register", json={"email": _unique_email("bye"), "password": "Password123!", "org_name": "Bye Org"})
    assert reg_resp.status_code == 201, reg_resp.text
    assert client.get("/api/auth/me").status_code == 200

    client.post("/api/auth/logout")

    assert client.get("/api/auth/me").status_code == 401


def test_register_duplicate_email_returns_409(client):
    payload = {"email": _unique_email("dup"), "password": "Password123!", "org_name": "Org A"}
    assert client.post("/api/auth/register", json=payload).status_code == 201

    resp = client.post("/api/auth/register", json={**payload, "org_name": "Org B"})
    assert resp.status_code == 409


@pytest.mark.parametrize("method,path,body", [
    ("get", "/api/projects", None),
    ("post", "/api/projects", {"name": "x"}),
    ("put", "/api/projects/1/context", {"context": "x"}),
    ("post", "/api/projects/1/questions", {"text": "x", "survey_col": "y"}),
    ("post", "/api/datasets/1/preprocess", None),
    ("get", "/api/datasets/1/stats", None),
    ("get", "/api/jobs/some-job-id", None),
])
def test_business_endpoints_require_auth(client, method, path, body):
    """Well-formed bodies, so a 401 can never be masked by a 422 validation error."""
    kwargs = {"json": body} if body is not None else {}
    resp = getattr(client, method)(path, **kwargs)
    assert resp.status_code == 401


def test_upload_endpoint_requires_auth(client, tiny_survey_bytes):
    resp = client.post(
        "/api/questions/1/datasets",
        files={"file": ("tiny_survey.xlsx", tiny_survey_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 401
