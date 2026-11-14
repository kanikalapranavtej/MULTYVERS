import sqlite3
from pathlib import Path

import pytest
from werkzeug.security import check_password_hash, generate_password_hash

from app import create_app
from app.config import Config

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "database" / "schema.sql"


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    WTF_CSRF_ENABLED = False


@pytest.fixture
def app(tmp_path):
    database = tmp_path / "organizers.db"
    connection = sqlite3.connect(database)
    connection.executescript(SCHEMA.read_text(encoding="utf-8"))
    hashed = generate_password_hash("password123")
    connection.executemany(
        "INSERT INTO users (name,email,password_hash,role) VALUES (?,?,?,?)",
        [
            ("Admin", "admin@test.com", hashed, "admin"),
            ("Student", "student@test.com", hashed, "student"),
            ("Organizer", "organizer@test.com", hashed, "organizer"),
        ],
    )
    connection.commit()
    connection.close()

    class TemporaryConfig(TestConfig):
        DATABASE = str(database)

    application = create_app(TemporaryConfig)
    yield application


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, email="admin@test.com"):
    return client.post("/auth/login", data={"email": email, "password": "password123"})


def test_admin_can_open_organizer_management(client):
    login(client)
    response = client.get("/admin/organizers/")
    assert response.status_code == 200
    assert b"Organizer Management" in response.data
    assert b"organizer@test.com" in response.data


def test_admin_can_create_organizer(app, client):
    login(client)
    response = client.post("/admin/organizers/", data={
        "action": "create", "name": "New Organizer", "email": "new@university.edu", "password": "securepass123"
    }, follow_redirects=True)
    assert response.status_code == 200
    db = sqlite3.connect(app.config["DATABASE"])
    row = db.execute("SELECT name,email,role,password_hash,is_active FROM users WHERE email=?", ("new@university.edu",)).fetchone()
    db.close()
    assert row[:3] == ("New Organizer", "new@university.edu", "organizer")
    assert check_password_hash(row[3], "securepass123")
    assert row[4] == 1


def test_admin_can_edit_organizer(app, client):
    login(client)
    client.post("/admin/organizers/", data={
        "action": "edit", "organizer_id": 3, "name": "Updated Organizer", "email": "updated@test.com"
    })
    db = sqlite3.connect(app.config["DATABASE"])
    row = db.execute("SELECT name,email FROM users WHERE user_id=3").fetchone()
    db.close()
    assert row == ("Updated Organizer", "updated@test.com")


def test_admin_can_deactivate_and_reactivate_organizer(app, client):
    login(client)
    client.post("/admin/organizers/", data={"action": "deactivate", "organizer_id": 3})
    db = sqlite3.connect(app.config["DATABASE"])
    assert db.execute("SELECT is_active FROM users WHERE user_id=3").fetchone()[0] == 0
    db.close()
    client.post("/admin/organizers/", data={"action": "reactivate", "organizer_id": 3})
    db = sqlite3.connect(app.config["DATABASE"])
    assert db.execute("SELECT is_active FROM users WHERE user_id=3").fetchone()[0] == 1
    db.close()


def test_student_cannot_manage_organizers(client):
    login(client, "student@test.com")
    assert client.get("/admin/organizers/").status_code == 403


def test_deactivated_organizer_cannot_log_in(app, client):
    db = sqlite3.connect(app.config["DATABASE"])
    db.execute("UPDATE users SET is_active=0 WHERE user_id=3")
    db.commit()
    db.close()
    response = client.post("/auth/login", data={"email": "organizer@test.com", "password": "password123"})
    assert response.status_code == 200
    assert b"deactivated" in response.data.lower()


def test_existing_database_gets_active_column_migration(tmp_path):
    database = tmp_path / "legacy.db"
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE users (user_id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    connection.execute("INSERT INTO users (name,email,password_hash,role) VALUES ('Legacy','legacy@test.com','hash','organizer')")
    connection.commit()
    connection.close()

    class LegacyConfig(TestConfig):
        DATABASE = str(database)

    application = create_app(LegacyConfig)
    with application.app_context():
        from app.database import get_db
        row = get_db().execute("SELECT is_active FROM users WHERE email='legacy@test.com'").fetchone()
        assert row["is_active"] == 1


def test_public_organizer_request_starts_pending(app, client):
    response = client.post("/auth/organizer-request", data={
        "name": "Pending Organizer",
        "email": "pending@university.edu",
        "password": "securepass123",
        "confirm_password": "securepass123",
    }, follow_redirects=True)
    assert response.status_code == 200
    db = sqlite3.connect(app.config["DATABASE"])
    row = db.execute(
        "SELECT role, approval_status, is_active FROM users WHERE email=?",
        ("pending@university.edu",),
    ).fetchone()
    db.close()
    assert row == ("organizer", "pending", 1)


def test_pending_organizer_cannot_log_in_until_admin_approves(app, client):
    client.post("/auth/organizer-request", data={
        "name": "Pending Organizer",
        "email": "pending@university.edu",
        "password": "securepass123",
        "confirm_password": "securepass123",
    })
    denied = client.post("/auth/login", data={
        "email": "pending@university.edu", "password": "securepass123"
    })
    assert b"awaiting administrator approval" in denied.data

    login(client)
    db = sqlite3.connect(app.config["DATABASE"])
    organizer_id = db.execute(
        "SELECT user_id FROM users WHERE email=?", ("pending@university.edu",)
    ).fetchone()[0]
    db.close()
    client.post("/admin/organizers/", data={
        "action": "approve", "organizer_id": organizer_id
    })
    client.post("/auth/logout")
    approved = client.post("/auth/login", data={
        "email": "pending@university.edu", "password": "securepass123"
    })
    assert approved.status_code == 302
