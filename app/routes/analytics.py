import csv
def safe_csv_value(value):
    """Prevent spreadsheet formula injection."""
    value = "" if value is None else str(value)

    if value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value

    return value
from io import StringIO
from flask import Response

from flask import Blueprint, jsonify
from flask_login import current_user

from app.database import get_db
from app.decorators import role_required

def safe_csv_value(value):
    """Prevent spreadsheet formula injection."""
    value = "" if value is None else str(value)

    if value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value

    return value

analytics_bp = Blueprint(
    "analytics",
    __name__,
    url_prefix="/api/analytics"
)


def get_event_scope():
    """Return SQL condition and parameters for the current user's events."""

    if current_user.role == "organizer":
        return "WHERE e.organizer_id = ?", [current_user.id]

    return "", []


@analytics_bp.route("/overview", methods=["GET"])
@role_required("organizer", "admin")
def analytics_overview():
    """Return event, registration and attendance analytics."""

    db = get_db()
    condition, params = get_event_scope()

    # Overall event statistics.
    event_stats = db.execute(f"""
        SELECT
            COUNT(*) AS total_events,
            COALESCE(SUM(CASE WHEN e.status = 'approved'
                THEN 1 ELSE 0 END), 0) AS approved_events,
            COALESCE(SUM(CASE WHEN e.status = 'pending'
                THEN 1 ELSE 0 END), 0) AS pending_events,
            COALESCE(SUM(CASE WHEN e.status = 'rejected'
                THEN 1 ELSE 0 END), 0) AS rejected_events,
            COALESCE(SUM(CASE WHEN e.status = 'cancelled'
                THEN 1 ELSE 0 END), 0) AS cancelled_events
        FROM events e
        {condition}
    """, params).fetchone()

    # Registration and attendance statistics.
    participation_stats = db.execute(f"""
        SELECT
            COUNT(CASE WHEN r.status = 'confirmed'
                THEN 1 END) AS confirmed_registrations,

            COUNT(CASE WHEN r.status = 'cancelled'
                THEN 1 END) AS cancelled_registrations,

            COUNT(a.attendance_id) AS total_attendance

        FROM events e

        LEFT JOIN registrations r
            ON e.event_id = r.event_id

        LEFT JOIN attendance a
            ON r.registration_id = a.registration_id

        {condition}
    """, params).fetchone()

    confirmed = participation_stats["confirmed_registrations"] or 0
    attendance = participation_stats["total_attendance"] or 0

    attendance_rate = (
        round((attendance / confirmed) * 100, 2)
        if confirmed else 0
    )

    # Event-wise performance.
    event_performance = db.execute(f"""
        SELECT
            e.event_id,
            e.title,
            e.status,
            e.capacity,

            COUNT(DISTINCT CASE
                WHEN r.status = 'confirmed'
                THEN r.registration_id
            END) AS confirmed_registrations,

            COUNT(DISTINCT a.attendance_id) AS attendance_count

        FROM events e

        LEFT JOIN registrations r
            ON e.event_id = r.event_id

        LEFT JOIN attendance a
            ON r.registration_id = a.registration_id

        {condition}

        GROUP BY e.event_id
        ORDER BY confirmed_registrations DESC, e.title ASC
    """, params).fetchall()

    performance = []

    for row in event_performance:
        item = dict(row)

        registered = item["confirmed_registrations"]
        present = item["attendance_count"]

        item["attendance_percentage"] = (
            round((present / registered) * 100, 2)
            if registered else 0
        )

        item["registration_percentage"] = (
            round((registered / item["capacity"]) * 100, 2)
            if item["capacity"] else 0
        )

        performance.append(item)

    # Category-wise event statistics.
    category_stats = db.execute(f"""
        SELECT
            c.category_name,
            COUNT(DISTINCT e.event_id) AS total_events,
            COUNT(DISTINCT CASE
                WHEN r.status = 'confirmed'
                THEN r.registration_id
            END) AS confirmed_registrations

        FROM events e

        JOIN categories c
            ON e.category_id = c.category_id

        LEFT JOIN registrations r
            ON e.event_id = r.event_id

        {condition}

        GROUP BY c.category_id
        ORDER BY confirmed_registrations DESC
    """, params).fetchall()

    return jsonify({
        "scope": current_user.role,
        "statistics": {
            **dict(event_stats),
            **dict(participation_stats),
            "attendance_percentage": attendance_rate
        },
        "event_performance": performance,
        "category_performance": [
            dict(row) for row in category_stats
        ]
    }), 200


