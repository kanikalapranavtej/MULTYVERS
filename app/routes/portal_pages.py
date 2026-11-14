from flask import Blueprint, redirect, url_for, render_template, abort, request
from flask_login import current_user
from app.database import get_db
from app.decorators import role_required

portal_pages_bp = Blueprint("portal_pages", __name__)

@portal_pages_bp.route("/dashboard")
@role_required("student", "organizer", "admin")
def dashboard():
    if current_user.role == "admin":
        return redirect(url_for("portal_pages.admin_portal"))
    if current_user.role == "organizer":
        return redirect(url_for("portal_pages.organizer_portal"))
    return redirect(url_for("portal_pages.student_portal"))

@portal_pages_bp.route("/student/portal")
@role_required("student")
def student_portal():
    db = get_db()
    registrations = db.execute("""SELECT r.registration_id, r.status AS registration_status, r.registered_at,
        e.event_id, e.title, e.starts_at, e.status AS event_status,
        v.venue_name, v.location FROM registrations r
        JOIN events e ON e.event_id=r.event_id JOIN venues v ON v.venue_id=e.venue_id
        WHERE r.user_id=? ORDER BY datetime(e.starts_at) DESC LIMIT 30""", (current_user.id,)).fetchall()
    stats = db.execute("""SELECT COUNT(*) AS total
        FROM registrations r JOIN events e ON e.event_id=r.event_id WHERE r.user_id=?""", (current_user.id,)).fetchone()
    return render_template("portals/student.html", registrations=registrations, stats=stats)

@portal_pages_bp.route("/organizer/portal")
@role_required("organizer")
def organizer_portal():
    db = get_db()
    events = db.execute("""SELECT e.event_id,e.title,e.starts_at,e.status,e.capacity,
        v.venue_name, COUNT(CASE WHEN r.status='confirmed' THEN 1 END) AS registrations
        FROM events e JOIN venues v ON v.venue_id=e.venue_id
        LEFT JOIN registrations r ON r.event_id=e.event_id
        WHERE e.organizer_id=? GROUP BY e.event_id ORDER BY datetime(e.starts_at) DESC""", (current_user.id,)).fetchall()
    stats = db.execute("""SELECT COUNT(*) AS total,
        COALESCE(SUM(CASE WHEN status='approved' THEN 1 ELSE 0 END),0) AS approved,
        COALESCE(SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END),0) AS pending
        FROM events WHERE organizer_id=?""", (current_user.id,)).fetchone()
    return render_template("portals/organizer.html", events=events, stats=stats)

@portal_pages_bp.route("/organizer/events/new")
@role_required("organizer")
def organizer_event_create_page():
    db = get_db()
    categories = db.execute("SELECT category_id, category_name FROM categories ORDER BY category_name").fetchall()
    venues = db.execute("SELECT venue_id, venue_name, location, capacity FROM venues ORDER BY venue_name").fetchall()
    return render_template("organizer/event_form.html", event=None, categories=categories, venues=venues)

@portal_pages_bp.route("/organizer/events/<int:event_id>/edit")
@role_required("organizer")
def organizer_event_edit_page(event_id):
    db = get_db()
    event = db.execute("""SELECT * FROM events WHERE event_id=? AND organizer_id=?""", (event_id, current_user.id)).fetchone()
    if event is None:
        abort(404)
    if event["status"] != "pending":
        return redirect(url_for("portal_pages.organizer_portal"))
    categories = db.execute("SELECT category_id, category_name FROM categories ORDER BY category_name").fetchall()
    venues = db.execute("SELECT venue_id, venue_name, location, capacity FROM venues ORDER BY venue_name").fetchall()
    return render_template("organizer/event_form.html", event=event, categories=categories, venues=venues)

@portal_pages_bp.route("/admin/events")
@role_required("admin")
def admin_events_page():
    db = get_db()
    status = request.args.get("status", "pending").strip().lower()
    allowed = {"all", "pending", "approved", "rejected", "cancelled"}
    if status not in allowed:
        status = "pending"
    query = """SELECT e.event_id,e.title,e.description,e.starts_at,e.ends_at,e.registration_deadline,e.capacity,e.status,
        u.name AS organizer_name,c.category_name,v.venue_name,
        COUNT(CASE WHEN r.status='confirmed' THEN 1 END) AS registrations
        FROM events e JOIN users u ON u.user_id=e.organizer_id
        JOIN categories c ON c.category_id=e.category_id JOIN venues v ON v.venue_id=e.venue_id
        LEFT JOIN registrations r ON r.event_id=e.event_id"""
    params = []
    if status != "all":
        query += " WHERE e.status=?"
        params.append(status)
    query += " GROUP BY e.event_id ORDER BY CASE e.status WHEN 'pending' THEN 0 ELSE 1 END, datetime(e.starts_at) DESC"
    events = db.execute(query, params).fetchall()
    return render_template("admin/events.html", events=events, selected_status=status)

@portal_pages_bp.route("/admin/portal")
@role_required("admin")
def admin_portal():
    db = get_db()
    stats = db.execute("""SELECT
        (SELECT COUNT(*) FROM users WHERE role='student') AS students,
        (SELECT COUNT(*) FROM users WHERE role='organizer') AS organizers,
        (SELECT COUNT(*) FROM users WHERE role='organizer' AND approval_status='pending') AS pending_organizers,
        (SELECT COUNT(*) FROM events) AS events,
        (SELECT COUNT(*) FROM events WHERE status='pending') AS pending_events,
        (SELECT COUNT(*) FROM registrations) AS registrations""").fetchone()
    recent_events = db.execute("""SELECT e.event_id,e.title,e.status,e.starts_at,u.name AS organizer_name
        FROM events e JOIN users u ON u.user_id=e.organizer_id
        ORDER BY e.event_id DESC LIMIT 8""").fetchall()
    return render_template("portals/admin.html", stats=stats, events=recent_events)
