from datetime import datetime
import sqlite3

from flask import Blueprint, request, jsonify
from flask_login import current_user

from app.database import get_db
from app.decorators import role_required


events_bp = Blueprint(
    "events",
    __name__,
    url_prefix="/api/events"
)


# --------------------------------------------------
# HELPER FUNCTIONS
# --------------------------------------------------

def parse_positive_integer(value):
    """
    Convert a positive integer or integer string to int.
    Reject booleans, floats, zero and negative numbers.
    """
    if isinstance(value, bool):
        raise ValueError("Boolean is not a valid integer.")

    if isinstance(value, int):
        result = value

    elif isinstance(value, str):
        value = value.strip()

        if not value or not value.isdecimal():
            raise ValueError("Invalid integer.")

        result = int(value)

    else:
        raise ValueError("Invalid integer type.")

    if result <= 0:
        raise ValueError("Value must be positive.")

    return result


def parse_event_datetime(value):
    """
    Parse an ISO 8601 datetime string.
    """
    if not isinstance(value, str):
        raise ValueError("Datetime must be text.")

    return datetime.fromisoformat(value)

def check_venue_conflict(
    db, venue_id, starts_at, ends_at, exclude_event_id=None
):
    """Return another active event if its venue booking overlaps."""

    query = """
        SELECT event_id, title, starts_at, ends_at
        FROM events
        WHERE venue_id = ?
          AND status IN ('pending', 'approved')
    """
    params = [venue_id]

    if exclude_event_id is not None:
        query += " AND event_id != ?"
        params.append(exclude_event_id)

    events = db.execute(query, params).fetchall()

    requested_start = starts_at.astimezone()
    requested_end = ends_at.astimezone()

    for event in events:
        existing_start = datetime.fromisoformat(
            event["starts_at"]
        ).astimezone()

        existing_end = datetime.fromisoformat(
            event["ends_at"]
        ).astimezone()

        if requested_start < existing_end and requested_end > existing_start:
            return event

    return None


# --------------------------------------------------
# 1. CREATE EVENT
# --------------------------------------------------

