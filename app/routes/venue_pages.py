from flask import Blueprint, render_template
from flask_login import current_user, login_required

venue_pages_bp = Blueprint("venue_pages", __name__)


@venue_pages_bp.route("/admin/venues")
@login_required
def venue_management_page():
    if current_user.role != "admin":
        from flask import abort
        abort(403)

    return render_template("admin/venues.html")