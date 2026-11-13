import sqlite3
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.config import Config


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_FILE = PROJECT_ROOT / "database" / "schema.sql"


class TestConfig(Config):

    TESTING = True

    SECRET_KEY = "test-analytics-pages-secret"

    WTF_CSRF_ENABLED = False


@pytest.fixture
def app(tmp_path):

    database_path = tmp_path / "test_analytics_pages.db"

    connection = sqlite3.connect(database_path)

    connection.executescript(
        SCHEMA_FILE.read_text(encoding="utf-8")
    )

    password_hash = generate_password_hash("password123")

    users = [
        ("Test Admin", "admin@test.com", "admin"),
        ("Test Organizer", "organizer@test.com", "organizer"),
        ("Test Student", "student@test.com", "student")
    ]

    for name, email, role in users:

        connection.execute("""
            INSERT INTO users (
                name,
                email,
                password_hash,
                role
            )
            VALUES (?, ?, ?, ?)
        """, (name, email, password_hash, role))

    connection.commit()
    connection.close()

    class TemporaryConfig(TestConfig):

        DATABASE = str(database_path)

    application = create_app(TemporaryConfig)

    yield application


@pytest.fixture
def client(app):

    return app.test_client()


def login_as(client, role):

    emails = {
        "admin": "admin@test.com",
        "organizer": "organizer@test.com",
        "student": "student@test.com"
    }

    return client.post("/auth/login", data={
        "email": emails[role],
        "password": "password123"
    })


def test_organizer_can_access_analytics_dashboard(client):

    login_as(client, "organizer")

    response = client.get("/analytics/dashboard")

    assert response.status_code == 200

    assert b"Analytics Dashboard" in response.data


def test_admin_can_access_analytics_dashboard(client):

    login_as(client, "admin")

    response = client.get("/analytics/dashboard")

    assert response.status_code == 200

    assert b"Analytics Dashboard" in response.data


def test_student_cannot_access_analytics_dashboard(client):

    login_as(client, "student")

    response = client.get("/analytics/dashboard")

    assert response.status_code == 403


def test_unauthenticated_user_cannot_access_analytics_dashboard(client):

    response = client.get("/analytics/dashboard")

    assert response.status_code == 302


def test_dashboard_contains_analytics_components(client):

    login_as(client, "organizer")

    response = client.get("/analytics/dashboard")

    assert response.status_code == 200

    assert b"totalEvents" in response.data

    assert b"eventStatusChart" in response.data

    assert b"registrationChart" in response.data

    assert b"attendanceChart" in response.data

    assert b"Export CSV" in response.data


def test_dashboard_loads_analytics_javascript(client):

    login_as(client, "organizer")

    response = client.get("/analytics/dashboard")

    assert response.status_code == 200

    assert b"analytics.js" in response.data

    assert b"analytics.css" in response.data