from flask import Blueprint, jsonify, current_app

from app.database import get_db


main_bp = Blueprint("main", __name__)


@main_bp.route("/", methods=["GET"])
def home():

    return jsonify({
        "application": "MULTYVERS",
        "message": "Welcome to MULTYVERS!",
        "status": "running"
    })


@main_bp.route("/health", methods=["GET"])
def health():

    try:

        db = get_db()

        db.execute("SELECT 1").fetchone()

        tables = db.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """).fetchall()

        return jsonify({
            "application": "MULTYVERS",
            "status": "healthy",
            "database": "connected",
            "tables": [row["name"] for row in tables]
        }), 200

    except Exception:

        current_app.logger.exception(
            "Database health check failed"
        )

        return jsonify({
            "application": "MULTYVERS",
            "status": "unhealthy",
            "database": "disconnected"
        }), 503