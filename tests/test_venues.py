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
    database_path = tmp_path / "test_venues.db"

    connection = sqlite3.connect(database_path)
    schema = SCHEMA_FILE.read_text(encoding="utf-8")
    connection.executescript(schema)

    password_hash = generate_password_hash("password123")

    users = [
        ("Test Organizer", "organizer@test.com", "organizer"),
        ("Test Student", "student@test.com", "student"),
        ("Test Admin", "admin@test.com", "admin"),
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
    }

    return client.post("/auth/login", data={
        "email": emails[role],
        "password": "password123",
    })


def valid_venue_data():
    return {
        "venue_name": "Seminar Hall",
        "location": "Academic Block",
        "capacity": 150,
    }


def test_admin_can_create_venue(client, app):
    login_as(client, "admin")

    response = client.post(
        "/api/venues/",
        json=valid_venue_data()
    )

    assert response.status_code == 201

    data = response.get_json()
    assert data["message"] == "Venue created successfully."

    with sqlite3.connect(app.config["DATABASE"]) as connection:
        venue = connection.execute("""
            SELECT venue_name, location, capacity
            FROM venues WHERE venue_id = ?
        """, (data["venue_id"],)).fetchone()

    assert venue == ("Seminar Hall", "Academic Block", 150)


def test_admin_can_list_venues(client):
    login_as(client, "admin")

    response = client.get("/api/venues/")

    assert response.status_code == 200

    data = response.get_json()
    assert data["count"] == 1
    assert data["venues"][0]["venue_name"] == "Main Auditorium"


def test_admin_can_view_single_venue(client):
    login_as(client, "admin")

    response = client.get("/api/venues/1")

    assert response.status_code == 200
    assert response.get_json()["venue"]["venue_name"] == "Main Auditorium"


def test_nonexistent_venue_returns_404(client):
    login_as(client, "admin")

    response = client.get("/api/venues/999")

    assert response.status_code == 404


def test_admin_can_update_venue(client):
    login_as(client, "admin")

    response = client.put(
        "/api/venues/1",
        json={
            "venue_name": "Updated Auditorium",
            "capacity": 300,
        }
    )

    assert response.status_code == 200

    response = client.get("/api/venues/1")

    venue = response.get_json()["venue"]
    assert venue["venue_name"] == "Updated Auditorium"
    assert venue["capacity"] == 300
    assert venue["location"] == "Campus"


def test_duplicate_venue_name_is_rejected(client):
    login_as(client, "admin")

    response = client.post(
        "/api/venues/",
        json={
            "venue_name": "Main Auditorium",
            "location": "New Block",
            "capacity": 100,
        }
    )

    assert response.status_code == 409


@pytest.mark.parametrize("data", [
    {},
    {"venue_name": "Hall"},
    {"venue_name": "", "location": "Campus", "capacity": 100},
    {"venue_name": "Hall", "location": "", "capacity": 100},
    {"venue_name": "Hall", "location": "Campus", "capacity": 0},
    {"venue_name": "Hall", "location": "Campus", "capacity": -10},
    {"venue_name": "Hall", "location": "Campus", "capacity": "abc"},
    {"venue_name": "Hall", "location": "Campus", "capacity": 10.5},
])
def test_invalid_venue_data_is_rejected(client, data):
    login_as(client, "admin")

    response = client.post("/api/venues/", json=data)

    assert response.status_code == 400


def test_student_cannot_manage_venues(client):
    login_as(client, "student")

    response = client.get("/api/venues/")

    assert response.status_code == 403


def test_organizer_cannot_manage_venues(client):
    login_as(client, "organizer")

    response = client.post(
        "/api/venues/",
        json=valid_venue_data()
    )

    assert response.status_code == 403


def test_unauthenticated_user_cannot_manage_venues(client):
    response = client.get("/api/venues/")

    assert response.status_code == 302
    assert "/auth/login" in response.location


def test_admin_can_delete_unused_venue(client):
    login_as(client, "admin")

    response = client.delete("/api/venues/1")

    assert response.status_code == 200

    response = client.get("/api/venues/1")
    assert response.status_code == 404


