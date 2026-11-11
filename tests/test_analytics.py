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
    database_path = tmp_path / "test_analytics.db"

    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(
        SCHEMA_FILE.read_text(encoding="utf-8")
    )

    password_hash = generate_password_hash("password123")

    users = [
        ("Test Admin", "admin@test.com", password_hash, "admin"),
        ("Test Organizer", "organizer@test.com", password_hash, "organizer"),
        ("Test Student", "student@test.com", password_hash, "student"),
        ("Second Organizer", "organizer2@test.com", password_hash, "organizer")
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


def login_as(client, role="organizer"):
    return client.post("/auth/login", data={
        "email": f"{role}@test.com",
        "password": "password123"
    })


def create_event(app, title, organizer_id=2, status="approved"):
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


def test_admin_can_export_all_event_analytics(app, client):
    create_event(app, "Python Workshop")
    create_event(app, "AI Seminar", organizer_id=4)

    login_as(client, "admin")

    response = client.get("/api/analytics/export")

    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert "attachment" in response.headers["Content-Disposition"]

    content = response.data.decode("utf-8-sig")

    assert "Event ID" in content
    assert "Event Title" in content
    assert "Python Workshop" in content
    assert "AI Seminar" in content


def test_organizer_can_export_own_event_analytics(app, client):
    create_event(app, "Organizer One Event")
    create_event(app, "Organizer Two Event", organizer_id=4)

    login_as(client, "organizer")

    response = client.get("/api/analytics/export")

    assert response.status_code == 200

    content = response.data.decode("utf-8-sig")

    assert "Organizer One Event" in content
    assert "Organizer Two Event" not in content


def test_analytics_export_contains_registration_and_attendance_counts(
    app, client
):
    event_id = create_event(app, "Python Workshop")

    connection = sqlite3.connect(app.config["DATABASE"])

    cursor = connection.execute("""
        INSERT INTO registrations (user_id, event_id, status)
        VALUES (?, ?, ?)
    """, (3, event_id, "confirmed"))

    registration_id = cursor.lastrowid

    connection.execute("""
        INSERT INTO attendance (
            registration_id, event_id, user_id, marked_by, method
        )
        VALUES (?, ?, ?, ?, ?)
    """, (registration_id, event_id, 3, 2, "qr"))

    connection.commit()
    connection.close()

    login_as(client, "organizer")

    response = client.get("/api/analytics/export")

    assert response.status_code == 200

    content = response.data.decode("utf-8-sig")

    assert "Registrations" in content
    assert "Attendance" in content
    assert "1" in content


def test_analytics_export_prevents_formula_injection(app, client):
    create_event(app, "=HYPERLINK('https://example.com')")

    login_as(client, "organizer")

    response = client.get("/api/analytics/export")

    assert response.status_code == 200

    content = response.data.decode("utf-8-sig")

    assert "'=HYPERLINK" in content


def test_student_cannot_export_analytics(client):
    login_as(client, "student")

    response = client.get("/api/analytics/export")

    assert response.status_code == 403


def test_analytics_export_requires_login(client):
    response = client.get("/api/analytics/export")

    assert response.status_code == 302
    assert "/auth/login" in response.location