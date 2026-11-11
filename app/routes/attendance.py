import csv
from io import StringIO
from flask import Response
from datetime import datetime, timezone
from io import BytesIO
import sqlite3

import qrcode
from flask import (
    Blueprint,
    current_app,
    jsonify,
    request,
    send_file
)
from flask_login import current_user
from itsdangerous import URLSafeTimedSerializer, BadSignature

from app.database import get_db
from app.decorators import role_required


attendance_bp = Blueprint(
    "attendance",
    __name__,
    url_prefix="/api"
)

QR_SALT = "multyvers-event-attendance-v1"

def safe_csv_value(value):
    """Prevent spreadsheet formula injection."""
    value = "" if value is None else str(value)

    if value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value

    return value


def get_token_serializer():
    return URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"],
        salt=QR_SALT
    )


def parse_event_time(value):
    parsed = datetime.fromisoformat(value)

    if parsed.tzinfo is None:
        parsed = parsed.astimezone()

    return parsed.astimezone(timezone.utc)


def event_access_allowed(event_id):
    """Check whether the current organizer owns the event or is admin."""

    db = get_db()

    event = db.execute("""
        SELECT event_id, organizer_id
        FROM events
        WHERE event_id = ?
    """, (event_id,)).fetchone()

    if event is None:
        return None, (jsonify({"error": "Event not found."}), 404)

    if current_user.role != "admin":
        if event["organizer_id"] != current_user.id:
            return None, (
                jsonify({"error": "You cannot access this event."}),
                403
            )

    return event, None


@attendance_bp.route(
    "/events/<int:event_id>/attendance/qr",
    methods=["GET"]
)
@role_required("organizer", "admin")
def generate_attendance_qr(event_id):
    """Generate a signed QR code for an approved event."""

    db = get_db()

    event, error = event_access_allowed(event_id)

    if error:
        return error

    event_status = db.execute("""
        SELECT status
        FROM events
        WHERE event_id = ?
    """, (event_id,)).fetchone()

    if event_status["status"] != "approved":
        return jsonify({
            "error": "QR codes can only be generated for approved events."
        }), 400

    token = get_token_serializer().dumps({
        "event_id": event_id,
        "purpose": "attendance"
    })

    qr_image = qrcode.make(token)

    image_buffer = BytesIO()
    qr_image.save(image_buffer, format="PNG")
    image_buffer.seek(0)

    return send_file(
        image_buffer,
        mimetype="image/png",
        download_name=f"event_{event_id}_attendance_qr.png"
    )


@attendance_bp.route("/attendance/mark", methods=["POST"])
@role_required("student")
def mark_attendance():
    """Mark attendance after validating QR token and registration."""

    data = request.get_json(silent=True) or {}
    token = data.get("token")

    if not isinstance(token, str) or not token.strip():
        return jsonify({
            "error": "A valid QR token is required."
        }), 400

    try:
        payload = get_token_serializer().loads(
    token,
    max_age=86400
)
    except BadSignature:
        return jsonify({
            "error": "Invalid or tampered QR code."
        }), 400

    if (
        not isinstance(payload, dict)
        or payload.get("purpose") != "attendance"
        or not isinstance(payload.get("event_id"), int)
        or isinstance(payload.get("event_id"), bool)
    ):
        return jsonify({
            "error": "Invalid QR code."
        }), 400

    event_id = payload["event_id"]
    db = get_db()

    try:
        # Serialize attendance writes and prevent duplicate submissions.
        db.execute("BEGIN IMMEDIATE")

        event = db.execute("""
            SELECT event_id, starts_at, ends_at, status
            FROM events
            WHERE event_id = ?
        """, (event_id,)).fetchone()

        if event is None or event["status"] != "approved":
            db.rollback()
            return jsonify({
                "error": "Event not found or not approved."
            }), 404

        now = datetime.now(timezone.utc)

        try:
            starts_at = parse_event_time(event["starts_at"])
            ends_at = parse_event_time(event["ends_at"])
        except (ValueError, TypeError):
            db.rollback()
            return jsonify({
                "error": "Invalid event schedule."
            }), 400

        if now < starts_at or now > ends_at:
            db.rollback()
            return jsonify({
                "error": "Attendance can only be marked during the event."
            }), 400

        registration = db.execute("""
            SELECT registration_id
            FROM registrations
            WHERE user_id = ?
              AND event_id = ?
              AND status = 'confirmed'
        """, (current_user.id, event_id)).fetchone()

        if registration is None:
            db.rollback()
            return jsonify({
                "error": "You must have a confirmed registration to mark attendance."
            }), 403

        existing = db.execute("""
            SELECT attendance_id
            FROM attendance
            WHERE event_id = ? AND user_id = ?
        """, (event_id, current_user.id)).fetchone()

        if existing:
            db.rollback()
            return jsonify({
                "error": "Attendance has already been marked."
            }), 409

        db.execute("""
            INSERT INTO attendance (
                registration_id,
                event_id,
                user_id,
                marked_by,
                method
            )
            VALUES (?, ?, ?, ?, 'qr')
        """, (
            registration["registration_id"],
            event_id,
            current_user.id,
            current_user.id
        ))

        db.commit()

        return jsonify({
            "message": "Attendance marked successfully.",
            "event_id": event_id,
            "status": "present"
        }), 201

    except sqlite3.IntegrityError:
        db.rollback()
        return jsonify({
            "error": "Attendance has already been marked."
        }), 409

    except Exception:
        db.rollback()
        raise


@attendance_bp.route(
    "/events/<int:event_id>/attendance",
    methods=["GET"]
)
@role_required("organizer", "admin")
def get_event_attendance(event_id):
    """View attendance records for an event."""

    db = get_db()

    event, error = event_access_allowed(event_id)

    if error:
        return error

    records = db.execute("""
        SELECT
            a.attendance_id,
            a.event_id,
            a.user_id,
            u.name AS student_name,
            u.email AS student_email,
            a.marked_at,
            a.method
        FROM attendance a
        JOIN users u ON a.user_id = u.user_id
        WHERE a.event_id = ?
        ORDER BY a.marked_at DESC
    """, (event_id,)).fetchall()

    return jsonify({
        "event_id": event_id,
        "attendance": [dict(row) for row in records],
        "count": len(records)
    }), 200

@attendance_bp.route(
    "/events/<int:event_id>/attendance/export",
    methods=["GET"]
)
@role_required("organizer", "admin")
def export_event_attendance(event_id):
    """Export event attendance records as CSV."""

    db = get_db()

    event, error = event_access_allowed(event_id)

    if error:
        return error

    records = db.execute("""
        SELECT
            u.name AS student_name,
            u.email AS student_email,
            a.marked_at,
            a.method
        FROM attendance a
        JOIN users u ON a.user_id = u.user_id
        WHERE a.event_id = ?
        ORDER BY a.marked_at DESC
    """, (event_id,)).fetchall()

    output = StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Student Name",
        "Email",
        "Attendance Time",
        "Attendance Method"
    ])

    for row in records:
        writer.writerow([
            safe_csv_value(row["student_name"]),
            safe_csv_value(row["student_email"]),
            safe_csv_value(row["marked_at"]),
            safe_csv_value(row["method"])
        ])

    return Response(
        "\ufeff" + output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition":
                f'attachment; filename="event_{event_id}_attendance.csv"'
        }
    )
