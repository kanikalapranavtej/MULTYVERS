import csv
from io import StringIO
from flask import Response

from flask import Blueprint, jsonify, request

from app.database import get_db
from app.decorators import role_required
from flask_login import current_user

def safe_csv_value(value):
    """Prevent spreadsheet formula injection."""
    value = "" if value is None else str(value)

    if value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value

    return value

participants_bp = Blueprint(
    "participants",
    __name__,
    url_prefix="/api/events"
)


@participants_bp.route("/<int:event_id>/participants", methods=["GET"])
@role_required("organizer", "admin")
def get_event_participants(event_id):
    db = get_db()

    event = db.execute("""
        SELECT event_id, organizer_id, title
        FROM events
        WHERE event_id = ?
    """, (event_id,)).fetchone()

    if event is None:
        return jsonify({"error": "Event not found."}), 404

    if current_user.role != "admin":
        if event["organizer_id"] != current_user.id:
            return jsonify({
                "error": "You cannot view participants for this event."
            }), 403

    search = request.args.get("search", "").strip()
    status = request.args.get("status", "confirmed").strip().lower()

    if status not in ("confirmed", "cancelled", "all"):
        return jsonify({"error": "Invalid registration status."}), 400

    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))

        if page < 1 or per_page < 1 or per_page > 100:
            raise ValueError

    except (ValueError, TypeError):
        return jsonify({"error": "Invalid pagination values."}), 400

    conditions = ["r.event_id = ?"]
    params = [event_id]

    if status != "all":
        conditions.append("r.status = ?")
        params.append(status)

    if search:
        conditions.append("(u.name LIKE ? OR u.email LIKE ?)")
        search_term = f"%{search}%"
        params.extend([search_term, search_term])

    where_clause = " AND ".join(conditions)

    total = db.execute(f"""
        SELECT COUNT(*) AS total
        FROM registrations r
        JOIN users u ON u.user_id = r.user_id
        WHERE {where_clause}
    """, params).fetchone()["total"]

    offset = (page - 1) * per_page

    participants = db.execute(f"""
        SELECT
            r.registration_id,
            r.user_id,
            u.name,
            u.email,
            r.status AS registration_status,
            r.registered_at,
            CASE
                WHEN a.attendance_id IS NOT NULL THEN 'present'
                ELSE 'absent'
            END AS attendance_status,
            a.marked_at AS attendance_time
        FROM registrations r
        JOIN users u ON u.user_id = r.user_id
        LEFT JOIN attendance a
            ON a.registration_id = r.registration_id
        WHERE {where_clause}
        ORDER BY r.registered_at DESC
        LIMIT ? OFFSET ?
    """, params + [per_page, offset]).fetchall()

    return jsonify({
        "event_id": event_id,
        "event_title": event["title"],
        "participants": [dict(row) for row in participants],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page
        }
    }), 200

@participants_bp.route(
    "/<int:event_id>/participants/export",
    methods=["GET"]
)
@role_required("organizer", "admin")
def export_event_participants(event_id):
    db = get_db()

    event = db.execute("""
        SELECT event_id, organizer_id, title
        FROM events
        WHERE event_id = ?
    """, (event_id,)).fetchone()

    if event is None:
        return jsonify({"error": "Event not found."}), 404

    if (
        current_user.role != "admin"
        and event["organizer_id"] != current_user.id
    ):
        return jsonify({"error": "Access denied."}), 403

    status = request.args.get("status", "all").lower()

    if status not in ("confirmed", "cancelled", "all"):
        return jsonify({"error": "Invalid registration status."}), 400

    query = """
        SELECT
            u.name,
            u.email,
            r.status,
            r.registered_at,
            CASE
                WHEN a.attendance_id IS NOT NULL THEN 'Present'
                ELSE 'Absent'
            END AS attendance_status,
            a.marked_at
        FROM registrations r
        JOIN users u ON u.user_id = r.user_id
        LEFT JOIN attendance a
            ON a.registration_id = r.registration_id
        WHERE r.event_id = ?
    """

    params = [event_id]

    if status != "all":
        query += " AND r.status = ?"
        params.append(status)

    query += " ORDER BY r.registered_at DESC"

    rows = db.execute(query, params).fetchall()

    output = StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Student Name",
        "Email",
        "Registration Status",
        "Registration Date",
        "Attendance Status",
        "Attendance Time"
    ])

    for row in rows:
        writer.writerow([
            safe_csv_value(row["name"]),
            safe_csv_value(row["email"]),
            safe_csv_value(row["status"]),
            safe_csv_value(row["registered_at"]),
            safe_csv_value(row["attendance_status"]),
            safe_csv_value(row["marked_at"])
        ])

    return Response(
        "\ufeff" + output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition":
                f'attachment; filename="event_{event_id}_participants.csv"'
        }
    )