@events_bp.route("/", methods=["POST"])
@role_required("organizer")
def create_event():

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "error": "Request body must contain a valid JSON object."
        }), 400

    required_fields = [
        "title",
        "category_id",
        "venue_id",
        "starts_at",
        "ends_at",
        "registration_deadline",
        "capacity"
    ]

    missing_fields = [
        field for field in required_fields
        if field not in data or data[field] is None or data[field] == ""
    ]

    if missing_fields:
        return jsonify({
            "error": "Required fields are missing.",
            "missing_fields": missing_fields
        }), 400

    # Validate title
    title = data["title"]

    if not isinstance(title, str):
        return jsonify({
            "error": "Event title must be text."
        }), 400

    title = title.strip()

    if not title:
        return jsonify({
            "error": "Event title cannot be empty."
        }), 400

    # Validate description
    description = data.get("description", "")

    if not isinstance(description, str):
        return jsonify({
            "error": "Description must be text."
        }), 400

    # Validate numerical and datetime fields
    try:
        category_id = parse_positive_integer(data["category_id"])
        venue_id = parse_positive_integer(data["venue_id"])
        capacity = parse_positive_integer(data["capacity"])

        starts_at = parse_event_datetime(data["starts_at"])
        ends_at = parse_event_datetime(data["ends_at"])

        registration_deadline = parse_event_datetime(
            data["registration_deadline"]
        )

    except (ValueError, TypeError, OverflowError):
        return jsonify({
            "error": "Invalid category, venue, capacity or date format."
        }), 400

    # Ensure consistent timezone awareness
    date_values = [
        starts_at,
        ends_at,
        registration_deadline
    ]

    timezone_awareness = [
        value.utcoffset() is not None
        for value in date_values
    ]

    if len(set(timezone_awareness)) != 1:
        return jsonify({
            "error": "All event dates must use consistent timezone information."
        }), 400

    # Validate event duration
    if ends_at <= starts_at:
        return jsonify({
            "error": "Event end time must be later than start time."
        }), 400

    # Validate registration deadline
    if registration_deadline > starts_at:
        return jsonify({
            "error": "Registration deadline cannot be after event start."
        }), 400

    current_time = (
        datetime.now().astimezone()
        if timezone_awareness[0]
        else datetime.now()
    )

    if registration_deadline <= current_time:
        return jsonify({
            "error": "Registration deadline must be in the future."
        }), 400

    db = get_db()

    # Check category
    category = db.execute("""
        SELECT category_id
        FROM categories
        WHERE category_id = ?
    """, (category_id,)).fetchone()

    if category is None:
        return jsonify({
            "error": "Selected category does not exist."
        }), 400

    # Check venue
    venue = db.execute("""
        SELECT capacity
        FROM venues
        WHERE venue_id = ?
    """, (venue_id,)).fetchone()

    if venue is None:
        return jsonify({
            "error": "Selected venue does not exist."
        }), 400

    # Check venue capacity
    if capacity > venue["capacity"]:
        return jsonify({
            "error": "Event capacity exceeds venue capacity."
        }), 400

     # Check venue booking conflict
    conflict = check_venue_conflict(
        db, venue_id, starts_at, ends_at
    )

    if conflict:
        return jsonify({
            "error": "This venue is already booked during the selected time.",
            "conflicting_event_id": conflict["event_id"],
            "conflicting_event_title": conflict["title"]
        }), 409

    # Insert event
    try:
        cursor = db.execute("""
            INSERT INTO events (
                title,
                description,
                organizer_id,
                category_id,
                venue_id,
                starts_at,
                ends_at,
                registration_deadline,
                capacity,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
        """, (
            title,
            description,
            current_user.id,
            category_id,
            venue_id,
            starts_at.isoformat(),
            ends_at.isoformat(),
            registration_deadline.isoformat(),
            capacity
        ))

        db.commit()

        return jsonify({
            "message": "Event created successfully. Awaiting admin approval.",
            "event_id": cursor.lastrowid,
            "status": "pending"
        }), 201

    except sqlite3.IntegrityError:
        db.rollback()

        return jsonify({
            "error": "Event could not be created because of a database constraint."
        }), 400

    except Exception:
        db.rollback()
        raise


# --------------------------------------------------
# 2. LIST AND SEARCH APPROVED EVENTS
# --------------------------------------------------

