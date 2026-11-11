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
    database_path = tmp_path / "test_events.db"

    connection = sqlite3.connect(database_path)
    schema = SCHEMA_FILE.read_text(encoding="utf-8")
    connection.executescript(schema)

    # Create test users.
    password_hash = generate_password_hash("password123")

    connection.execute("""
        INSERT INTO users (name, email, password_hash, role)
        VALUES (?, ?, ?, ?)
    """, ("Test Organizer", "organizer@test.com", password_hash, "organizer"))

    connection.execute("""
        INSERT INTO users (name, email, password_hash, role)
        VALUES (?, ?, ?, ?)
    """, ("Test Student", "student@test.com", password_hash, "student"))
    
    connection.execute("""
    INSERT INTO users (name, email, password_hash, role)
    VALUES (?, ?, ?, ?)
    """, ("Test Admin", "admin@test.com", password_hash, "admin"))

    # Create a test category.
    connection.execute("""
        INSERT INTO categories (category_name, description)
        VALUES (?, ?)
    """, ("Technology", "Technology-related events"))

    # Create a test venue with capacity 200.
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
    email_by_role = {
        "organizer": "organizer@test.com",
        "student": "student@test.com",
        "admin": "admin@test.com"
    }

    if role not in email_by_role:
        raise ValueError(f"Unsupported test role: {role}")

    return client.post("/auth/login", data={
        "email": email_by_role[role],
        "password": "password123"
    })


def valid_event_data():
    return {
        "title": "Python Workshop",
        "description": "A beginner-friendly Python workshop.",
        "category_id": 1,
        "venue_id": 1,
        "starts_at": "2027-01-15T10:00:00",
        "ends_at": "2027-01-15T12:00:00",
        "registration_deadline": "2027-01-14T18:00:00",
        "capacity": 100
    }


def test_organizer_can_create_event(client, app):
    login_as(client, "organizer")

    response = client.post(
        "/api/events/",
        json=valid_event_data()
    )

    assert response.status_code == 201

    data = response.get_json()

    assert data["message"] == (
        "Event created successfully. Awaiting admin approval."
    )
    assert data["status"] == "pending"

    # Verify that the event was actually saved.
    with sqlite3.connect(app.config["DATABASE"]) as connection:
        connection.row_factory = sqlite3.Row

        event = connection.execute("""
            SELECT * FROM events WHERE event_id = ?
        """, (data["event_id"],)).fetchone()

    assert event is not None
    assert event["title"] == "Python Workshop"
    assert event["status"] == "pending"
    assert event["organizer_id"] == 1


def test_student_cannot_create_event(client):
    login_as(client, "student")

    response = client.post(
        "/api/events/",
        json=valid_event_data()
    )

    assert response.status_code == 403


def test_unauthenticated_user_cannot_create_event(client):
    response = client.post(
        "/api/events/",
        json=valid_event_data()
    )

    assert response.status_code == 302
    assert "/auth/login" in response.location


def test_missing_event_fields_are_rejected(client):
    login_as(client, "organizer")

    response = client.post(
        "/api/events/",
        json={"title": "Incomplete Event"}
    )

    assert response.status_code == 400
    assert "missing_fields" in response.get_json()


def test_invalid_event_dates_are_rejected(client):
    login_as(client, "organizer")

    data = valid_event_data()
    data["ends_at"] = "2027-01-15T09:00:00"

    response = client.post("/api/events/", json=data)

    assert response.status_code == 400


def test_nonexistent_category_is_rejected(client):
    login_as(client, "organizer")

    data = valid_event_data()
    data["category_id"] = 999

    response = client.post("/api/events/", json=data)

    assert response.status_code == 400


def test_nonexistent_venue_is_rejected(client):
    login_as(client, "organizer")

    data = valid_event_data()
    data["venue_id"] = 999

    response = client.post("/api/events/", json=data)

    assert response.status_code == 400


def test_event_capacity_cannot_exceed_venue_capacity(client):
    login_as(client, "organizer")

    data = valid_event_data()
    data["capacity"] = 250

    response = client.post("/api/events/", json=data)

    assert response.status_code == 400
    assert "exceeds venue capacity" in response.get_json()["error"]

