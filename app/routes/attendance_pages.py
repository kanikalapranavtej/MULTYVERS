from flask import Blueprint, render_template
from flask_login import current_user

from app.database import get_db
from app.decorators import role_required


attendance_pages_bp = Blueprint("attendance_pages", __name__)


@attendance_pages_bp.route("/organizer/attendance")
@role_required("organizer", "admin")
def organizer_attendance_page():

    db = get_db()

    if current_user.role == "admin":
        events = db.execute("""
            SELECT event_id, title, starts_at, ends_at, status
            FROM events
            WHERE status = 'approved'
            ORDER BY datetime(starts_at) DESC
        """).fetchall()

    else:
        events = db.execute("""
            SELECT event_id, title, starts_at, ends_at, status
            FROM events
            WHERE organizer_id = ?
              AND status = 'approved'
            ORDER BY datetime(starts_at) DESC
        """, (current_user.id,)).fetchall()

    return render_template(
        "organizer/attendance.html",
        events=events
    )


@attendance_pages_bp.route("/student/attendance")
@role_required("student")
def student_attendance_page():

    return render_template(
        "student/attendance_scanner.html"
    )