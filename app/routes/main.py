from flask import Blueprint, jsonify, current_app

from app.database import get_db
from app.decorators import role_required


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
        
# --------------------------------
# STUDENT DASHBOARD
# --------------------------------

@main_bp.route("/student/dashboard")
@role_required("student")
def student_dashboard():

    return jsonify({
        "dashboard": "Student",
        "message": "Welcome to the Student Dashboard!",
        "role": "student"
    }), 200


# --------------------------------
# ORGANIZER DASHBOARD
# --------------------------------

@main_bp.route("/organizer/dashboard")
@role_required("organizer")
def organizer_dashboard():

    return jsonify({
        "dashboard": "Organizer",
        "message": "Welcome to the Organizer Dashboard!",
        "role": "organizer"
    }), 200


# --------------------------------
# ADMIN DASHBOARD
# --------------------------------

@main_bp.route("/admin/dashboard")
@role_required("admin")
def admin_dashboard():

    return jsonify({
        "dashboard": "Admin",
        "message": "Welcome to the Admin Dashboard!",
        "role": "admin"
    }), 200        
        