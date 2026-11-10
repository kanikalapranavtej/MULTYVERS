import sqlite3

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


def init_app(app):
    """Register database cleanup with Flask."""

    app.teardown_appcontext(close_db)