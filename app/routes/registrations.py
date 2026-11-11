from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_login import current_user

from app.database import get_db
from app.decorators import role_required


registrations_bp = Blueprint(
    "registrations",
    __name__,
    url_prefix="/api/registrations"
)


def get_current_time():
    """Return the current time as a timezone-aware datetime."""
    return datetime.now().astimezone()


def parse_datetime(value):
    """Parse an ISO-formatted datetime and normalize it to UTC."""
    parsed = datetime.fromisoformat(value)

    if parsed.tzinfo is None:
        parsed = parsed.astimezone()

    return parsed.astimezone(timezone.utc)


@registrations_bp.route("/", methods=["POST"])
@role_required("student")
def register_for_event():
    """Register the logged-in student for an approved event."""

    data = request.get_json(silent=True) or {}
    event_id = data.get("event_id")

    if event_id is None:
        return jsonify({
            "error": "Event ID is required."
        }), 400

    try:
        event_id = int(event_id)

        if event_id <= 0:
            raise ValueError

    except (ValueError, TypeError):
        return jsonify({
            "error": "Invalid event ID."
        }), 400

    db = get_db()

    try:
        # Start a write transaction to prevent capacity race conditions.
        db.execute("BEGIN IMMEDIATE")

        event = db.execute("""
            SELECT event_id, registration_deadline, capacity, status
            FROM events
            WHERE event_id = ?
        """, (event_id,)).fetchone()

        if event is None or event["status"] != "approved":
            db.rollback()
            return jsonify({
                "error": "Event not found."
            }), 404

        try:
            deadline = parse_datetime(event["registration_deadline"])
        except (ValueError, TypeError):
            db.rollback()
            return jsonify({
                "error": "Invalid event registration deadline."
            }), 400

        if get_current_time().astimezone(timezone.utc) > deadline:
            db.rollback()
            return jsonify({
                "error": "Registration deadline has passed."
            }), 400

        existing = db.execute("""
            SELECT registration_id, status
            FROM registrations
            WHERE user_id = ? AND event_id = ?
        """, (current_user.id, event_id)).fetchone()

        if existing and existing["status"] == "confirmed":
            db.rollback()
            return jsonify({
                "error": "You are already registered for this event."
            }), 409

        registered_count = db.execute("""
            SELECT COUNT(*) AS total
            FROM registrations
            WHERE event_id = ? AND status = 'confirmed'
        """, (event_id,)).fetchone()["total"]

        if registered_count >= event["capacity"]:
            db.rollback()
            return jsonify({
                "error": "Event registration capacity is full."
            }), 409

        if existing:
            # Reactivate a previously cancelled registration.
            db.execute("""
                UPDATE registrations
                SET status = 'confirmed',
                    registered_at = CURRENT_TIMESTAMP
                WHERE registration_id = ?
            """, (existing["registration_id"],))
        else:
            db.execute("""
                INSERT INTO registrations (user_id, event_id, status)
                VALUES (?, ?, 'confirmed')
            """, (current_user.id, event_id))

        db.commit()

        return jsonify({
            "message": "Successfully registered for the event.",
            "event_id": event_id,
            "status": "confirmed"
        }), 201

    except Exception:
        db.rollback()
        raise


@registrations_bp.route("/", methods=["GET"])
@role_required("student")
def get_my_registrations():
    """Return all registrations belonging to the logged-in student."""

    db = get_db()

    registrations = db.execute("""
        SELECT
            r.registration_id,
            r.event_id,
            r.status AS registration_status,
            r.registered_at,
            e.title,
            e.description,
            e.starts_at,
            e.ends_at,
            e.registration_deadline,
            c.category_name,
            v.venue_name,
            v.location
        FROM registrations r
        JOIN events e
            ON r.event_id = e.event_id
        JOIN categories c
            ON e.category_id = c.category_id
        JOIN venues v
            ON e.venue_id = v.venue_id
        WHERE r.user_id = ?
        ORDER BY r.registered_at DESC
    """, (current_user.id,)).fetchall()

    return jsonify({
        "registrations": [
            dict(row) for row in registrations
        ],
        "count": len(registrations)
    }), 200


@registrations_bp.route("/<int:event_id>", methods=["DELETE"])
@role_required("student")
def cancel_registration(event_id):
    """Cancel the logged-in student's registration for an event."""

    db = get_db()

    registration = db.execute("""
        SELECT registration_id, status
        FROM registrations
        WHERE user_id = ? AND event_id = ?
    """, (current_user.id, event_id)).fetchone()

    if registration is None:
        return jsonify({
            "error": "Registration not found."
        }), 404

    if registration["status"] == "cancelled":
        return jsonify({
            "error": "Registration is already cancelled."
        }), 400

    db.execute("""
        UPDATE registrations
        SET status = 'cancelled'
        WHERE registration_id = ?
    """, (registration["registration_id"],))

    db.commit()

    return jsonify({
        "message": "Registration cancelled successfully.",
        "event_id": event_id,
        "status": "cancelled"
    }), 200