def test_get_approved_event_details(client, app):
    # Log in as an organizer.
    login_as(client, "organizer")

    # Create an event.
    data = valid_event_data()
    response = client.post("/api/events/", json=data)

    assert response.status_code == 201

    event_id = response.get_json()["event_id"]

    # Change its status to approved for this test.
    connection = sqlite3.connect(app.config["DATABASE"])

    try:
        connection.execute("""
            UPDATE events
            SET status = 'approved'
            WHERE event_id = ?
        """, (event_id,))

        connection.commit()
    finally:
        connection.close()

    # Retrieve event details.
    response = client.get(f"/api/events/{event_id}")

    assert response.status_code == 200

    event = response.get_json()["event"]

    assert event["event_id"] == event_id
    assert event["title"] == data["title"]
    assert event["status"] == "approved"
    assert "category_name" in event
    assert "venue_name" in event
    assert "organizer_name" in event
    assert "registered_count" in event


def test_get_nonexistent_event_details(client):
    response = client.get("/api/events/999999")

    assert response.status_code == 404
    assert response.get_json()["error"] == "Event not found."


def test_pending_event_details_are_not_public(client):
    login_as(client, "organizer")

    data = valid_event_data()
    response = client.post("/api/events/", json=data)

    assert response.status_code == 201

    event_id = response.get_json()["event_id"]

    # Newly created events are pending.
    response = client.get(f"/api/events/{event_id}")

    assert response.status_code == 404
    assert response.get_json()["error"] == "Event not found."
    
def test_organizer_can_update_own_pending_event(client):
    login_as(client, "organizer")

    # Create an event.
    data = valid_event_data()
    response = client.post("/api/events/", json=data)

    assert response.status_code == 201
    event_id = response.get_json()["event_id"]

    # Update its title.
    updated_data = {
        "title": "Updated MULTYVERS Event"
    }

    response = client.put(
        f"/api/events/{event_id}",
        json=updated_data
    )

    assert response.status_code == 200
    assert response.get_json()["message"] == "Event updated successfully."
    
