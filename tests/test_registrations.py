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
    database_path = tmp_path / "test_registrations.db"

    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON")

    schema = SCHEMA_FILE.read_text(encoding="utf-8")
    connection.executescript(schema)

    password_hash = generate_password_hash("password123")

    # Create organizer.
    connection.execute("""
        INSERT INTO users (name, email, password_hash, role)
        VALUES (?, ?, ?, ?)
    """, (
        "Test Organizer",
        "organizer@test.com",
        password_hash,
        "organizer"
    ))

    # Create student.
    connection.execute("""
        INSERT INTO users (name, email, password_hash, role)
        VALUES (?, ?, ?, ?)
    """, (
        "Test Student",
        "student@test.com",
        password_hash,
        "student"
    ))

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


def login_as(client, role="student"):
    email = (
        "student@test.com"
        if role == "student"
        else "organizer@test.com"
    )

    return client.post("/auth/login", data={
        "email": email,
        "password": "password123"
    })


@pytest.fixture
def approved_event(app):
    """Create an approved event for registration tests."""

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
        "Python Workshop",
        "Learn Python programming.",
        1,
        1,
        1,
        "2027-01-15T10:00:00",
        "2027-01-15T12:00:00",
        "2027-01-14T18:00:00",
        100,
        "approved"
    ))

    event_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return event_id


def test_student_can_register_for_approved_event(
    client, approved_event, app
):
    login_as(client)

    response = client.post(
        "/api/registrations/",
        json={"event_id": approved_event}
    )

    assert response.status_code == 201
    assert response.get_json()["status"] == "confirmed"

    with sqlite3.connect(app.config["DATABASE"]) as connection:
        registration = connection.execute("""
            SELECT status
            FROM registrations
            WHERE user_id = 2 AND event_id = ?
        """, (approved_event,)).fetchone()

    assert registration is not None
    assert registration[0] == "confirmed"


def test_student_cannot_register_twice(
    client, approved_event
):
    login_as(client)

    first_response = client.post(
        "/api/registrations/",
        json={"event_id": approved_event}
    )

    second_response = client.post(
        "/api/registrations/",
        json={"event_id": approved_event}
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_registration_rejects_missing_event_id(client):
    login_as(client)

    response = client.post(
        "/api/registrations/",
        json={}
    )

    assert response.status_code == 400


def test_registration_rejects_invalid_event_id(client):
    login_as(client)

    response = client.post(
        "/api/registrations/",
        json={"event_id": "invalid"}
    )

    assert response.status_code == 400


def test_student_cannot_register_for_nonexistent_event(client):
    login_as(client)

    response = client.post(
        "/api/registrations/",
        json={"event_id": 999999}
    )

    assert response.status_code == 404


def test_student_cannot_register_for_full_event(
    client, app, approved_event
):
    login_as(client)

    connection = sqlite3.connect(app.config["DATABASE"])

    try:
        connection.execute("""
            UPDATE events
            SET capacity = 1
            WHERE event_id = ?
        """, (approved_event,))

        # Another user has already taken the only available seat.
        connection.execute("""
            INSERT INTO registrations (user_id, event_id, status)
            VALUES (?, ?, 'confirmed')
        """, (1, approved_event))

        connection.commit()
    finally:
        connection.close()

    response = client.post(
        "/api/registrations/",
        json={"event_id": approved_event}
    )

    assert response.status_code == 409
    assert "capacity is full" in response.get_json()["error"]


def test_student_can_view_own_registrations(
    client, approved_event
):
    login_as(client)

    client.post(
        "/api/registrations/",
        json={"event_id": approved_event}
    )

    response = client.get("/api/registrations/")

    assert response.status_code == 200

    data = response.get_json()

    assert data["count"] == 1
    assert data["registrations"][0]["event_id"] == approved_event
    assert data["registrations"][0]["registration_status"] == "confirmed"


def test_student_can_cancel_registration(
    client, approved_event
):
    login_as(client)

    client.post(
        "/api/registrations/",
        json={"event_id": approved_event}
    )

    response = client.delete(
        f"/api/registrations/{approved_event}"
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "cancelled"


def test_cancelled_registration_can_be_reactivated(
    client, approved_event
):
    login_as(client)

    client.post(
        "/api/registrations/",
        json={"event_id": approved_event}
    )

    cancel_response = client.delete(
        f"/api/registrations/{approved_event}"
    )

    assert cancel_response.status_code == 200

    register_response = client.post(
        "/api/registrations/",
        json={"event_id": approved_event}
    )

    assert register_response.status_code == 201
    assert register_response.get_json()["status"] == "confirmed"


def test_student_cannot_cancel_nonexistent_registration(client):
    login_as(client)

    response = client.delete("/api/registrations/999999")

    assert response.status_code == 404


def test_organizer_cannot_register_as_student(
    client, approved_event
):
    login_as(client, "organizer")

    response = client.post(
        "/api/registrations/",
        json={"event_id": approved_event}
    )

    assert response.status_code == 403


def test_unauthenticated_user_cannot_register(
    client, approved_event
):
    response = client.post(
        "/api/registrations/",
        json={"event_id": approved_event}
    )

    assert response.status_code == 302
    assert "/auth/login" in response.location
    
def test_student_cannot_register_after_deadline(
    client, app, approved_event
):
    login_as(client)

    connection = sqlite3.connect(app.config["DATABASE"])

    try:
        connection.execute("""
            UPDATE events
            SET registration_deadline = ?
            WHERE event_id = ?
        """, ("2000-01-01T00:00:00", approved_event))

        connection.commit()
    finally:
        connection.close()

    response = client.post(
        "/api/registrations/",
        json={"event_id": approved_event}
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == (
        "Registration deadline has passed."
    )


def test_student_cannot_register_for_pending_event(
    client, app, approved_event
):
    login_as(client)

    connection = sqlite3.connect(app.config["DATABASE"])

    try:
        connection.execute("""
            UPDATE events
            SET status = 'pending'
            WHERE event_id = ?
        """, (approved_event,))

        connection.commit()
    finally:
        connection.close()

    response = client.post(
        "/api/registrations/",
        json={"event_id": approved_event}
    )

    assert response.status_code == 404
    assert response.get_json()["error"] == "Event not found."