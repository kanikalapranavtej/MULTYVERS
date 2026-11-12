from flask import Blueprint, render_template, request, abort
from app.database import get_db


pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/events")
def event_listing():
    db = get_db()

    search = request.args.get("search", "").strip()
    category_id = request.args.get("category_id", "").strip()
    sort = request.args.get("sort", "upcoming")

    try:
        page = max(1, int(request.args.get("page", 1)))
    except (ValueError, TypeError):
        page = 1

    per_page = 9

    conditions = ["e.status = 'approved'"]
    parameters = []

    if search:
        conditions.append(
            "(e.title LIKE ? OR e.description LIKE ?)"
        )
        parameters.extend([f"%{search}%", f"%{search}%"])

    if category_id:
        try:
            category_id = int(category_id)
            if category_id <= 0:
                raise ValueError
            conditions.append("e.category_id = ?")
            parameters.append(category_id)
        except ValueError:
            abort(400)

    where_clause = " AND ".join(conditions)

    sort_options = {
        "upcoming": "datetime(e.starts_at) ASC",
        "latest": "datetime(e.starts_at) DESC",
        "popular": "registered_count DESC",
    }

    order_clause = sort_options.get(sort, sort_options["upcoming"])

    total = db.execute(
        f"""
        SELECT COUNT(*)
        FROM events e
        WHERE {where_clause}
        """,
        parameters
    ).fetchone()[0]

    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, total_pages)

    events = db.execute(
        f"""
        SELECT
            e.event_id,
            e.title,
            e.description,
            e.starts_at,
            e.ends_at,
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
        JOIN categories c ON e.category_id = c.category_id
        JOIN venues v ON e.venue_id = v.venue_id
        JOIN users u ON e.organizer_id = u.user_id
        WHERE {where_clause}
        ORDER BY {order_clause}
        LIMIT ? OFFSET ?
        """,
        parameters + [per_page, (page - 1) * per_page]
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
        page=page,
        total_pages=total_pages,
        total=total,
        current_year=2026
    )


@pages_bp.route("/events/<int:event_id>")
def event_detail():
    event_id = request.view_args["event_id"]
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
        JOIN categories c ON e.category_id = c.category_id
        JOIN venues v ON e.venue_id = v.venue_id
        JOIN users u ON e.organizer_id = u.user_id
        WHERE e.event_id = ?
          AND e.status = 'approved'
        """,
        (event_id,)
    ).fetchone()

    if event is None:
        abort(404)

    return render_template(
        "events/detail.html",
        event=dict(event),
        current_year=2026
    )