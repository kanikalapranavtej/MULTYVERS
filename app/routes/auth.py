from urllib.parse import urljoin, urlparse
from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash
)

from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from app.models import User
from app.database import get_db

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


# -------------------------------
# USER REGISTRATION
# -------------------------------

@auth_bp.route("/register", methods=["GET", "POST"])
def register():

    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not name or not email or not password:
            flash("All fields are required.", "danger")
            return redirect(url_for("auth.register"))

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("auth.register"))

        if len(password) < 8:
            flash("Password must contain at least 8 characters.", "danger")
            return redirect(url_for("auth.register"))

        if User.get_by_email(email):
            flash("Email already registered.", "danger")
            return redirect(url_for("auth.register"))

        password_hash = generate_password_hash(password)

        db = get_db()

        try:
            db.execute(
                """
                INSERT INTO users (name, email, password_hash, role)
                VALUES (?, ?, ?, ?)
                """,
                (name, email, password_hash, "student")
            )

            db.commit()

            flash("Registration successful. Please log in.", "success")

            return redirect(url_for("auth.login"))

        except Exception:
            db.rollback()
            flash("Registration failed. Please try again.", "danger")

    return render_template("auth/register.html")


# -------------------------------
# USER LOGIN
# -------------------------------

@auth_bp.route("/login", methods=["GET", "POST"])
def login():

    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.get_by_email(email)

        if user and check_password_hash(user.password_hash, password):

            login_user(user)

            flash("Welcome back!", "success")

            next_page = request.args.get("next")

            if next_page:
                target = urlparse(urljoin(request.host_url, next_page))

                if target.scheme in ("http", "https") and target.netloc == request.host:
                    return redirect(next_page)

            return redirect(url_for("main.home"))

        flash("Invalid email or password.", "danger")

    return render_template("auth/login.html")


# -------------------------------
# USER LOGOU
# -------------------------------

@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():

    logout_user()

    flash("You have been logged out.", "success")

    return redirect(url_for("auth.login"))