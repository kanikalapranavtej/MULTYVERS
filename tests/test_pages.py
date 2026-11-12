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
    database_path = tmp_path / "test_pages.db"

    connection = sqlite3.connect(database_path)
    connection.executescript(
        SCHEMA_FILE.read_text(encoding="utf-8")
    )

    password_hash = generate_password_hash("password123")

    connection.execute(
        """
        INSERT INTO users (name, email, password_hash, role)
        VALUES (?, ?, ?, ?)
        """,
        ("Test Organizer", "organizer@test.com",
         password_hash, "organizer")
    )

    connection.execute(
        """
        INSERT INTO categories (category_name, description)
        VALUES (?, ?)
        """,
        ("Technology", "Technology events")
    )

    connection.execute(
        """
        INSERT INTO categories (category_name, description)
        VALUES (?, ?)
        """,
        ("Sports", "Sports events")
    )

    connection.execute(
        """
        INSERT INTO venues (venue_name, location, capacity)
        VALUES (?, ?, ?)
        """,
        ("Main Auditorium", "Campus", 200)
    )

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
def seed_events(app):
    """Create approved events for page tests."""

    with sqlite3.connect(app.config["DATABASE"]) as connection:

        events = [
            (
                "Python Workshop",
                "Learn Python programming",
                1,
                "2027-01-15T10:00:00",
                "2027-01-15T12:00:00",
                "2027-01-14T18:00:00",
                100,
            ),
            (
                "Football Tournament",
                "Inter-college football",
                2,
                "2027-02-10T09:00:00",
                "2027-02-10T17:00:00",
                "2027-02-09T18:00:00",
                150,
            ),
            (
                "AI Conference",
                "Artificial intelligence conference",
                1,
                "2027-03-20T10:00:00",
                "2027-03-20T16:00:00",
                "2027-03-19T18:00:00",
                120,
            ),
        ]

        for title, description, category_id, start, end, deadline, capacity in events:
            connection.execute(
                """
                INSERT INTO events (
                    title, description, organizer_id,
                    category_id, venue_id, starts_at,
                    ends_at, registration_deadline,
                    capacity, status
                )
                VALUES (?, ?, 1, ?, 1, ?, ?, ?, ?, 'approved')
                """,
                (
                    title, description, category_id,
                    start, end, deadline, capacity
                )
            )

        connection.commit()


def test_event_listing_loads(client, seed_events):
    response = client.get("/events")

    assert response.status_code == 200
    assert b"Explore Events" in response.data
    assert b"Python Workshop" in response.data


def test_event_detail_loads(client, seed_events):
    response = client.get("/events/1")

    assert response.status_code == 200
    assert b"Python Workshop" in response.data
    assert b"Main Auditorium" in response.data


def test_nonexistent_event_returns_404(client):
    response = client.get("/events/999")

    assert response.status_code == 404


def test_unapproved_event_returns_404(client, app):
    with sqlite3.connect(app.config["DATABASE"]) as connection:
        connection.execute(
            """
            INSERT INTO events (
                title, description, organizer_id,
                category_id, venue_id, starts_at,
                ends_at, registration_deadline,
                capacity, status
            )
            VALUES (
                'Pending Event', 'Not approved', 1,
                1, 1, '2027-04-01T10:00:00',
                '2027-04-01T12:00:00',
                '2027-03-31T18:00:00', 100, 'pending'
            )
            """
        )
        connection.commit()

    response = client.get("/events/4")

    assert response.status_code == 404


def test_event_search_filters_results(client, seed_events):
    response = client.get("/events?search=Python")

    assert response.status_code == 200
    assert b"Python Workshop" in response.data
    assert b"Football Tournament" not in response.data


def test_category_filter_works(client, seed_events):
    response = client.get("/events?category_id=2")

    assert response.status_code == 200
    assert b"Football Tournament" in response.data
    assert b"Python Workshop" not in response.data


def test_date_filters_work(client, seed_events):
    response = client.get(
        "/events?start_date=2027-02-01&end_date=2027-02-28"
    )

    assert response.status_code == 200
    assert b"Football Tournament" in response.data
    assert b"Python Workshop" not in response.data


def test_invalid_date_is_rejected(client):
    response = client.get("/events?start_date=invalid-date")

    assert response.status_code == 400


def test_invalid_date_range_is_rejected(client):
    response = client.get(
        "/events?start_date=2027-03-01&end_date=2027-01-01"
    )

    assert response.status_code == 400


def test_invalid_sort_is_rejected(client):
    response = client.get("/events?sort=invalid")

    assert response.status_code == 400


def test_latest_sort_loads(client, seed_events):
    response = client.get("/events?sort=latest")

    assert response.status_code == 200


def test_popular_sort_loads(client, seed_events):
    response = client.get("/events?sort=popular")

    assert response.status_code == 200


def test_pagination_loads(client, app):
    with sqlite3.connect(app.config["DATABASE"]) as connection:
        for number in range(12):
            connection.execute(
                """
                INSERT INTO events (
                    title, description, organizer_id,
                    category_id, venue_id, starts_at,
                    ends_at, registration_deadline,
                    capacity, status
                )
                VALUES (?, ?, 1, 1, 1, ?, ?, ?, 100, 'approved')
                """,
                (
                    f"Test Event {number}",
                    "Pagination test",
                    "2027-05-01T10:00:00",
                    "2027-05-01T12:00:00",
                    "2027-04-30T18:00:00",
                )
            )

        connection.commit()

    response = client.get("/events?page=2")

    assert response.status_code == 200
    assert b"Test Event" in response.data


def test_invalid_page_is_rejected(client):
    response = client.get("/events?page=0")

    assert response.status_code == 400