from flask import Blueprint, flash, redirect, render_template, request, url_for
from app.database import get_db
from app.decorators import role_required

admin_students_bp = Blueprint("admin_students", __name__, url_prefix="/admin/students")


@admin_students_bp.route("/", methods=["GET", "POST"], strict_slashes=False)
@role_required("admin")
def student_management():
    db = get_db()
    if request.method == "POST":
        student_id = request.form.get("student_id", type=int)
        action = request.form.get("action")
        if not student_id or action not in {"deactivate", "reactivate"}:
            flash("Invalid student account action.", "error")
        else:
            active = 0 if action == "deactivate" else 1
            cursor = db.execute(
                "UPDATE users SET is_active=? WHERE user_id=? AND role='student'",
                (active, student_id),
            )
            if cursor.rowcount:
                db.commit()
                flash("Student account deactivated." if not active else "Student account reactivated.", "success")
            else:
                db.rollback()
                flash("Student account was not found.", "error")
        return redirect(url_for("admin_students.student_management", q=request.args.get("q", "")))

    query = request.args.get("q", "").strip()
    sql = (
        "SELECT u.user_id,u.name,u.email,u.created_at,u.is_active,"
        "COUNT(r.registration_id) AS registrations "
        "FROM users u LEFT JOIN registrations r ON r.user_id=u.user_id "
        "WHERE u.role='student'"
    )
    params = []
    if query:
        sql += " AND (u.name LIKE ? OR u.email LIKE ?)"
        params.extend((f"%{query}%", f"%{query}%"))
    sql += " GROUP BY u.user_id ORDER BY u.name COLLATE NOCASE"
    students = db.execute(sql, params).fetchall()
    totals = db.execute(
        "SELECT COUNT(*) AS total,COALESCE(SUM(is_active),0) AS active FROM users WHERE role='student'"
    ).fetchone()
    return render_template(
        "admin/students.html", students=students, query=query,
        total=totals["total"], active=totals["active"]
    )
