import sqlite3
from pathlib import Path

import pytest

from app import create_app
from app.config import Config
from app.models import User


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_FILE = PROJECT_ROOT / "database" / "schema.sql"


@pytest.fixture
def app(tmp_path):

    database_path = tmp_path / "test.db"

    connection = sqlite3.connect(database_path)

    schema = SCHEMA_FILE.read_text(encoding="utf-8")

    connection.executescript(schema)

    connection.execute(
        """
        INSERT INTO users
        (name, email, password_hash, role)
        VALUES (?, ?, ?, ?)
        """,
        (
            "Rahul",
            "rahul@example.com",
            "test_hash",
            "student"
        )
    )

    connection.commit()
    connection.close()

    class TestConfig(Config):
        TESTING = True
        SECRET_KEY = "test-secret"
        DATABASE = str(database_path)
        WTF_CSRF_ENABLED = False

    return create_app(TestConfig)


@pytest.fixture
def client(app):
    return app.test_client()


def test_get_user_by_id(app):

    with app.app_context():

        user = User.get_by_id(1)

        assert user is not None
        assert user.name == "Rahul"
        assert user.role == "student"


def test_get_user_by_email(app):

    with app.app_context():

        user = User.get_by_email("rahul@example.com")

        assert user is not None
        assert user.email == "rahul@example.com"


def test_user_not_found(app):

    with app.app_context():

        user = User.get_by_id(999)

        assert user is None


def test_invalid_user_id(app):

    with app.app_context():

        user = User.get_by_id("invalid")

        assert user is None