@analytics_bp.route("/events/<int:event_id>", methods=["GET"])
@role_required("organizer", "admin")
def event_analytics(event_id):
    """Return detailed analytics for one event."""

    db = get_db()

    event = db.execute("""
        SELECT
            e.event_id,
            e.title,
            e.status,
            e.capacity,
            e.organizer_id
        FROM events e
        WHERE e.event_id = ?
    """, (event_id,)).fetchone()

    if event is None:
        return jsonify({"error": "Event not found."}), 404

    if (
        current_user.role == "organizer"
        and event["organizer_id"] != current_user.id
    ):
        return jsonify({
            "error": "You cannot access this event's analytics."
        }), 403

    stats = db.execute("""
        SELECT
            COUNT(CASE WHEN r.status = 'confirmed'
                THEN 1 END) AS confirmed_registrations,

            COUNT(CASE WHEN r.status = 'cancelled'
                THEN 1 END) AS cancelled_registrations,

            COUNT(a.attendance_id) AS attendance_count

        FROM events e

        LEFT JOIN registrations r
            ON e.event_id = r.event_id

        LEFT JOIN attendance a
            ON r.registration_id = a.registration_id

        WHERE e.event_id = ?
    """, (event_id,)).fetchone()

    confirmed = stats["confirmed_registrations"] or 0
    attendance = stats["attendance_count"] or 0
    capacity = event["capacity"]

    return jsonify({
        "event": {
            "event_id": event["event_id"],
            "title": event["title"],
            "status": event["status"],
            "capacity": capacity
        },
        "statistics": {
            **dict(stats),
            "attendance_percentage": (
                round(attendance / confirmed * 100, 2)
                if confirmed else 0
            ),
            "registration_percentage": (
                round(confirmed / capacity * 100, 2)
                if capacity else 0
            )
        }
    }), 200

@analytics_bp.route("/export", methods=["GET"])
@role_required("organizer", "admin")
def export_analytics():
    db = get_db()
    condition, params = get_event_scope()

    rows = db.execute(f"""
        SELECT
            e.event_id,
            e.title,
            e.status,
            e.capacity,

            COUNT(DISTINCT CASE
                WHEN r.status = 'confirmed'
                THEN r.registration_id
            END) AS registrations,

            COUNT(DISTINCT a.attendance_id) AS attendance

        FROM events e

        LEFT JOIN registrations r
            ON e.event_id = r.event_id

        LEFT JOIN attendance a
            ON r.registration_id = a.registration_id

        {condition}

        GROUP BY e.event_id
        ORDER BY e.starts_at DESC
    """, params).fetchall()

    output = StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Event ID",
        "Event Title",
        "Status",
        "Capacity",
        "Registrations",
        "Attendance",
        "Attendance Percentage"
    ])

    for row in rows:
        registered = row["registrations"]
        present = row["attendance"]

        percentage = (
            round(present / registered * 100, 2)
            if registered else 0
        )

        writer.writerow([
            row["event_id"],
            safe_csv_value(row["title"]),
            row["status"],
            row["capacity"],
            registered,
            present,
            percentage
        ])

    return Response(
        "\ufeff" + output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition":
                'attachment; filename="multyvers_analytics.csv"'
        }
    )