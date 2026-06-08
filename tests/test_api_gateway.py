"""API gateway smoke tests."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DEV_SKIP_AUTH", "true")
os.environ.setdefault("JWT_SECRET", "test-secret")

from api.database import init_db  # noqa: E402
from api.main import app  # noqa: E402


@pytest.fixture()
def client():
    init_db()
    return TestClient(app)


def test_health(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_users_me_dev_skip(client: TestClient):
    r = client.get("/users/me")
    assert r.status_code == 200
    assert "email" in r.json()


def test_auth_google_sync(client: TestClient):
    r = client.post(
        "/auth/google",
        json={
            "sub": "test-google-sub",
            "email": "test@example.com",
            "display_name": "Test",
        },
        headers={"X-API-Sync-Secret": "dev-sync-secret"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["access_token"]
    assert data["user"]["email"] == "test@example.com"
