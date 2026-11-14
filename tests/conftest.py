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
    SECRET_KEY = "multyvers-test-secret"
    WTF_CSRF_ENABLED = False


@pytest.fixture
def app(tmp_path):

    database_path = tmp_path / "multyvers_test.db"

    connection = sqlite3.connect(database_path)

    connection.executescript(
        SCHEMA.read_text(encoding="utf-8")
    )

    password_hash = generate_password_hash("password123")

    connection.executemany(
        """
        INSERT INTO users
        (name, email, password_hash, role)
        VALUES (?, ?, ?, ?)
        """,
        [
            ("Admin", "admin@test.com", password_hash, "admin"),
            ("Student", "student@test.com", password_hash, "student"),
        ]
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