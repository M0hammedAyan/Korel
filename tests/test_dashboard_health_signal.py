"""Integration tests for the dashboard health signal.

These tests lock the contract used by the frontend banner:
- `/health/live` is the availability signal for the dashboard.
- `/health` can still report degraded when dependencies fail.
"""

import os
import tempfile
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


# Use a real temp file so all sqlite3.connect() calls share one DB.
# :memory: opens a fresh empty database per connection, breaking init_db().
_db_fd, _db_path = tempfile.mkstemp(suffix=".db", prefix="koral_dashboard_test_")
os.close(_db_fd)

os.environ["API_KEY"] = "test-api-key"
os.environ["API_KEY_ADMIN"] = "test-admin-key"
os.environ["API_KEY_OPERATOR"] = "test-operator-key"
os.environ["API_KEY_VIEWER"] = "test-viewer-key"
os.environ["JWT_SECRET"] = "test-jwt-secret"
os.environ["DB_TYPE"] = "sqlite"
os.environ["DB_PATH"] = _db_path
os.environ["DISABLE_AUTH"] = "false"
os.environ["REMEDIATION_ENABLED"] = "true"


# Explicitly init schema — TestClient doesn't guarantee lifespan fires before first test.
from backend.database import init_db as _init_db

_init_db()

from backend.main import app


client = TestClient(app, raise_server_exceptions=False)


def test_dashboard_live_health_stays_green_when_dependencies_degrade():
    r = client.get("/health/live")

    assert r.status_code == 200
    assert r.json() == {"status": "ok", "live": True, "service": "koral-backend"}


def test_full_health_can_degrade_without_affecting_dashboard_live_signal():
    with patch("backend.main._database_health", new=AsyncMock(return_value=False)), patch(
        "backend.main._dependency_health", new=AsyncMock(return_value=False)
    ), patch("backend.main._websocket_health", return_value=False):
        degraded = client.get("/health")
        live = client.get("/health/live")

    assert degraded.status_code == 503
    assert degraded.json()["status"] == "degraded"
    assert live.status_code == 200
    assert live.json()["status"] == "ok"