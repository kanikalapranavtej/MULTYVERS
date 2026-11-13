from flask import Blueprint, jsonify, current_app, render_template
from flask_login import current_user

from app.database import get_db
from app.decorators import role_required


main_bp = Blueprint("main", __name__)


@main_bp.route("/", methods=["GET"])
def home():
    db = get_db()

    # Retrieve approved upcoming events.
    featured_events = db.execute("""
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
        WHERE e.status = 'approved'
          AND datetime(e.starts_at) >= datetime('now', 'localtime')
        ORDER BY datetime(e.starts_at) ASC
        LIMIT 6
    """).fetchall()

    # Retrieve real event categories.
    categories = db.execute("""
        SELECT
            c.category_id,
            c.category_name,
            COUNT(e.event_id) AS event_count
        FROM categories c
        LEFT JOIN events e
            ON e.category_id = c.category_id
            AND e.status = 'approved'
            AND datetime(e.starts_at) >= datetime('now', 'localtime')
        GROUP BY c.category_id, c.category_name
        ORDER BY c.category_name
    """).fetchall()

    # Real platform statistics.
    statistics = db.execute("""
        SELECT
            (SELECT COUNT(*) FROM users WHERE role = 'student')
                AS students,
            (SELECT COUNT(*) FROM events WHERE status = 'approved')
                AS events,
            (SELECT COUNT(*) FROM categories)
                AS categories
    """).fetchone()

    return render_template(
        "landing.html",
        featured_events=[dict(row) for row in featured_events],
        categories=[dict(row) for row in categories],
        statistics=dict(statistics),
        current_year=__import__("datetime").datetime.now().year
    )


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

    db = get_db()

    # Retrieve the logged-in student's basic information.
    student = {
        "user_id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.role
    }

    # Retrieve all registrations belonging to this student.
    registrations = db.execute("""
        SELECT
            r.registration_id,
            r.status AS registration_status,
            r.registered_at,
            e.event_id,
            e.title,
            e.description,
            e.starts_at,
            e.ends_at,
            e.status AS event_status,
            c.category_name,
            v.venue_name,
            v.location AS venue_location
        FROM registrations r
        JOIN events e
            ON r.event_id = e.event_id
        JOIN categories c
            ON e.category_id = c.category_id
        JOIN venues v
            ON e.venue_id = v.venue_id
        WHERE r.user_id = ?
        ORDER BY e.starts_at ASC
    """, (current_user.id,)).fetchall()

    # Convert database rows into JSON-compatible dictionaries.
    registered_events = [
        dict(row) for row in registrations
    ]

    # Calculate registration statistics.
    total_registrations = len(registered_events)

    confirmed_registrations = sum(
        1 for event in registered_events
        if event["registration_status"] == "confirmed"
    )

    cancelled_registrations = sum(
        1 for event in registered_events
        if event["registration_status"] == "cancelled"
    )

    # Count upcoming and past confirmed events.
    time_data = db.execute("""
        SELECT
            SUM(
                CASE
                    WHEN r.status = 'confirmed'
                    AND e.status = 'approved'
                    AND datetime(e.starts_at) >= datetime('now', 'localtime')
                    THEN 1 ELSE 0
                END
            ) AS upcoming_events,

            SUM(
                CASE
                    WHEN r.status = 'confirmed'
                    AND e.status = 'approved'
                    AND datetime(e.starts_at) < datetime('now', 'localtime')
                    THEN 1 ELSE 0
                END
            ) AS past_events

        FROM registrations r
        JOIN events e
            ON r.event_id = e.event_id
        WHERE r.user_id = ?
    """, (current_user.id,)).fetchone()

    statistics = {
        "total_registrations": total_registrations,
        "confirmed_registrations": confirmed_registrations,
        "cancelled_registrations": cancelled_registrations,
        "upcoming_events": time_data["upcoming_events"] or 0,
        "past_events": time_data["past_events"] or 0
    }

    return jsonify({
    "dashboard": "Student",
    "message": f"Welcome, {current_user.name}!",
    "role": current_user.role,
    "student": student,
    "statistics": statistics,
    "registered_events": registered_events
     }), 200

# --------------------------------
# ORGANIZER DASHBOARD
# --------------------------------

