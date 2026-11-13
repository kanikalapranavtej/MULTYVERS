import sqlite3
from pathlib import Path

import pytest

from app import create_app
from app.config import Config


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_FILE = PROJECT_ROOT / "database" / "schema.sql"


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret-key"
    WTF_CSRF_ENABLED = False


@pytest.fixture
def app(tmp_path):

    database_path = tmp_path / "test.db"

    connection = sqlite3.connect(database_path)

    schema = SCHEMA_FILE.read_text(encoding="utf-8")

    connection.executescript(schema)

    connection.close()

    class TemporaryConfig(TestConfig):
        DATABASE = str(database_path)

    application = create_app(TemporaryConfig)

    yield application


@pytest.fixture
def client(app):
    return app.test_client()


def test_home_endpoint(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.content_type.startswith("text/html")
    assert b"MULTYVERS" in response.data


def test_health_endpoint(client):

    response = client.get("/health")

    assert response.status_code == 200

    data = response.get_json()

    assert data["status"] == "healthy"
    assert data["database"] == "connected"


def test_health_returns_all_tables(client):

    response = client.get("/health")

    data = response.get_json()

    expected_tables = {
        "users",
        "events",
        "categories",
        "venues",
        "registrations"
    }

    assert expected_tables.issubset(set(data["tables"]))


def test_invalid_route_returns_404(client):

    response = client.get("/invalid-page")

    assert response.status_code == 404

    assert response.get_json()["error"] == "Resource not found"