@events_bp.route("/", methods=["GET"])
def get_events():

    db = get_db()

    search = request.args.get("search", "").strip()
    category_id = request.args.get("category_id", "").strip()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()
    sort = request.args.get("sort", "upcoming").strip().lower()

    # Validate pagination
    try:
        page = parse_positive_integer(request.args.get("page", "1"))
        per_page = parse_positive_integer(request.args.get("per_page", "10"))

    except ValueError:
        return jsonify({
            "error": "Page and per_page must be positive integers."
        }), 400

    if per_page > 100:
        return jsonify({
            "error": "Maximum per_page value is 100."
        }), 400

    # Validate sorting
    sort_options = {
        "upcoming": "e.starts_at ASC, e.event_id ASC",
        "latest": "e.created_at DESC, e.event_id DESC",
        "popular": "registered_count DESC, e.starts_at ASC"
    }

    if sort not in sort_options:
        return jsonify({
            "error": "Sort must be upcoming, latest, or popular."
        }), 400

    # Validate category
    if category_id:
        try:
            category_id = parse_positive_integer(category_id)

        except ValueError:
            return jsonify({
                "error": "Category ID must be a positive integer."
            }), 400

    # Validate date format
    for date_value in (start_date, end_date):
        if date_value:
            try:
                datetime.strptime(date_value, "%Y-%m-%d")
            except ValueError:
                return jsonify({
                    "error": "Dates must use YYYY-MM-DD format."
                }), 400

    # Validate date range
    if start_date and end_date and start_date > end_date:
        return jsonify({
            "error": "Start date cannot be after end date."
        }), 400

    # Build filters
    conditions = ["e.status = 'approved'"]
    parameters = []

    # Search title and description
    if search:
        conditions.append(
            "(e.title LIKE ? OR e.description LIKE ?)"
        )
        parameters.extend([
            f"%{search}%",
            f"%{search}%"
        ])

    # Category filter
    if category_id:
        conditions.append("e.category_id = ?")
        parameters.append(category_id)

    # Start date filter
    if start_date:
        conditions.append("date(e.starts_at) >= date(?)")
        parameters.append(start_date)

    # End date filter (inclusive)
    if end_date:
        conditions.append("date(e.starts_at) <= date(?)")
        parameters.append(end_date)

    where_clause = " AND ".join(conditions)

    # Count matching events
    total = db.execute(
        f"""
        SELECT COUNT(*)
        FROM events e
        WHERE {where_clause}
        """,
        parameters
    ).fetchone()[0]

    # Retrieve filtered and sorted events
    events = db.execute(
        f"""
        SELECT
            e.event_id,
            e.title,
            e.description,
            e.starts_at,
            e.ends_at,
            e.registration_deadline,
            e.capacity,
            e.created_at,
            c.category_name,
            v.venue_name,
            v.location,
            u.name AS organizer_name,
            COUNT(r.registration_id) AS registered_count

        FROM events e

        JOIN categories c
            ON e.category_id = c.category_id

        JOIN venues v
            ON e.venue_id = v.venue_id

        JOIN users u
            ON e.organizer_id = u.user_id

        LEFT JOIN registrations r
            ON e.event_id = r.event_id
            AND r.status = 'confirmed'

        WHERE {where_clause}

        GROUP BY e.event_id

        ORDER BY {sort_options[sort]}

        LIMIT ? OFFSET ?
        """,
        parameters + [
            per_page,
            (page - 1) * per_page
        ]
    ).fetchall()

    return jsonify({
        "events": [
            dict(event) for event in events
        ],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total_events": total,
            "total_pages": (total + per_page - 1) // per_page
        }
    }), 200

@events_bp.route("/<int:event_id>", methods=["GET"])
def get_event_details(event_id):
    """
    Retrieve complete details of a single approved event.
    """

    db = get_db()

    event = db.execute("""
        SELECT
            e.event_id,
            e.title,
            e.description,
            e.starts_at,
            e.ends_at,
            e.registration_deadline,
            e.capacity,
            e.status,
            e.created_at,
            c.category_name,
            v.venue_name,
            v.location AS venue_location,
            u.name AS organizer_name,
            (
                SELECT COUNT(*)
                FROM registrations r
                WHERE r.event_id = e.event_id
                  AND r.status = 'confirmed'
            ) AS registered_count
        FROM events e
        JOIN categories c
            ON e.category_id = c.category_id
        JOIN venues v
            ON e.venue_id = v.venue_id
        JOIN users u
            ON e.organizer_id = u.user_id
        WHERE e.event_id = ?
          AND e.status = 'approved'
    """, (event_id,)).fetchone()

    if event is None:
        return jsonify({
            "error": "Event not found."
        }), 404

    return jsonify({
        "event": dict(event)
    }), 200

