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

    database_path = tmp_path / "test_organizer_dashboard.db"

    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON")

    schema = SCHEMA_FILE.read_text(encoding="utf-8")
    connection.executescript(schema)

    password_hash = generate_password_hash("password123")

    # Create two organizers and one student.
    users = [
        ("Organizer One", "organizer1@test.com", password_hash, "organizer"),
        ("Organizer Two", "organizer2@test.com", password_hash, "organizer"),
        ("Test Student", "student@test.com", password_hash, "student")
    ]

    connection.executemany("""
        INSERT INTO users (name, email, password_hash, role)
        VALUES (?, ?, ?, ?)
    """, users)

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


def login_as(client, email="organizer1@test.com"):

    return client.post("/auth/login", data={
        "email": email,
        "password": "password123"
    })


def create_event(app, organizer_id, title, status):

    connection = sqlite3.connect(app.config["DATABASE"])

    cursor = connection.execute("""
        INSERT INTO events (
            title,
            description,
            organizer_id,
            category_id,
            venue_id,
            starts_at,
            ends_at,
            registration_deadline,
            capacity,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        title,
        "Test event description",
        organizer_id,
        1,
        1,
        "2027-01-15T10:00:00",
        "2027-01-15T12:00:00",
        "2027-01-14T18:00:00",
        100,
        status
    ))

    event_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return event_id


def test_organizer_dashboard_returns_profile(client):

    login_as(client)

    response = client.get("/organizer/dashboard")

    assert response.status_code == 200

    data = response.get_json()

    assert data["dashboard"] == "Organizer"
    assert data["organizer"]["name"] == "Organizer One"
    assert data["organizer"]["email"] == "organizer1@test.com"
    assert data["role"] == "organizer"


def test_organizer_dashboard_returns_event_statistics(
    app, client
):

    create_event(app, 1, "Python Workshop", "approved")
    create_event(app, 1, "AI Seminar", "pending")
    create_event(app, 1, "Robotics Event", "rejected")
    create_event(app, 1, "Music Festival", "cancelled")

    login_as(client)

    response = client.get("/organizer/dashboard")

    assert response.status_code == 200

    statistics = response.get_json()["statistics"]

    assert statistics["total_events"] == 4
    assert statistics["approved_events"] == 1
    assert statistics["pending_events"] == 1
    assert statistics["rejected_events"] == 1
    assert statistics["cancelled_events"] == 1
    assert statistics["total_registrations"] == 0


def test_organizer_dashboard_returns_registration_counts(
    app, client
):

    event_id = create_event(
        app, 1, "Python Workshop", "approved"
    )

    connection = sqlite3.connect(app.config["DATABASE"])

    # Student 3 registers for the event.
    connection.execute("""
        INSERT INTO registrations (user_id, event_id, status)
        VALUES (?, ?, ?)
    """, (3, event_id, "confirmed"))

    connection.commit()
    connection.close()

    login_as(client)

    response = client.get("/organizer/dashboard")

    data = response.get_json()

    assert data["statistics"]["total_registrations"] == 1
    assert data["events"][0]["confirmed_registrations"] == 1
    assert data["events"][0]["total_registrations"] == 1


def test_organizer_can_only_view_own_events(app, client):

    create_event(app, 1, "Organizer One Event", "approved")
    create_event(app, 2, "Organizer Two Event", "approved")

    login_as(client, "organizer1@test.com")

    response = client.get("/organizer/dashboard")

    assert response.status_code == 200

    events = response.get_json()["events"]

    event_titles = [event["title"] for event in events]

    assert "Organizer One Event" in event_titles
    assert "Organizer Two Event" not in event_titles


def test_organizer_dashboard_requires_login(client):

    response = client.get("/organizer/dashboard")

    assert response.status_code == 302
    assert "/auth/login" in response.location


def test_student_cannot_access_organizer_dashboard(client):

    login_as(client, "student@test.com")

    response = client.get("/organizer/dashboard")

    assert response.status_code == 403