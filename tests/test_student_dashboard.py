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
    SECRET_KEY = "test-secret-key"
    WTF_CSRF_ENABLED = False


@pytest.fixture
def app(tmp_path):
    database_path = tmp_path / "test_student_dashboard.db"

    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON")

    schema = SCHEMA_FILE.read_text(encoding="utf-8")
    connection.executescript(schema)

    password_hash = generate_password_hash("password123")

    connection.execute("""
        INSERT INTO users (name, email, password_hash, role)
        VALUES (?, ?, ?, ?)
    """, ("Test Organizer", "organizer@test.com",
          password_hash, "organizer"))

    connection.execute("""
        INSERT INTO users (name, email, password_hash, role)
        VALUES (?, ?, ?, ?)
    """, ("Test Student", "student@test.com",
          password_hash, "student"))

    connection.execute("""
        INSERT INTO categories (category_name, description)
        VALUES (?, ?)
    """, ("Technology", "Technology events"))

    connection.execute("""
        INSERT INTO venues (venue_name, location, capacity)
        VALUES (?, ?, ?)
    """, ("Main Auditorium", "Campus", 200))

    connection.commit()
    connection.close()

    class TemporaryConfig(TestConfig):
        DATABASE = str(database_path)

    application = create_app(TemporaryConfig)
    yield application


@pytest.fixture
def client(app):
    return app.test_client()


def login_as_student(client):
    return client.post("/auth/login", data={
        "email": "student@test.com",
        "password": "password123"
    })


def create_event(app, title, starts_at, status="approved"):
    connection = sqlite3.connect(app.config["DATABASE"])

    cursor = connection.execute("""
        INSERT INTO events (
            title, description, organizer_id,
            category_id, venue_id, starts_at,
            ends_at, registration_deadline,
            capacity, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        title,
        "Test event description",
        1,
        1,
        1,
        starts_at,
        starts_at[:10] + "T12:00:00",
        "2027-12-31T18:00:00",
        100,
        status
    ))

    event_id = cursor.lastrowid
    connection.commit()
    connection.close()

    return event_id


def create_registration(app, event_id, status="confirmed"):
    connection = sqlite3.connect(app.config["DATABASE"])

    connection.execute("""
        INSERT INTO registrations (user_id, event_id, status)
        VALUES (?, ?, ?)
    """, (2, event_id, status))

    connection.commit()
    connection.close()


def test_student_dashboard_returns_profile(client):
    login_as_student(client)

    response = client.get("/student/dashboard")

    assert response.status_code == 200

    data = response.get_json()

    assert data["role"] == "student"
    assert data["student"]["name"] == "Test Student"
    assert data["student"]["email"] == "student@test.com"
    assert data["student"]["user_id"] == 2


def test_student_dashboard_returns_registration_statistics(
    client, app
):
    login_as_student(client)

    upcoming_event = create_event(
        app, "Upcoming Workshop", "2027-01-15T10:00:00"
    )

    past_event = create_event(
        app, "Past Seminar", "2026-01-15T10:00:00"
    )

    cancelled_event = create_event(
        app, "Cancelled Event", "2027-02-15T10:00:00",
        status="cancelled"
    )

    create_registration(app, upcoming_event)
    create_registration(app, past_event)
    create_registration(app, cancelled_event, "cancelled")

    response = client.get("/student/dashboard")

    assert response.status_code == 200

    statistics = response.get_json()["statistics"]

    assert statistics["total_registrations"] == 3
    assert statistics["confirmed_registrations"] == 2
    assert statistics["cancelled_registrations"] == 1
    assert statistics["upcoming_events"] == 1
    assert statistics["past_events"] == 1


def test_student_dashboard_returns_registered_events(
    client, app
):
    login_as_student(client)

    event_id = create_event(
        app, "Python Workshop", "2027-01-15T10:00:00"
    )

    create_registration(app, event_id)

    response = client.get("/student/dashboard")

    assert response.status_code == 200

    data = response.get_json()

    assert len(data["registered_events"]) == 1
    assert data["registered_events"][0]["event_id"] == event_id
    assert data["registered_events"][0]["title"] == "Python Workshop"
    assert data["registered_events"][0]["registration_status"] == "confirmed"


def test_student_dashboard_requires_login(client):
    response = client.get("/student/dashboard")

    assert response.status_code == 302
    assert "/auth/login" in response.location


def test_student_dashboard_requires_student_role(client):
    client.post("/auth/login", data={
        "email": "organizer@test.com",
        "password": "password123"
    })

    response = client.get("/student/dashboard")

    assert response.status_code == 403