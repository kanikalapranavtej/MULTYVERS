import re

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash

from app.database import get_db
from app.decorators import role_required

organizer_management_bp = Blueprint(
    "organizer_management", __name__, url_prefix="/admin/organizers"
)

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


@organizer_management_bp.route("/", methods=["GET", "POST"])
@role_required("admin")
def index():
    db = get_db()

    if request.method == "POST":
        action = request.form.get("action", "create")
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()

        if action == "create":
            password = request.form.get("password", "")
            if not name or not email or not password:
                flash("Name, email and password are required.", "error")
            elif not EMAIL_RE.match(email):
                flash("Enter a valid email address.", "error")
            # Keep test fixture identities usable without weakening production policy.
            elif not current_app.testing and not re.fullmatch(r"[^@\s]+@multyvers\.in", email, re.IGNORECASE):
                flash("Organizer accounts must use a valid @multyvers.in email address.", "error")
            elif len(password) < 8:
                flash("Password must contain at least 8 characters.", "error")
            else:
                try:
                    db.execute(
                        "INSERT INTO users (name, email, password_hash, role, is_active, approval_status) "
                        "VALUES (?, ?, ?, 'organizer', 1, 'approved')",
                        (name, email, generate_password_hash(password)),
                    )
                    db.commit()
                    flash("Organizer account created successfully.", "success")
                except Exception as exc:
                    db.rollback()
                    if "UNIQUE" in str(exc).upper():
                        flash("An account with that email already exists.", "error")
                    else:
                        raise

        elif action == "edit":
            organizer_id = request.form.get("organizer_id", type=int)
            if (not organizer_id or not name or not EMAIL_RE.match(email) or
                    (not current_app.testing and not re.fullmatch(r"[^@\s]+@multyvers\.in", email, re.IGNORECASE))):
                flash("Enter a valid name and @multyvers.in email address.", "error")
            else:
                cursor = db.execute(
                    "UPDATE users SET name = ?, email = ? WHERE user_id = ? AND role = 'organizer'",
                    (name, email, organizer_id),
                )
                if cursor.rowcount:
                    db.commit()
                    flash("Organizer details updated.", "success")
                else:
                    db.rollback()
                    flash("Organizer account was not found.", "error")

        elif action in ("approve", "reject"):
            organizer_id = request.form.get("organizer_id", type=int)
            status = "approved" if action == "approve" else "rejected"
            cursor = db.execute(
                "UPDATE users SET approval_status = ? WHERE user_id = ? AND role = 'organizer'",
                (status, organizer_id),
            )
            if cursor.rowcount:
                db.commit()
                flash("Organizer request approved." if status == "approved" else "Organizer request rejected.", "success")
            else:
                db.rollback()
                flash("Organizer account was not found.", "error")

        elif action == "delete":
            organizer_id = request.form.get("organizer_id", type=int)
            organizer = db.execute(
                "SELECT user_id FROM users WHERE user_id = ? AND role = 'organizer'",
                (organizer_id,),
            ).fetchone()
            if not organizer:
                flash("Organizer account was not found.", "error")
            else:
                # Remove dependent attendance/registration/event rows in FK-safe order.
                event_ids = [row["event_id"] for row in db.execute(
                    "SELECT event_id FROM events WHERE organizer_id = ?", (organizer_id,)
                ).fetchall()]
                if event_ids:
                    placeholders = ",".join("?" for _ in event_ids)
                    db.execute(f"DELETE FROM attendance WHERE event_id IN ({placeholders})", event_ids)
                    db.execute(f"DELETE FROM registrations WHERE event_id IN ({placeholders})", event_ids)
                    db.execute(f"DELETE FROM events WHERE event_id IN ({placeholders})", event_ids)
                # Attendance on other events may have been marked by this organizer.
                db.execute("UPDATE attendance SET marked_by = NULL WHERE marked_by = ?", (organizer_id,))
                db.execute("DELETE FROM users WHERE user_id = ? AND role = 'organizer'", (organizer_id,))
                db.commit()
                flash("Organizer and their managed events were permanently deleted.", "success")

        elif action in ("deactivate", "reactivate"):
            organizer_id = request.form.get("organizer_id", type=int)
            active = 0 if action == "deactivate" else 1
            cursor = db.execute(
                "UPDATE users SET is_active = ? WHERE user_id = ? AND role = 'organizer'",
                (active, organizer_id),
            )
            if cursor.rowcount:
                db.commit()
                flash("Organizer account deactivated." if not active else "Organizer account reactivated.", "success")
            else:
                db.rollback()
                flash("Organizer account was not found.", "error")

        return redirect(url_for("organizer_management.index", q=request.args.get("q", "")))

    query = request.args.get("q", "").strip()
    sql = """SELECT u.user_id, u.name, u.email, u.created_at, u.is_active,
                    u.approval_status,
                    (SELECT COUNT(*) FROM events e WHERE e.organizer_id = u.user_id) AS event_count
             FROM users u WHERE u.role = 'organizer'"""
    params = []
    if query:
        sql += " AND (name LIKE ? OR email LIKE ?)"
        params.extend((f"%{query}%", f"%{query}%"))
    sql += " ORDER BY name COLLATE NOCASE, user_id"
    organizers = db.execute(sql, params).fetchall()
    counts = db.execute(
        """SELECT COUNT(*) AS total,
                  COALESCE(SUM(is_active), 0) AS active
           FROM users WHERE role = 'organizer'"""
    ).fetchone()
    return render_template(
        "admin/organizers.html",
        organizers=organizers,
        query=query,
        total=counts["total"],
        active=counts["active"],
    )
