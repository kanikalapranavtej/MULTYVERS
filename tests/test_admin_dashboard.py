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
    database_path = tmp_path / "test_admin_dashboard.db"

    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON")

    schema = SCHEMA_FILE.read_text(encoding="utf-8")
    connection.executescript(schema)

    password_hash = generate_password_hash("password123")

    users = [
        ("Test Admin", "admin@test.com", password_hash, "admin"),
        ("Test Organizer", "organizer@test.com", password_hash, "organizer"),
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


def login_as(client, role="admin"):
    email = f"{role}@test.com"

    return client.post("/auth/login", data={
        "email": email,
        "password": "password123"
    })


def create_event(app, title, status):
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
        2,
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


def test_admin_dashboard_returns_successfully(client):
    login_as(client)

    response = client.get("/admin/dashboard")

    assert response.status_code == 200

    data = response.get_json()

    assert data["dashboard"] == "Admin"
    assert data["role"] == "admin"
    assert data["message"] == "Welcome, Test Admin!"


def test_admin_dashboard_returns_user_statistics(client):
    login_as(client)

    response = client.get("/admin/dashboard")

    users = response.get_json()["statistics"]["users"]

    assert users["total_users"] == 3
    assert users["total_students"] == 1
    assert users["total_organizers"] == 1
    assert users["total_admins"] == 1


def test_admin_dashboard_returns_event_statistics(app, client):
    create_event(app, "Approved Event", "approved")
    create_event(app, "Pending Event", "pending")
    create_event(app, "Rejected Event", "rejected")
    create_event(app, "Cancelled Event", "cancelled")
    create_event(app, "Draft Event", "draft")

    login_as(client)

    response = client.get("/admin/dashboard")

    events = response.get_json()["statistics"]["events"]

    assert events["total_events"] == 5
    assert events["approved_events"] == 1
    assert events["pending_events"] == 1
    assert events["rejected_events"] == 1
    assert events["cancelled_events"] == 1
    assert events["draft_events"] == 1


def test_admin_dashboard_returns_registration_statistics(app, client):
    event_id = create_event(app, "Python Workshop", "approved")

    connection = sqlite3.connect(app.config["DATABASE"])

    # Create a second student for this test.
    password_hash = generate_password_hash("password123")

    connection.execute("""
        INSERT INTO users (name, email, password_hash, role)
        VALUES (?, ?, ?, ?)
    """, ("Second Student", "student2@test.com", password_hash, "student"))

    # Student 1 has a confirmed registration.
    connection.execute("""
        INSERT INTO registrations (user_id, event_id, status)
        VALUES (?, ?, ?)
    """, (3, event_id, "confirmed"))

    # Student 2 has a cancelled registration.
    connection.execute("""
        INSERT INTO registrations (user_id, event_id, status)
        VALUES (?, ?, ?)
    """, (4, event_id, "cancelled"))

    connection.commit()
    connection.close()

    login_as(client)

    response = client.get("/admin/dashboard")

    assert response.status_code == 200

    registrations = response.get_json()["statistics"]["registrations"]

    assert registrations["total_registrations"] == 2
    assert registrations["confirmed_registrations"] == 1
    assert registrations["cancelled_registrations"] == 1


def test_admin_dashboard_returns_recent_users(client):
    login_as(client)

    response = client.get("/admin/dashboard")

    recent_users = response.get_json()["statistics"]["recent_users"]

    assert len(recent_users) == 3
    assert recent_users[0]["email"] == "student@test.com"
    assert recent_users[-1]["email"] == "admin@test.com"


def test_admin_dashboard_returns_recent_events(app, client):
    create_event(app, "Python Workshop", "approved")
    create_event(app, "AI Seminar", "pending")

    login_as(client)

    response = client.get("/admin/dashboard")

    recent_events = response.get_json()["statistics"]["recent_events"]

    assert len(recent_events) == 2
    assert recent_events[0]["title"] == "AI Seminar"
    assert recent_events[0]["organizer_name"] == "Test Organizer"


def test_admin_dashboard_empty_statistics_return_zero(client):
    login_as(client)

    response = client.get("/admin/dashboard")

    data = response.get_json()["statistics"]

    assert data["events"]["total_events"] == 0
    assert data["events"]["approved_events"] == 0
    assert data["events"]["pending_events"] == 0

    assert data["registrations"]["total_registrations"] == 0
    assert data["registrations"]["confirmed_registrations"] == 0
    assert data["registrations"]["cancelled_registrations"] == 0


def test_admin_dashboard_requires_login(client):
    response = client.get("/admin/dashboard")

    assert response.status_code == 302
    assert "/auth/login" in response.location


def test_student_cannot_access_admin_dashboard(client):
    login_as(client, "student")

    response = client.get("/admin/dashboard")

    assert response.status_code == 403


def test_organizer_cannot_access_admin_dashboard(client):
    login_as(client, "organizer")

    response = client.get("/admin/dashboard")

    assert response.status_code == 403