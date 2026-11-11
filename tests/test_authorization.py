
from pathlib import Path
import sqlite3

import pytest

from app import create_app
from app.config import Config


# --------------------------------
# TEST CONFIGURATION
# --------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_FILE = PROJECT_ROOT / "database" / "schema.sql"


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret-key"
    WTF_CSRF_ENABLED = False


# --------------------------------
# APPLICATION FIXTURE
# --------------------------------

@pytest.fixture
def app(tmp_path):

    database_path = tmp_path / "test.db"

    connection = sqlite3.connect(database_path)

    schema = SCHEMA_FILE.read_text(encoding="utf-8")

    connection.executescript(schema)

    connection.close()

    class TemporaryConfig(TestConfig):
        DATABASE = str(database_path)

    application = create_app(TemporaryConfig)

    yield application


# --------------------------------
# TEST CLIENT FIXTURE
# --------------------------------

@pytest.fixture
def client(app):

    return app.test_client()

import sqlite3

import pytest
from werkzeug.security import generate_password_hash


PASSWORD = "TestPassword123"


def create_test_user(app, role):
    """
    Insert a test user with the specified role.
    """

    connection = sqlite3.connect(app.config["DATABASE"])

    connection.execute(
        """
        INSERT INTO users (name, email, password_hash, role)
        VALUES (?, ?, ?, ?)
        """,
        (
            f"Test {role}",
            f"{role}@test.com",
            generate_password_hash(PASSWORD),
            role
        )
    )

    connection.commit()
    connection.close()


def login_as(client, email):
    """
    Log in as a test user.
    """

    return client.post(
        "/auth/login",
        data={
            "email": email,
            "password": PASSWORD
        },
        follow_redirects=True
    )


# --------------------------------
# STUDENT AUTHORIZATION
# --------------------------------

def test_student_can_access_student_dashboard(app, client):

    create_test_user(app, "student")

    login_as(client, "student@test.com")

    response = client.get("/student/dashboard")

    assert response.status_code == 200
    assert response.get_json()["role"] == "student"


def test_student_cannot_access_admin_dashboard(app, client):

    create_test_user(app, "student")

    login_as(client, "student@test.com")

    response = client.get("/admin/dashboard")

    assert response.status_code == 403


# --------------------------------
# ORGANIZER AUTHORIZATION
# --------------------------------

def test_organizer_can_access_organizer_dashboard(app, client):

    create_test_user(app, "organizer")

    login_as(client, "organizer@test.com")

    response = client.get("/organizer/dashboard")

    assert response.status_code == 200
    assert response.get_json()["role"] == "organizer"


def test_organizer_cannot_access_student_dashboard(app, client):

    create_test_user(app, "organizer")

    login_as(client, "organizer@test.com")

    response = client.get("/student/dashboard")

    assert response.status_code == 403


# --------------------------------
# ADMIN AUTHORIZATION
# --------------------------------

def test_admin_can_access_admin_dashboard(app, client):

    create_test_user(app, "admin")

    login_as(client, "admin@test.com")

    response = client.get("/admin/dashboard")

    assert response.status_code == 200
    assert response.get_json()["role"] == "admin"


# --------------------------------
# UNAUTHENTICATED ACCESS
# --------------------------------

@pytest.mark.parametrize(
    "route",
    [
        "/student/dashboard",
        "/organizer/dashboard",
        "/admin/dashboard"
    ]
)
def test_unauthenticated_user_cannot_access_dashboards(client, route):

    response = client.get(route)

    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]
