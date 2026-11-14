import os
import sqlite3
from werkzeug.security import generate_password_hash

from flask import current_app, g


def get_db():
    """Get a database connection for the current request."""

    if "db" not in g:
        connection = sqlite3.connect(
            current_app.config["DATABASE"],
            timeout=10
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        g.db = connection

    return g.db


def close_db(error=None):
    """Close the database connection."""

    db = g.pop("db", None)
    if db is not None:
        db.close()


def migrate_organizer_account_status(app):
    """Safely add organizer account-state columns to legacy databases."""

    database_path = app.config["DATABASE"]
    connection = sqlite3.connect(database_path, timeout=10)
    try:
        table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'users'"
        ).fetchone()
        if table is None:
            return

        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(users)").fetchall()
        }
        if "is_active" not in columns:
            connection.execute(
                "ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1 "
                "CHECK (is_active IN (0, 1))"
            )
        if "approval_status" not in columns:
            # Existing organizer accounts are grandfathered as approved.
            connection.execute(
                "ALTER TABLE users ADD COLUMN approval_status TEXT NOT NULL DEFAULT 'approved' "
                "CHECK (approval_status IN ('pending', 'approved', 'rejected'))"
            )
        connection.commit()
    finally:
        connection.close()


def init_app(app):
    """Register database cleanup and apply safe schema migrations."""

    app.teardown_appcontext(close_db)
    migrate_organizer_account_status(app)
    ensure_default_admin(app)


def ensure_default_admin(app):
    """Create the single configured administrator when the database is initialized."""
    if app.config.get("TESTING"):
        return

    connection = sqlite3.connect(app.config["DATABASE"], timeout=10)
    try:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='users'"
        ).fetchone()
        if not exists:
            return

        # Keep the official administrator identity reserved.
        connection.execute(
            "DELETE FROM users WHERE role = 'admin' AND lower(email) != ?",
            ("admin@multyvers.in",),
        )
        admin_password = os.environ.get("MULTYVERS_ADMIN_PASSWORD", "password")
        admin = connection.execute(
            "SELECT user_id FROM users WHERE lower(email) = ?",
            ("admin@multyvers.in",),
        ).fetchone()
        if admin is None:
            connection.execute(
                """INSERT INTO users
                   (name, email, password_hash, role, is_active, approval_status)
                   VALUES (?, ?, ?, 'admin', 1, 'approved')""",
                ("MULTYVERS Administrator", "admin@multyvers.in",
                 generate_password_hash(admin_password)),
            )
        else:
            connection.execute(
                """UPDATE users
                   SET name = ?, role = 'admin', is_active = 1,
                       approval_status = 'approved', password_hash = ?
                   WHERE user_id = ?""",
                ("MULTYVERS Administrator", generate_password_hash(admin_password), admin[0]),
            )
        connection.commit()
    finally:
        connection.close()