@events_bp.route("/<int:event_id>", methods=["PUT"])
@role_required("organizer")
def update_event(event_id):
    """
    Update an event owned by the logged-in organizer.
    Only pending events can be updated.
    """

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "error": "Request body must contain a valid JSON object."
        }), 400

    db = get_db()

    event = db.execute("""
        SELECT event_id, organizer_id, status
        FROM events
        WHERE event_id = ?
    """, (event_id,)).fetchone()

    if event is None:
        return jsonify({
            "error": "Event not found."
        }), 404

    if event["organizer_id"] != current_user.id:
        return jsonify({
            "error": "You are not authorized to update this event."
        }), 403

    if event["status"] != "pending":
        return jsonify({
            "error": "Only pending events can be updated."
        }), 400

    allowed_fields = {
        "title",
        "description",
        "category_id",
        "venue_id",
        "starts_at",
        "ends_at",
        "registration_deadline",
        "capacity"
    }

    if not data or not set(data).issubset(allowed_fields):
        return jsonify({
            "error": "Invalid or empty update fields."
        }), 400

    # Retrieve existing event details.
    existing = db.execute("""
        SELECT *
        FROM events
        WHERE event_id = ?
    """, (event_id,)).fetchone()

    updated = dict(existing)

    # Apply supplied changes.
    updated.update(data)

    # Validate title.
    if not isinstance(updated["title"], str) or not updated["title"].strip():
        return jsonify({
            "error": "Event title cannot be empty."
        }), 400

    updated["title"] = updated["title"].strip()

    # Validate description.
    if not isinstance(updated["description"], str):
        return jsonify({
            "error": "Description must be text."
        }), 400

    try:
        category_id = parse_positive_integer(updated["category_id"])
        venue_id = parse_positive_integer(updated["venue_id"])
        capacity = parse_positive_integer(updated["capacity"])

        starts_at = parse_event_datetime(updated["starts_at"])
        ends_at = parse_event_datetime(updated["ends_at"])
        deadline = parse_event_datetime(
            updated["registration_deadline"]
        )

    except (ValueError, TypeError, OverflowError):
        return jsonify({
            "error": "Invalid event data or date format."
        }), 400

    date_values = [starts_at, ends_at, deadline]

    awareness = [
        value.utcoffset() is not None
        for value in date_values
    ]

    if len(set(awareness)) != 1:
        return jsonify({
            "error": "All event dates must use consistent timezone information."
        }), 400

    if ends_at <= starts_at:
        return jsonify({
            "error": "Event end time must be later than start time."
        }), 400

    if deadline > starts_at:
        return jsonify({
            "error": "Registration deadline cannot be after event start."
        }), 400

    current_time = (
        datetime.now().astimezone()
        if awareness[0]
        else datetime.now()
    )

    if deadline <= current_time:
        return jsonify({
            "error": "Registration deadline must be in the future."
        }), 400

    # Verify category.
    category = db.execute("""
        SELECT category_id
        FROM categories
        WHERE category_id = ?
    """, (category_id,)).fetchone()

    if category is None:
        return jsonify({
            "error": "Selected category does not exist."
        }), 400

    # Verify venue and its capacity.
    venue = db.execute("""
        SELECT capacity
        FROM venues
        WHERE venue_id = ?
    """, (venue_id,)).fetchone()

    if venue is None:
        return jsonify({
            "error": "Selected venue does not exist."
        }), 400

    if capacity > venue["capacity"]:
        return jsonify({
            "error": "Event capacity exceeds venue capacity."
        }), 400

        # Check venue booking conflict, excluding this event
    conflict = check_venue_conflict(
        db,
        venue_id,
        starts_at,
        ends_at,
        exclude_event_id=event_id
    )

    if conflict:
        return jsonify({
            "error": "This venue is already booked during the selected time.",
            "conflicting_event_id": conflict["event_id"],
            "conflicting_event_title": conflict["title"]
        }), 409

    try:
        db.execute("""
            UPDATE events
            SET
                title = ?,
                description = ?,
                category_id = ?,
                venue_id = ?,
                starts_at = ?,
                ends_at = ?,
                registration_deadline = ?,
                capacity = ?
            WHERE event_id = ?
              AND organizer_id = ?
              AND status = 'pending'
        """, (
            updated["title"],
            updated["description"],
            category_id,
            venue_id,
            starts_at.isoformat(),
            ends_at.isoformat(),
            deadline.isoformat(),
            capacity,
            event_id,
            current_user.id
        ))

        if db.execute("SELECT changes()").fetchone()[0] != 1:
            db.rollback()
            return jsonify({
                "error": "Event was not updated. It may have changed or is no longer editable."
            }), 409

        db.commit()

        return jsonify({
            "message": "Event updated successfully.",
            "event_id": event_id
        }), 200

    except sqlite3.IntegrityError:
        db.rollback()

        return jsonify({
            "error": "Event could not be updated because of a database constraint."
        }), 400

    except Exception:
        db.rollback()
        raise

