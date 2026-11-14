import sqlite3
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.config import Config


ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "database" / "schema.sql"


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "category-test-secret"
    WTF_CSRF_ENABLED = False


@pytest.fixture
def app(tmp_path):
    database_path = tmp_path / "categories.db"
    connection = sqlite3.connect(database_path)
    connection.executescript(SCHEMA.read_text(encoding="utf-8"))
    password_hash = generate_password_hash("password123")
    connection.executemany(
        "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
        [
            ("Admin", "admin@test.com", password_hash, "admin"),
            ("Student", "student@test.com", password_hash, "student"),
        ],
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


def login(client, email="admin@test.com"):
    return client.post("/auth/login", data={
        "email": email,
        "password": "password123",
    })


def test_admin_can_open_category_management(client):
    login(client)
    response = client.get("/admin/categories")
    assert response.status_code == 200
    assert b"Category Management" in response.data


def test_admin_can_create_and_edit_category(client, app):
    login(client)
    response = client.post("/admin/categories", data={
        "action": "create",
        "category_name": "Technical",
        "description": "Technical campus events",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Technical" in response.data

    with sqlite3.connect(app.config["DATABASE"]) as db:
        category_id = db.execute(
            "SELECT category_id FROM categories WHERE category_name='Technical'"
        ).fetchone()[0]

    client.post("/admin/categories", data={
        "action": "update",
        "category_id": category_id,
        "category_name": "Technology",
        "description": "Technology events",
    })

    with sqlite3.connect(app.config["DATABASE"]) as db:
        row = db.execute(
            "SELECT category_name, description FROM categories WHERE category_id=?",
            (category_id,),
        ).fetchone()
    assert row == ("Technology", "Technology events")


def test_category_in_use_cannot_be_deleted(client, app):
    login(client)
    with sqlite3.connect(app.config["DATABASE"]) as db:
        db.execute(
            "INSERT INTO categories (category_name) VALUES ('Sports')"
        )
        category_id = db.execute(
            "SELECT category_id FROM categories WHERE category_name='Sports'"
        ).fetchone()[0]
        db.execute(
            """INSERT INTO venues (venue_name, location, capacity)
               VALUES ('Ground', 'Campus', 500)"""
        )
        venue_id = db.execute(
            "SELECT venue_id FROM venues WHERE venue_name='Ground'"
        ).fetchone()[0]
        db.execute(
            """INSERT INTO events
               (title, organizer_id, category_id, venue_id, starts_at, ends_at,
                registration_deadline, capacity, status)
               VALUES ('Sports Day', 1, ?, ?, '2030-01-02T10:00:00',
                       '2030-01-02T12:00:00', '2030-01-01T10:00:00', 100, 'pending')""",
            (category_id, venue_id),
        )
        db.commit()

    client.post("/admin/categories", data={
        "action": "delete",
        "category_id": category_id,
    }, follow_redirects=True)

    with sqlite3.connect(app.config["DATABASE"]) as db:
        exists = db.execute(
            "SELECT 1 FROM categories WHERE category_id=?",
            (category_id,),
        ).fetchone()
    assert exists is not None


def test_student_cannot_access_category_management(client):
    login(client, "student@test.com")
    assert client.get("/admin/categories").status_code == 403
