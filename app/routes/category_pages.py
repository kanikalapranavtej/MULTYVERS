from flask import Blueprint, flash, redirect, render_template, request, url_for
from app.database import get_db
from app.decorators import role_required

category_pages_bp = Blueprint("category_pages", __name__)


@category_pages_bp.route(
    "/admin/categories",
    methods=["GET", "POST"],
    strict_slashes=False
)
@role_required("admin")
def category_management_page():

    db = get_db()

    if request.method == "POST":

        action = request.form.get("action", "create")
        category_name = request.form.get("category_name", "").strip()
        description = request.form.get("description", "").strip()
        category_id = request.form.get("category_id", type=int)

        # CREATE CATEGORY
        if action == "create":

            if not category_name:
                flash("Category name is required.", "error")

            else:
                try:
                    db.execute(
                        """
                        INSERT INTO categories
                        (category_name, description)
                        VALUES (?, ?)
                        """,
                        (category_name, description)
                    )

                    db.commit()
                    flash("Category created successfully.", "success")

                except Exception as exc:
                    db.rollback()

                    if "UNIQUE" in str(exc).upper():
                        flash(
                            "A category with that name already exists.",
                            "error"
                        )
                    else:
                        raise

        # EDIT OR UPDATE CATEGORY
        elif action in ("edit", "update"):

            if not category_id or not category_name:
                flash(
                    "A valid category ID and name are required.",
                    "error"
                )

            else:
                try:
                    cursor = db.execute(
                        """
                        UPDATE categories
                        SET category_name = ?, description = ?
                        WHERE category_id = ?
                        """,
                        (category_name, description, category_id)
                    )

                    if cursor.rowcount:
                        db.commit()
                        flash(
                            "Category updated successfully.",
                            "success"
                        )
                    else:
                        db.rollback()
                        flash("Category not found.", "error")

                except Exception as exc:
                    db.rollback()

                    if "UNIQUE" in str(exc).upper():
                        flash(
                            "A category with that name already exists.",
                            "error"
                        )
                    else:
                        raise

        # DELETE CATEGORY
        elif action == "delete":

            if not category_id:
                flash("Invalid category.", "error")

            else:
                used = db.execute(
                    """
                    SELECT COUNT(*) AS total
                    FROM events
                    WHERE category_id = ?
                    """,
                    (category_id,)
                ).fetchone()["total"]

                if used:
                    flash(
                        "This category is used by existing events "
                        "and cannot be deleted.",
                        "error"
                    )

                else:
                    cursor = db.execute(
                        """
                        DELETE FROM categories
                        WHERE category_id = ?
                        """,
                        (category_id,)
                    )

                    if cursor.rowcount:
                        db.commit()
                        flash("Category deleted.", "success")
                    else:
                        db.rollback()
                        flash("Category not found.", "error")

        else:
            flash("Invalid category action.", "error")

        return redirect(
            url_for(
                "category_pages.category_management_page",
                q=request.args.get("q", "")
            )
        )

    # VIEW AND SEARCH CATEGORIES

    query = request.args.get("q", "").strip()

    sql = """
        SELECT
            c.category_id,
            c.category_name,
            c.description,
            COUNT(e.event_id) AS event_count
        FROM categories c
        LEFT JOIN events e
            ON e.category_id = c.category_id
    """

    params = []

    if query:
        sql += """
            WHERE c.category_name LIKE ?
            OR c.description LIKE ?
        """

        params.extend([
            f"%{query}%",
            f"%{query}%"
        ])

    sql += """
        GROUP BY c.category_id
        ORDER BY c.category_name COLLATE NOCASE
    """

    categories = db.execute(sql, params).fetchall()

    return render_template(
        "admin/categories.html",
        categories=categories,
        query=query
    )