def test_update_event_rejects_empty_data(client):
    login_as(client, "organizer")

    data = valid_event_data()
    response = client.post("/api/events/", json=data)

    event_id = response.get_json()["event_id"]

    response = client.put(
        f"/api/events/{event_id}",
        json={}
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Invalid or empty update fields."

def test_update_nonexistent_event(client):
    login_as(client, "organizer")

    response = client.put(
        "/api/events/999999",
        json={"title": "Updated Event"}
    )

    assert response.status_code == 404
    assert response.get_json()["error"] == "Event not found."
    
def test_approved_event_cannot_be_updated(client, app):
    import sqlite3

    login_as(client, "organizer")

    data = valid_event_data()
    response = client.post("/api/events/", json=data)

    event_id = response.get_json()["event_id"]

    # Approve the event directly in the test database.
    connection = sqlite3.connect(app.config["DATABASE"])

    try:
        connection.execute("""
            UPDATE events
            SET status = 'approved'
            WHERE event_id = ?
        """, (event_id,))

        connection.commit()
    finally:
        connection.close()

    response = client.put(
        f"/api/events/{event_id}",
        json={"title": "Trying to update approved event"}
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Only pending events can be updated."

def test_get_events_returns_only_approved_events(client, app):
    login_as(client, "organizer")

    data = valid_event_data()
    response = client.post("/api/events/", json=data)

    assert response.status_code == 201
    event_id = response.get_json()["event_id"]

    # Approve the event for this test.
    with sqlite3.connect(app.config["DATABASE"]) as connection:
        connection.execute("""
            UPDATE events
            SET status = 'approved'
            WHERE event_id = ?
        """, (event_id,))

    response = client.get("/api/events/")

    assert response.status_code == 200

    result = response.get_json()
    assert len(result["events"]) == 1
    assert result["events"][0]["title"] == data["title"]


def test_get_events_supports_search(client, app):
    login_as(client, "organizer")

    data = valid_event_data()
    response = client.post("/api/events/", json=data)

    event_id = response.get_json()["event_id"]

    with sqlite3.connect(app.config["DATABASE"]) as connection:
        connection.execute("""
            UPDATE events
            SET status = 'approved'
            WHERE event_id = ?
        """, (event_id,))

    response = client.get("/api/events/?search=Python")

    assert response.status_code == 200
    assert len(response.get_json()["events"]) == 1


def test_get_events_rejects_invalid_pagination(client):
    response = client.get("/api/events/?page=0")

    assert response.status_code == 400


def test_get_events_supports_pagination(client):
    response = client.get("/api/events/?page=1&per_page=5")

    assert response.status_code == 200

    pagination = response.get_json()["pagination"]

    assert pagination["page"] == 1
    assert pagination["per_page"] == 5
    
def test_organizer_can_cancel_own_pending_event(client):
    login_as(client, "organizer")

    # Create an event.
    response = client.post(
        "/api/events/",
        json=valid_event_data()
    )

    assert response.status_code == 201
    event_id = response.get_json()["event_id"]

    # Cancel the event.
    response = client.patch(
        f"/api/events/{event_id}/cancel"
    )

    assert response.status_code == 200

    result = response.get_json()

    assert result["message"] == "Event cancelled successfully."
    assert result["status"] == "cancelled"


def test_organizer_cannot_cancel_nonexistent_event(client):
    login_as(client, "organizer")

    response = client.patch("/api/events/999999/cancel")

    assert response.status_code == 404
    assert response.get_json()["error"] == "Event not found."


def test_student_cannot_cancel_event(client):
    # Create an event as an organizer first.
    login_as(client, "organizer")

    response = client.post(
        "/api/events/",
        json=valid_event_data()
    )

    event_id = response.get_json()["event_id"]

    # Log out the organizer and log in as a student.
    client.post("/auth/logout")
    login_as(client, "student")

    response = client.patch(
        f"/api/events/{event_id}/cancel"
    )

    assert response.status_code == 403


def test_approved_event_cannot_be_cancelled_by_organizer(client, app):
    login_as(client, "organizer")

    response = client.post(
        "/api/events/",
        json=valid_event_data()
    )

    event_id = response.get_json()["event_id"]

    # Approve the event directly in the test database.
    with sqlite3.connect(app.config["DATABASE"]) as connection:
        connection.execute("""
            UPDATE events
            SET status = 'approved'
            WHERE event_id = ?
        """, (event_id,))

    response = client.patch(
        f"/api/events/{event_id}/cancel"
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == (
        "Only pending events can be cancelled."
    )


def test_unauthenticated_user_cannot_cancel_event(client):
    response = client.patch("/api/events/1/cancel")

    assert response.status_code == 302
    assert "/auth/login" in response.location


def test_organizer_cannot_update_another_organizers_event(client, app):
    # Create the event as the first organizer.
    login_as(client, "organizer")
    response = client.post("/api/events/", json=valid_event_data())
    assert response.status_code == 201
    event_id = response.get_json()["event_id"]

    # Create a second organizer directly in the test database.
    password_hash = generate_password_hash("password123")
    with sqlite3.connect(app.config["DATABASE"]) as connection:
        connection.execute("""
            INSERT INTO users (name, email, password_hash, role)
            VALUES (?, ?, ?, ?)
        """, ("Second Organizer", "second@test.com", password_hash, "organizer"))

    client.post("/auth/logout")
    response = client.post("/auth/login", data={
        "email": "second@test.com",
        "password": "password123"
    })
    assert response.status_code in (302, 200)

    response = client.put(
        f"/api/events/{event_id}",
        json={"title": "Unauthorized change"}
    )
    assert response.status_code == 403
    assert response.get_json()["error"] == (
        "You are not authorized to update this event."
    )


def test_update_event_rejects_invalid_capacity(client):
    login_as(client, "organizer")
    response = client.post("/api/events/", json=valid_event_data())
    event_id = response.get_json()["event_id"]

    response = client.put(
        f"/api/events/{event_id}",
        json={"capacity": -5}
    )
    assert response.status_code == 400


def test_update_event_rejects_invalid_date_order(client):
    login_as(client, "organizer")
    response = client.post("/api/events/", json=valid_event_data())
    event_id = response.get_json()["event_id"]

    response = client.put(
        f"/api/events/{event_id}",
        json={"ends_at": "2027-01-15T09:00:00"}
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == (
        "Event end time must be later than start time."
    )


def test_update_event_rejects_mixed_timezone_information(client):
    login_as(client, "organizer")
    response = client.post("/api/events/", json=valid_event_data())
    event_id = response.get_json()["event_id"]

    response = client.put(
        f"/api/events/{event_id}",
        json={"starts_at": "2027-01-15T10:00:00+05:30"}
    )
    assert response.status_code == 400
    assert "consistent timezone" in response.get_json()["error"]
    
def test_admin_can_approve_pending_event(client):
    login_as(client, "organizer")

    response = client.post(
        "/api/events/",
        json=valid_event_data()
    )

    assert response.status_code == 201

    event_id = response.get_json()["event_id"]

    # Log out the organizer and log in as admin.
    client.post("/auth/logout")
    login_as(client, "admin")

    response = client.patch(
        f"/api/events/{event_id}/approve"
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "approved"


def test_admin_can_reject_pending_event(client):
    login_as(client, "organizer")

    response = client.post(
        "/api/events/",
        json=valid_event_data()
    )

    event_id = response.get_json()["event_id"]

    client.post("/auth/logout")
    login_as(client, "admin")

    response = client.patch(
        f"/api/events/{event_id}/reject"
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "rejected"


def test_organizer_cannot_approve_event(client):
    login_as(client, "organizer")

    response = client.post(
        "/api/events/",
        json=valid_event_data()
    )

    event_id = response.get_json()["event_id"]

    response = client.patch(
        f"/api/events/{event_id}/approve"
    )

    assert response.status_code == 403


def test_student_cannot_reject_event(client):
    login_as(client, "organizer")

    response = client.post(
        "/api/events/",
        json=valid_event_data()
    )

    event_id = response.get_json()["event_id"]

    client.post("/auth/logout")
    login_as(client, "student")

    response = client.patch(
        f"/api/events/{event_id}/reject"
    )

    assert response.status_code == 403


def test_unauthenticated_user_cannot_approve_event(client):
    response = client.patch("/api/events/1/approve")

    assert response.status_code == 302
    assert "/auth/login" in response.location


def test_admin_cannot_approve_nonexistent_event(client):
    login_as(client, "admin")

    response = client.patch(
        "/api/events/999999/approve"
    )

    assert response.status_code == 404


def test_already_approved_event_cannot_be_rejected(client, app):
    login_as(client, "organizer")

    response = client.post(
        "/api/events/",
        json=valid_event_data()
    )

    event_id = response.get_json()["event_id"]

    # Approve the event directly for this test.
    with sqlite3.connect(app.config["DATABASE"]) as connection:
        connection.execute("""
            UPDATE events
            SET status = 'approved'
            WHERE event_id = ?
        """, (event_id,))

    client.post("/auth/logout")
    login_as(client, "admin")

    response = client.patch(
        f"/api/events/{event_id}/reject"
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == (
        "Only pending events can be reviewed."
    )


def test_overlapping_events_at_same_venue_are_rejected(client):
    login_as(client, "organizer")

    first = valid_event_data()
    response = client.post("/api/events/", json=first)
    assert response.status_code == 201

    second = valid_event_data()
    second["title"] = "Overlapping Workshop"
    second["starts_at"] = "2027-01-15T11:00:00"
    second["ends_at"] = "2027-01-15T13:00:00"

    response = client.post("/api/events/", json=second)

    assert response.status_code == 409
    assert "already booked" in response.get_json()["error"]


def test_non_overlapping_events_at_same_venue_are_allowed(client):
    login_as(client, "organizer")

    first = valid_event_data()
    response = client.post("/api/events/", json=first)
    assert response.status_code == 201

    second = valid_event_data()
    second["title"] = "Afternoon Workshop"
    second["starts_at"] = "2027-01-15T12:00:00"
    second["ends_at"] = "2027-01-15T14:00:00"

    response = client.post("/api/events/", json=second)

    assert response.status_code == 201


def test_updating_event_into_conflicting_time_is_rejected(client):
    login_as(client, "organizer")

    first = valid_event_data()
    response = client.post("/api/events/", json=first)
    assert response.status_code == 201

    second = valid_event_data()
    second["title"] = "Second Workshop"
    second["starts_at"] = "2027-01-15T13:00:00"
    second["ends_at"] = "2027-01-15T15:00:00"

    response = client.post("/api/events/", json=second)
    assert response.status_code == 201
    second_event_id = response.get_json()["event_id"]

    response = client.put(
        f"/api/events/{second_event_id}",
        json={
            "starts_at": "2027-01-15T11:00:00",
            "ends_at": "2027-01-15T14:00:00"
        }
    )

    assert response.status_code == 409
    assert "already booked" in response.get_json()["error"]


def test_admin_cannot_approve_event_with_venue_conflict(client, app):
    login_as(client, "organizer")

    first = valid_event_data()
    response = client.post("/api/events/", json=first)
    assert response.status_code == 201

    second = valid_event_data()
    second["title"] = "Second Workshop"
    second["starts_at"] = "2027-01-15T13:00:00"
    second["ends_at"] = "2027-01-15T15:00:00"

    response = client.post("/api/events/", json=second)
    assert response.status_code == 201
    second_event_id = response.get_json()["event_id"]

    # Simulate another booking occupying the second event's time.
    with sqlite3.connect(app.config["DATABASE"]) as connection:
        connection.execute("""
            UPDATE events
            SET starts_at = ?, ends_at = ?
            WHERE event_id = ?
        """, (
            "2027-01-15T11:00:00",
            "2027-01-15T13:00:00",
            second_event_id
        ))
        connection.commit()

    client.post("/auth/logout")
    login_as(client, "admin")

    response = client.patch(
        f"/api/events/{second_event_id}/approve"
    )

    assert response.status_code == 409
    assert "venue is already booked" in response.get_json()["error"]