@events_bp.route("/<int:event_id>/cancel", methods=["PATCH"])
@role_required("organizer")
def cancel_event(event_id):
    db = get_db()

    event = db.execute("""
        SELECT event_id, organizer_id, status
        FROM events
        WHERE event_id = ?
    """, (event_id,)).fetchone()

    if event is None:
        return jsonify({
            "error": "Event not found."
        }), 404

    if event["organizer_id"] != current_user.id:
        return jsonify({
            "error": "You can only cancel your own events."
        }), 403

    if event["status"] != "pending":
        return jsonify({
            "error": "Only pending events can be cancelled."
        }), 400

    try:
        cursor = db.execute("""
            UPDATE events
            SET status = 'cancelled'
            WHERE event_id = ?
              AND organizer_id = ?
              AND status = 'pending'
        """, (event_id, current_user.id))

        if cursor.rowcount != 1:
            db.rollback()
            return jsonify({
                "error": "Event could not be cancelled because its status changed."
            }), 409

        db.commit()

        return jsonify({
            "message": "Event cancelled successfully.",
            "event_id": event_id,
            "status": "cancelled"
        }), 200

    except sqlite3.IntegrityError:
        db.rollback()
        return jsonify({
            "error": "Event could not be cancelled because of a database constraint."
        }), 400

    except Exception:
        db.rollback()
        raise

def review_event(event_id, new_status):
    """
    Approve or reject a pending event.
    Only administrators can perform this operation.
    """
    db = get_db()

    if new_status == "approved":
        event = db.execute("""
            SELECT venue_id, starts_at, ends_at
            FROM events
            WHERE event_id = ? AND status = 'pending'
        """, (event_id,)).fetchone()

        if event is not None:
            conflict = check_venue_conflict(
                db,
                event["venue_id"],
                datetime.fromisoformat(event["starts_at"]),
                datetime.fromisoformat(event["ends_at"]),
                exclude_event_id=event_id
            )

            if conflict:
                return jsonify({
                    "error": "Cannot approve event. The venue is already booked.",
                    "conflicting_event_id": conflict["event_id"],
                    "conflicting_event_title": conflict["title"]
                }), 409
    try:
        cursor = db.execute("""
            UPDATE events
            SET status = ?
            WHERE event_id = ?
              AND status = 'pending'
        """, (new_status, event_id))

        if cursor.rowcount == 0:
            db.rollback()

            event = db.execute("""
                SELECT event_id, status
                FROM events
                WHERE event_id = ?
            """, (event_id,)).fetchone()

            if event is None:
                return jsonify({
                    "error": "Event not found."
                }), 404

            return jsonify({
                "error": "Only pending events can be reviewed."
            }), 400

        db.commit()

        return jsonify({
            "message": f"Event {new_status} successfully.",
            "event_id": event_id,
            "status": new_status
        }), 200

    except sqlite3.IntegrityError:
        db.rollback()

        return jsonify({
            "error": "Database constraint prevented the event review."
        }), 400

    except Exception:
        db.rollback()
        raise


@events_bp.route("/<int:event_id>/approve", methods=["PATCH"])
@role_required("admin")
def approve_event(event_id):
    return review_event(event_id, "approved")


@events_bp.route("/<int:event_id>/reject", methods=["PATCH"])
@role_required("admin")
def reject_event(event_id):
    return review_event(event_id, "rejected")