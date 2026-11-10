import sqlite3
from pathlib import Path
import pytest


# Locate the SQL schema
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_FILE = PROJECT_ROOT / "database" / "schema.sql"


@pytest.fixture
def db():
    """Create a fresh temporary database for every test."""

    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")

    schema = SCHEMA_FILE.read_text(encoding="utf-8")
    connection.executescript(schema)

    yield connection

    connection.close()


def create_user(db, name, email, role="student"):
    """Insert a test user."""

    cursor = db.execute(
        """
        INSERT INTO users (name, email, password_hash, role)
        VALUES (?, ?, ?, ?)
        """,
        (name, email, "test_hash", role)
    )

    return cursor.lastrowid


def create_event(db, organizer_id):
    """Insert a test event."""

    category = db.execute(
        "INSERT INTO categories (category_name) VALUES (?)",
        ("Technical",)
    ).lastrowid

    venue = db.execute(
        """
        INSERT INTO venues (venue_name, location, capacity)
        VALUES (?, ?, ?)
        """,
        ("Main Auditorium", "Campus", 200)
    ).lastrowid

    cursor = db.execute(
        """
        INSERT INTO events (
            title, organizer_id, category_id, venue_id,
            starts_at, ends_at, registration_deadline, capacity
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "TechFest",
            organizer_id,
            category,
            venue,
            "2026-12-10T09:00:00",
            "2026-12-10T17:00:00",
            "2026-12-09T23:59:00",
            100
        )
    )

    return cursor.lastrowid


# TEST 1: Check whether all tables exist

def test_tables_created(db):

    cursor = db.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type = 'table'
        AND name NOT LIKE 'sqlite_%'
        """
    )

    tables = {row[0] for row in cursor.fetchall()}

    expected = {
        "users",
        "events",
        "categories",
        "venues",
        "registrations"
    }

    assert expected.issubset(tables)


# TEST 2: Valid user creation

def test_valid_user_creation(db):

    user_id = create_user(
        db, "Rahul", "rahul@example.com"
    )

    assert user_id > 0


# TEST 3: Duplicate email rejection

def test_duplicate_email_rejected(db):

    create_user(db, "Rahul", "rahul@example.com")

    with pytest.raises(sqlite3.IntegrityError):
        create_user(db, "Arun", "RAHUL@example.com")


# TEST 4: Invalid role rejection

def test_invalid_role_rejected(db):

    with pytest.raises(sqlite3.IntegrityError):
        create_user(
            db, "Rahul", "rahul@example.com", "guest"
        )


# TEST 5: Valid event creation

def test_valid_event_creation(db):

    organizer = create_user(
        db, "Organizer", "organizer@example.com", "organizer"
    )

    event_id = create_event(db, organizer)

    assert event_id > 0


# TEST 6: Invalid organizer rejection

def test_invalid_organizer_rejected(db):

    with pytest.raises(sqlite3.IntegrityError):
        create_event(db, 9999)


# TEST 7: Duplicate registration rejection

def test_duplicate_registration_rejected(db):

    student = create_user(
        db, "Rahul", "rahul@example.com"
    )

    organizer = create_user(
        db, "Organizer", "organizer@example.com", "organizer"
    )

    event = create_event(db, organizer)

    db.execute(
        """
        INSERT INTO registrations (user_id, event_id)
        VALUES (?, ?)
        """,
        (student, event)
    )

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO registrations (user_id, event_id)
            VALUES (?, ?)
            """,
            (student, event)
        )


# TEST 8: Invalid capacity rejection

def test_invalid_capacity_rejected(db):

    with pytest.raises(sqlite3.IntegrityError):

        db.execute(
            """
            INSERT INTO venues (venue_name, location, capacity)
            VALUES (?, ?, ?)
            """,
            ("Invalid Hall", "Campus", 0)
        )