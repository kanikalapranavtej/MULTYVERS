import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.config import Config


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_FILE = PROJECT_ROOT / "database" / "schema.sql"


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-attendance-pages-secret"
    WTF_CSRF_ENABLED = False


@pytest.fixture
def app(tmp_path):

    database_path = tmp_path / "test_attendance_pages.db"

    connection = sqlite3.connect(database_path)

    connection.executescript(
        SCHEMA_FILE.read_text(encoding="utf-8")
    )

    password_hash = generate_password_hash("password123")

    users = [
        ("Test Organizer", "organizer@test.com", "organizer"),
        ("Test Student", "student@test.com", "student"),
        ("Test Admin", "admin@test.com", "admin"),
        ("Other Organizer", "other@test.com", "organizer"),
    ]

    for name, email, role in users:
        connection.execute("""
            INSERT INTO users (name, email, password_hash, role)
            VALUES (?, ?, ?, ?)
        """, (name, email, password_hash, role))

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


@pytest.fixture
def event_id(app):

    now = datetime.now(timezone.utc)

    starts_at = (now - timedelta(hours=1)).isoformat()
    ends_at = (now + timedelta(hours=1)).isoformat()
    deadline = (now - timedelta(days=1)).isoformat()

    with sqlite3.connect(app.config["DATABASE"]) as connection:

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
            "Test Workshop",
            "Attendance testing event",
            1,
            1,
            1,
            starts_at,
            ends_at,
            deadline,
            100,
            "approved"
        ))

        return cursor.lastrowid


def login_as(client, role):

    emails = {
        "organizer": "organizer@test.com",
        "student": "student@test.com",
        "admin": "admin@test.com",
        "other": "other@test.com",
    }

    return client.post("/auth/login", data={
        "email": emails[role],
        "password": "password123"
    })


def test_organizer_can_access_attendance_page(client, event_id):

    login_as(client, "organizer")

    response = client.get("/organizer/attendance")

    assert response.status_code == 200
    assert b"QR Attendance" in response.data
    assert b"Test Workshop" in response.data


def test_admin_can_access_attendance_page(client, event_id):

    login_as(client, "admin")

    response = client.get("/organizer/attendance")

    assert response.status_code == 200
    assert b"QR Attendance" in response.data


def test_student_can_access_scanner_page(client):

    login_as(client, "student")

    response = client.get("/student/attendance")

    assert response.status_code == 200
    assert b"Scan Attendance" in response.data
    assert b"qr-reader" in response.data


def test_unauthenticated_user_cannot_access_organizer_page(client):

    response = client.get("/organizer/attendance")

    assert response.status_code == 302


def test_unauthenticated_user_cannot_access_student_page(client):

    response = client.get("/student/attendance")

    assert response.status_code == 302


def test_student_cannot_access_organizer_attendance_page(client):

    login_as(client, "student")

    response = client.get("/organizer/attendance")

    assert response.status_code == 403


def test_organizer_cannot_access_student_scanner_page(client):

    login_as(client, "organizer")

    response = client.get("/student/attendance")

    assert response.status_code == 403