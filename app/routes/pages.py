from datetime import date, datetime

from flask import Blueprint, render_template, request, abort, url_for
from flask_login import current_user

from app.database import get_db


pages_bp = Blueprint("pages", __name__)

PER_PAGE = 9

SORT_OPTIONS = {
    "upcoming": "datetime(e.starts_at) ASC, e.event_id ASC",
    "latest": "datetime(e.created_at) DESC, e.event_id DESC",
    "popular": "registered_count DESC, e.event_id ASC",
}


def validate_date(value):
    """Validate an optional YYYY-MM-DD date."""
    if not value:
        return None

    try:
        return date.fromisoformat(value)
    except ValueError:
        abort(400, description="Dates must use YYYY-MM-DD format.")


@pages_bp.route("/events")
def event_listing():

    db = get_db()

    search = request.args.get("search", "").strip()
    category_id = request.args.get("category_id", "").strip()
    sort = request.args.get("sort", "upcoming").strip()

    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()

    if sort not in SORT_OPTIONS:
        abort(400, description="Invalid sorting option.")

    start = validate_date(start_date)
    end = validate_date(end_date)

    if start and end and start > end:
        abort(400, description="Start date cannot be after end date.")

    try:
        page = int(request.args.get("page", "1"))
    except ValueError:
        abort(400, description="Page must be a positive integer.")

    if page < 1:
        abort(400, description="Page must be a positive integer.")

    conditions = ["e.status = 'approved'"]
    parameters = []

    # Search title and description.
    if search:
        conditions.append(
            "(e.title LIKE ? OR e.description LIKE ?)"
        )
        parameters.extend([
            f"%{search}%",
            f"%{search}%"
        ])

    # Category filter.
    if category_id:
        if not category_id.isdecimal() or int(category_id) <= 0:
            abort(400, description="Invalid category.")

        category_id = int(category_id)

        conditions.append("e.category_id = ?")
        parameters.append(category_id)
    else:
        category_id = ""

    # Start date filter.
    if start:
        conditions.append(
            "datetime(e.starts_at) >= datetime(?)"
        )
        parameters.append(f"{start.isoformat()} 00:00:00")

    # End date filter: include the complete selected day.
    if end:
        conditions.append(
            "datetime(e.starts_at) < datetime(?)"
        )
        parameters.append(
            f"{end.isoformat()} 00:00:00"
        )
        parameters[-1] = (
            f"{end.isoformat()} 00:00:00"
        )

        conditions[-1] = (
            "datetime(e.starts_at) < datetime(?, '+1 day')"
        )

    where_clause = " AND ".join(conditions)
    order_clause = SORT_OPTIONS[sort]

    # Count matching events.
    total = db.execute(
        f"""
        SELECT COUNT(*)
        FROM events e
        WHERE {where_clause}
        """,
        parameters
    ).fetchone()[0]

    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    page = min(page, total_pages)

    # Fetch matching events.
    events = db.execute(
        f"""
        SELECT
            e.event_id,
            e.title,
            e.description,
            e.starts_at,
            e.ends_at,
            e.capacity,
            e.registration_deadline,
            c.category_name,
            v.venue_name,
            v.location,
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

        WHERE {where_clause}

        ORDER BY {order_clause}

        LIMIT ? OFFSET ?
        """,
        parameters + [
            PER_PAGE,
            (page - 1) * PER_PAGE
        ]
    ).fetchall()

    categories = db.execute(
        """
        SELECT category_id, category_name
        FROM categories
        ORDER BY category_name
        """
    ).fetchall()

    return render_template(
        "events/index.html",
        events=[dict(row) for row in events],
        categories=[dict(row) for row in categories],
        search=search,
        selected_category=category_id,
        sort=sort,
        start_date=start_date,
        end_date=end_date,
        page=page,
        total_pages=total_pages,
        total=total,
        current_year=datetime.now().year
    )


@pages_bp.route("/events/<int:event_id>")
def event_detail(event_id):

    db = get_db()

    event = db.execute(
        """
        SELECT
            e.event_id,
            e.title,
            e.description,
            e.starts_at,
            e.ends_at,
            e.registration_deadline,
            e.capacity,
            c.category_name,
            v.venue_name,
            v.location,
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
        """,
        (event_id,)
    ).fetchone()

    if event is None:
        abort(404)

    event = dict(event)

    registration_status = None

    if current_user.is_authenticated and current_user.role == "student":

        registration = db.execute(
            """
            SELECT status
            FROM registrations
            WHERE user_id = ? AND event_id = ?
            """,
            (current_user.id, event_id)
        ).fetchone()

        if registration:
            registration_status = registration["status"]

    # Check registration deadline.
    try:
        deadline = datetime.fromisoformat(
            event["registration_deadline"]
        )

        if deadline.tzinfo is None:
            deadline = deadline.astimezone()

        deadline_passed = datetime.now().astimezone() > deadline

    except (ValueError, TypeError):
        deadline_passed = True

    is_full = event["registered_count"] >= event["capacity"]

    can_register = (
        current_user.is_authenticated
        and current_user.role == "student"
        and registration_status != "confirmed"
        and not deadline_passed
        and not is_full
    )

    return render_template(
        "events/detail.html",
        event=event,
        registration_status=registration_status,
        can_register=can_register,
        deadline_passed=deadline_passed,
        is_full=is_full,
        current_year=datetime.now().year
    )