def test_venue_with_events_cannot_be_deleted(client, app):
    login_as(client, "admin")

    with sqlite3.connect(app.config["DATABASE"]) as connection:
        connection.execute("""
            INSERT INTO events (
                title, description, organizer_id, category_id,
                venue_id, starts_at, ends_at,
                registration_deadline, capacity, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "Test Event",
            "Test description",
            1,
            1,
            1,
            "2027-01-15T10:00:00",
            "2027-01-15T12:00:00",
            "2027-01-14T18:00:00",
            100,
            "pending",
        ))

        connection.commit()

    response = client.delete("/api/venues/1")

    assert response.status_code == 409

# --------------------------------------------------
# VENUE AVAILABILITY TESTS
# --------------------------------------------------

def insert_test_event(
    app,
    status="approved",
    starts_at="2027-01-15T10:00:00",
    ends_at="2027-01-15T12:00:00",
    venue_id=1
):
    with sqlite3.connect(app.config["DATABASE"]) as connection:
        cursor = connection.execute("""
            INSERT INTO events (
                title, description, organizer_id, category_id,
                venue_id, starts_at, ends_at,
                registration_deadline, capacity, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "Test Event",
            "Testing venue availability",
            1,
            1,
            venue_id,
            starts_at,
            ends_at,
            "2027-01-14T18:00:00",
            100,
            status,
        ))

        connection.commit()
        return cursor.lastrowid


def availability_url(
    venue_id=1,
    starts_at="2027-01-15T10:00:00",
    ends_at="2027-01-15T12:00:00",
    exclude_event_id=None
):
    url = (
        f"/api/venues/availability?"
        f"venue_id={venue_id}"
        f"&starts_at={starts_at}"
        f"&ends_at={ends_at}"
    )

    if exclude_event_id is not None:
        url += f"&exclude_event_id={exclude_event_id}"

    return url


def test_organizer_can_check_venue_availability(client):
    login_as(client, "organizer")

    response = client.get(availability_url())

    assert response.status_code == 200
    assert response.get_json()["available"] is True
    assert response.get_json()["conflict_count"] == 0


def test_admin_can_check_venue_availability(client):
    login_as(client, "admin")

    response = client.get(availability_url())

    assert response.status_code == 200
    assert response.get_json()["available"] is True


@pytest.mark.parametrize("status", ["pending", "approved"])
def test_active_event_creates_venue_conflict(client, app, status):
    login_as(client, "organizer")

    insert_test_event(app, status=status)

    response = client.get(availability_url())

    data = response.get_json()

    assert response.status_code == 200
    assert data["available"] is False
    assert data["conflict_count"] == 1
    assert data["conflicts"][0]["status"] == status


@pytest.mark.parametrize("status", ["rejected", "cancelled"])
def test_inactive_event_does_not_create_venue_conflict(
    client, app, status
):
    login_as(client, "organizer")

    insert_test_event(app, status=status)

    response = client.get(availability_url())

    assert response.status_code == 200
    assert response.get_json()["available"] is True
    assert response.get_json()["conflict_count"] == 0


def test_adjacent_bookings_do_not_conflict(client, app):
    login_as(client, "organizer")

    insert_test_event(
        app,
        starts_at="2027-01-15T10:00:00",
        ends_at="2027-01-15T12:00:00"
    )

    response = client.get(availability_url(
        starts_at="2027-01-15T12:00:00",
        ends_at="2027-01-15T14:00:00"
    ))

    assert response.status_code == 200
    assert response.get_json()["available"] is True


def test_event_ending_after_booking_starts_creates_conflict(
    client, app
):
    login_as(client, "organizer")

    insert_test_event(app)

    response = client.get(availability_url(
        starts_at="2027-01-15T11:00:00",
        ends_at="2027-01-15T13:00:00"
    ))

    assert response.status_code == 200
    assert response.get_json()["available"] is False


def test_current_event_can_be_excluded_during_update(client, app):
    login_as(client, "organizer")

    event_id = insert_test_event(app)

    response = client.get(
        availability_url(exclude_event_id=event_id)
    )

    assert response.status_code == 200
    assert response.get_json()["available"] is True
    assert response.get_json()["conflict_count"] == 0


@pytest.mark.parametrize("url", [
    "/api/venues/availability",
    "/api/venues/availability?venue_id=abc&starts_at=2027-01-15T10:00:00&ends_at=2027-01-15T12:00:00",
    "/api/venues/availability?venue_id=1&starts_at=invalid&ends_at=2027-01-15T12:00:00",
    "/api/venues/availability?venue_id=1&starts_at=2027-01-15T12:00:00&ends_at=2027-01-15T10:00:00",
    "/api/venues/availability?venue_id=999&starts_at=2027-01-15T10:00:00&ends_at=2027-01-15T12:00:00",
])
def test_invalid_availability_requests_are_rejected(client, url):
    login_as(client, "organizer")

    response = client.get(url)

    assert response.status_code in (400, 404)


def test_student_cannot_check_venue_availability(client):
    login_as(client, "student")

    response = client.get(availability_url())

    assert response.status_code == 403


def test_unauthenticated_user_cannot_check_venue_availability(client):
    response = client.get(availability_url())

    assert response.status_code == 302
    assert "/auth/login" in response.location