@main_bp.route("/organizer/dashboard")
@role_required("organizer")
def organizer_dashboard():

    db = get_db()

    # Retrieve all events created by this organizer.
    events = db.execute("""
        SELECT
            e.event_id,
            e.title,
            e.description,
            e.starts_at,
            e.ends_at,
            e.registration_deadline,
            e.capacity,
            e.status,
            c.category_name,
            v.venue_name,
            v.location AS venue_location,

            COUNT(
                CASE
                    WHEN r.status = 'confirmed' THEN 1
                END
            ) AS confirmed_registrations,

            COUNT(r.registration_id) AS total_registrations

        FROM events e

        JOIN categories c
            ON e.category_id = c.category_id

        JOIN venues v
            ON e.venue_id = v.venue_id

        LEFT JOIN registrations r
            ON e.event_id = r.event_id

        WHERE e.organizer_id = ?

        GROUP BY e.event_id

        ORDER BY datetime(e.starts_at) ASC

    """, (current_user.id,)).fetchall()

    # Convert database rows into JSON-compatible dictionaries.
    organizer_events = [
        dict(row) for row in events
    ]

    # Calculate event statistics.
    statistics = db.execute("""
        SELECT
            COUNT(*) AS total_events,

            SUM(CASE
                WHEN status = 'approved' THEN 1
                ELSE 0
            END) AS approved_events,

            SUM(CASE
                WHEN status = 'pending' THEN 1
                ELSE 0
            END) AS pending_events,

            SUM(CASE
                WHEN status = 'rejected' THEN 1
                ELSE 0
            END) AS rejected_events,

            SUM(CASE
                WHEN status = 'cancelled' THEN 1
                ELSE 0
            END) AS cancelled_events

        FROM events
        WHERE organizer_id = ?

    """, (current_user.id,)).fetchone()

    # Calculate confirmed registrations across all organizer events.
    registration_data = db.execute("""
        SELECT COUNT(*) AS total_registrations

        FROM registrations r

        JOIN events e
            ON r.event_id = e.event_id

        WHERE e.organizer_id = ?
        AND r.status = 'confirmed'

    """, (current_user.id,)).fetchone()

    return jsonify({
        "dashboard": "Organizer",
        "message": f"Welcome, {current_user.name}!",
        "role": current_user.role,

        "organizer": {
            "user_id": current_user.id,
            "name": current_user.name,
            "email": current_user.email
        },

        "statistics": {
            "total_events": statistics["total_events"] or 0,
            "approved_events": statistics["approved_events"] or 0,
            "pending_events": statistics["pending_events"] or 0,
            "rejected_events": statistics["rejected_events"] or 0,
            "cancelled_events": statistics["cancelled_events"] or 0,
            "total_registrations": registration_data["total_registrations"] or 0
        },

        "events": organizer_events

    }), 200



# --------------------------------
# ADMIN DASHBOARD
# --------------------------------

@main_bp.route("/admin/dashboard")
@role_required("admin")
def admin_dashboard():

    db = get_db()

    # 1. Retrieve platform-wide user statistics.
    user_statistics = db.execute("""
        SELECT
            COUNT(*) AS total_users,
            SUM(CASE WHEN role = 'student' THEN 1 ELSE 0 END)
                AS total_students,
            SUM(CASE WHEN role = 'organizer' THEN 1 ELSE 0 END)
                AS total_organizers,
            SUM(CASE WHEN role = 'admin' THEN 1 ELSE 0 END)
                AS total_admins
        FROM users
    """).fetchone()

    # 2. Retrieve event statistics.
    event_statistics = db.execute("""
        SELECT
            COUNT(*) AS total_events,
            COALESCE(SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END), 0)
            AS approved_events,
            COALESCE(SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END), 0)
            AS pending_events,
            COALESCE(SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END), 0)
            AS rejected_events,
            COALESCE(SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END), 0)
            AS cancelled_events,
            COALESCE(SUM(CASE WHEN status = 'draft' THEN 1 ELSE 0 END), 0)
            AS draft_events
        FROM events
    """).fetchone()

    # 3. Retrieve registration statistics.
    registration_statistics = db.execute("""
        SELECT
            COUNT(*) AS total_registrations,
            COALESCE(SUM(CASE WHEN status = 'confirmed' THEN 1 ELSE 0 END), 0)
            AS confirmed_registrations,
            COALESCE(SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END), 0)
            AS cancelled_registrations
        FROM registrations
    """).fetchone()

    # 4. Retrieve the five most recently registered users.
    recent_users = db.execute("""
        SELECT
            user_id,
            name,
            email,
            role,
            created_at
        FROM users
        ORDER BY user_id DESC
        LIMIT 5
    """).fetchall()

    # 5. Retrieve the five most recently created events.
    recent_events = db.execute("""
        SELECT
            e.event_id,
            e.title,
            e.status,
            e.created_at,
            u.name AS organizer_name
        FROM events e
        JOIN users u
            ON e.organizer_id = u.user_id
        ORDER BY e.event_id DESC
        LIMIT 5
    """).fetchall()

    # Convert database rows into JSON-compatible dictionaries.
    dashboard_data = {
        "users": dict(user_statistics),
        "events": dict(event_statistics),
        "registrations": dict(registration_statistics),
        "recent_users": [
            dict(row) for row in recent_users
        ],
        "recent_events": [
            dict(row) for row in recent_events
        ]
    }

    return jsonify({
        "dashboard": "Admin",
        "message": f"Welcome, {current_user.name}!",
        "role": current_user.role,
        "statistics": dashboard_data
    }), 200