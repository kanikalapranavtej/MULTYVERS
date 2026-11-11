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
    SECRET_KEY = "test-participants-secret"
    WTF_CSRF_ENABLED = False


@pytest.fixture
def app(tmp_path):
    database_path = tmp_path / "test_participants.db"

    connection = sqlite3.connect(database_path)
    connection.executescript(
        SCHEMA_FILE.read_text(encoding="utf-8")
    )

    password_hash = generate_password_hash("password123")

    users = [
        ("Organizer", "organizer@test.com", "organizer"),
        ("Student One", "student1@test.com", "student"),
        ("Student Two", "student2@test.com", "student"),
        ("Admin", "admin@test.com", "admin"),
        ("Other Organizer", "other@test.com", "organizer"),
    ]

    for name, email, role in users:
        connection.execute("""
            INSERT INTO users (name, email, password_hash, role)
            VALUES (?, ?, ?, ?)
        """, (name, email, password_hash, role))

    connection.execute("""
        INSERT INTO categories (category_name)
        VALUES ('Technology')
    """)

    connection.execute("""
        INSERT INTO venues (venue_name, location, capacity)
        VALUES ('Auditorium', 'Campus', 200)
    """)

    connection.execute("""
        INSERT INTO events (
            title, organizer_id, category_id, venue_id,
            starts_at, ends_at, registration_deadline,
            capacity, status
        )
        VALUES (
            'Python Workshop', 1, 1, 1,
            '2027-01-15T10:00:00',
            '2027-01-15T12:00:00',
            '2027-01-14T18:00:00',
            100, 'approved'
        )
    """)

    connection.execute("""
        INSERT INTO events (
            title, organizer_id, category_id, venue_id,
            starts_at, ends_at, registration_deadline,
            capacity, status
        )
        VALUES (
            'Other Workshop', 5, 1, 1,
            '2027-01-16T10:00:00',
            '2027-01-16T12:00:00',
            '2027-01-15T18:00:00',
            100, 'approved'
        )
    """)

    connection.execute("""
        INSERT INTO registrations (user_id, event_id, status)
        VALUES (2, 1, 'confirmed')
    """)

    connection.execute("""
        INSERT INTO registrations (user_id, event_id, status)
        VALUES (3, 1, 'cancelled')
    """)

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
        "student": "student1@test.com",
        "admin": "admin@test.com",
        "other": "other@test.com",
    }

    return client.post("/auth/login", data={
        "email": emails[role],
        "password": "password123"
    })


def test_organizer_can_view_event_participants(client):
    login_as(client, "organizer")

    response = client.get("/api/events/1/participants")

    assert response.status_code == 200

    data = response.get_json()
    assert data["event_id"] == 1
    assert data["event_title"] == "Python Workshop"
    assert len(data["participants"]) == 1
    assert data["participants"][0]["name"] == "Student One"


def test_admin_can_view_event_participants(client):
    login_as(client, "admin")

    response = client.get("/api/events/1/participants")

    assert response.status_code == 200
    assert response.get_json()["pagination"]["total"] == 1


def test_other_organizer_cannot_view_participants(client):
    login_as(client, "other")

    response = client.get("/api/events/1/participants")

    assert response.status_code == 403


def test_student_cannot_view_participants(client):
    login_as(client, "student")

    response = client.get("/api/events/1/participants")

    assert response.status_code == 403


def test_unauthenticated_user_cannot_view_participants(client):
    response = client.get("/api/events/1/participants")

    assert response.status_code == 302


def test_nonexistent_event_returns_404(client):
    login_as(client, "admin")

    response = client.get("/api/events/999/participants")

    assert response.status_code == 404


def test_cancelled_participants_can_be_filtered(client):
    login_as(client, "organizer")

    response = client.get(
        "/api/events/1/participants?status=cancelled"
    )

    assert response.status_code == 200

    data = response.get_json()
    assert data["pagination"]["total"] == 1
    assert data["participants"][0]["registration_status"] == "cancelled"


def test_all_registration_statuses_can_be_viewed(client):
    login_as(client, "organizer")

    response = client.get(
        "/api/events/1/participants?status=all"
    )

    assert response.status_code == 200
    assert response.get_json()["pagination"]["total"] == 2


def test_participants_can_be_searched_by_name(client):
    login_as(client, "organizer")

    response = client.get(
        "/api/events/1/participants?status=all&search=Student Two"
    )

    assert response.status_code == 200

    data = response.get_json()
    assert data["pagination"]["total"] == 1
    assert data["participants"][0]["name"] == "Student Two"


def test_invalid_registration_status_is_rejected(client):
    login_as(client, "organizer")

    response = client.get(
        "/api/events/1/participants?status=invalid"
    )

    assert response.status_code == 400


def test_invalid_pagination_is_rejected(client):
    login_as(client, "organizer")

    response = client.get(
        "/api/events/1/participants?page=0"
    )

    assert response.status_code == 400


def test_attendance_status_is_included(client, app):
    with sqlite3.connect(app.config["DATABASE"]) as connection:
        connection.execute("""
            INSERT INTO attendance (
                registration_id, event_id, user_id, marked_by, method
            )
            VALUES (1, 1, 2, 2, 'qr')
        """)

    login_as(client, "organizer")

    response = client.get("/api/events/1/participants")

    assert response.status_code == 200

    participant = response.get_json()["participants"][0]
    assert participant["attendance_status"] == "present"
    assert participant["attendance_time"] is not None

def test_organizer_can_export_participants_csv(client):
    login_as(client, "organizer")

    response = client.get(
        "/api/events/1/participants/export"
    )

    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert "attachment" in response.headers["Content-Disposition"]

    content = response.data.decode("utf-8-sig")

    assert "Student Name" in content
    assert "student1@test.com" in content
    assert "Student One" in content


def test_admin_can_export_participants_csv(client):
    login_as(client, "admin")

    response = client.get(
        "/api/events/1/participants/export"
    )

    assert response.status_code == 200


def test_other_organizer_cannot_export_participants(client):
    login_as(client, "other")

    response = client.get(
        "/api/events/1/participants/export"
    )

    assert response.status_code == 403


def test_student_cannot_export_participants(client):
    login_as(client, "student")

    response = client.get(
        "/api/events/1/participants/export"
    )

    assert response.status_code == 403


def test_participant_csv_supports_status_filter(client):
    login_as(client, "organizer")

    response = client.get(
        "/api/events/1/participants/export?status=cancelled"
    )

    assert response.status_code == 200

    content = response.data.decode("utf-8-sig")

    assert "Student Two" in content
    assert "Student One" not in content


def test_participant_csv_rejects_invalid_status(client):
    login_as(client, "organizer")

    response = client.get(
        "/api/events/1/participants/export?status=invalid"
    )

    assert response.status_code == 400


def test_participant_csv_prevents_formula_injection(client, app):
    with sqlite3.connect(app.config["DATABASE"]) as connection:
        connection.execute("""
            UPDATE users
            SET name = ?
            WHERE user_id = 2
        """, ("=HYPERLINK('https://example.com')",))

    login_as(client, "organizer")

    response = client.get(
        "/api/events/1/participants/export"
    )

    content = response.data.decode("utf-8-sig")

    assert "'=HYPERLINK" in content