from flask import Blueprint, render_template

from app.decorators import role_required


analytics_pages_bp = Blueprint("analytics_pages", __name__)


@analytics_pages_bp.route("/analytics/dashboard")
@role_required("organizer", "admin")
def analytics_dashboard():

    return render_template("analytics/dashboard.html")