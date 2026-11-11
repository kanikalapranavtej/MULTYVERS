import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from itsdangerous import URLSafeTimedSerializer
from werkzeug.security import generate_password_hash

from app import create_app
from app.config import Config


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_FILE = PROJECT_ROOT / "database" / "schema.sql"


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-attendance-secret"
    WTF_CSRF_ENABLED = False


@pytest.fixture
def app(tmp_path):
    database_path = tmp_path / "test_attendance.db"

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


@pytest.fixture
def registration_id(app, event_id):
    with sqlite3.connect(app.config["DATABASE"]) as connection:
        cursor = connection.execute("""
            INSERT INTO registrations (user_id, event_id, status)
            VALUES (?, ?, 'confirmed')
        """, (2, event_id))

        return cursor.lastrowid


def make_token(app, event_id):
    serializer = URLSafeTimedSerializer(
        app.config["SECRET_KEY"],
        salt="multyvers-event-attendance-v1"
    )

    return serializer.dumps({
        "event_id": event_id,
        "purpose": "attendance"
    })


def test_organizer_can_generate_event_qr(client, event_id):
    login_as(client, "organizer")

    response = client.get(
        f"/api/events/{event_id}/attendance/qr"
    )

    assert response.status_code == 200
    assert response.mimetype == "image/png"
    assert response.data.startswith(b"\x89PNG")


def test_admin_can_generate_event_qr(client, event_id):
    login_as(client, "admin")

    response = client.get(
        f"/api/events/{event_id}/attendance/qr"
    )

    assert response.status_code == 200
    assert response.mimetype == "image/png"


def test_student_cannot_generate_event_qr(client, event_id):
    login_as(client, "student")

    response = client.get(
        f"/api/events/{event_id}/attendance/qr"
    )

    assert response.status_code == 403


def test_invalid_qr_token_is_rejected(client, app, event_id):
    login_as(client, "student")

    response = client.post(
        "/api/attendance/mark",
        json={"token": "invalid-token"}
    )

    assert response.status_code == 400


def test_registered_student_can_mark_attendance(
    client, app, event_id, registration_id
):
    login_as(client, "student")

    token = make_token(app, event_id)

    response = client.post(
        "/api/attendance/mark",
        json={"token": token}
    )

    assert response.status_code == 201
    assert response.get_json()["status"] == "present"


def test_unregistered_student_cannot_mark_attendance(
    client, app, event_id
):
    login_as(client, "student")

    token = make_token(app, event_id)

    response = client.post(
        "/api/attendance/mark",
        json={"token": token}
    )

    assert response.status_code == 403


def test_cancelled_registration_cannot_mark_attendance(
    client, app, event_id, registration_id
):
    with sqlite3.connect(app.config["DATABASE"]) as connection:
        connection.execute("""
            UPDATE registrations
            SET status = 'cancelled'
            WHERE registration_id = ?
        """, (registration_id,))

    login_as(client, "student")

    token = make_token(app, event_id)

    response = client.post(
        "/api/attendance/mark",
        json={"token": token}
    )

    assert response.status_code == 403


def test_duplicate_attendance_is_rejected(
    client, app, event_id, registration_id
):
    login_as(client, "student")

    token = make_token(app, event_id)

    first = client.post(
        "/api/attendance/mark",
        json={"token": token}
    )

    second = client.post(
        "/api/attendance/mark",
        json={"token": token}
    )

    assert first.status_code == 201
    assert second.status_code == 409


def test_organizer_can_view_attendance_report(
    client, app, event_id, registration_id
):
    with sqlite3.connect(app.config["DATABASE"]) as connection:
        connection.execute("""
            INSERT INTO attendance (
                registration_id, event_id, user_id, marked_by, method
            )
            VALUES (?, ?, ?, ?, 'qr')
        """, (registration_id, event_id, 2, 2))

    login_as(client, "organizer")

    response = client.get(
        f"/api/events/{event_id}/attendance"
    )

    assert response.status_code == 200
    assert response.get_json()["count"] == 1


def test_other_organizer_cannot_view_attendance(
    client, event_id
):
    login_as(client, "other")

    response = client.get(
        f"/api/events/{event_id}/attendance"
    )

    assert response.status_code == 403

def test_organizer_can_export_attendance_csv(
    client, app, event_id, registration_id
):
    with sqlite3.connect(app.config["DATABASE"]) as connection:
        connection.execute("""
            INSERT INTO attendance (
                registration_id, event_id, user_id, marked_by, method
            )
            VALUES (?, ?, ?, ?, 'qr')
        """, (registration_id, event_id, 2, 2))

    login_as(client, "organizer")

    response = client.get(
        f"/api/events/{event_id}/attendance/export"
    )

    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert "attachment" in response.headers["Content-Disposition"]

    content = response.data.decode("utf-8-sig")

    assert "Student Name" in content
    assert "student@test.com" in content
    assert "Test Student" in content
    assert "qr" in content


def test_admin_can_export_attendance_csv(client, event_id):
    login_as(client, "admin")

    response = client.get(
        f"/api/events/{event_id}/attendance/export"
    )

    assert response.status_code == 200


def test_other_organizer_cannot_export_attendance_csv(
    client, event_id
):
    login_as(client, "other")

    response = client.get(
        f"/api/events/{event_id}/attendance/export"
    )

    assert response.status_code == 403


def test_student_cannot_export_attendance_csv(client, event_id):
    login_as(client, "student")

    response = client.get(
        f"/api/events/{event_id}/attendance/export"
    )

    assert response.status_code == 403


def test_nonexistent_event_attendance_export_returns_404(client):
    login_as(client, "admin")

    response = client.get(
        "/api/events/999/attendance/export"
    )

    assert response.status_code == 404