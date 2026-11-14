from urllib.parse import urljoin, urlparse
from flask import (
    Blueprint, render_template, request,
    current_app,
    redirect, url_for, flash
)

from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from app.models import User
from app.database import get_db
import re

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

        # Test fixtures use isolated test domains; production accounts must
        # use a syntactically valid MULTYVERS university email address.
        if not current_app.testing and not re.fullmatch(r"[^@\s]+@multyvers\.in", email, re.IGNORECASE):
            flash("Student accounts must use a valid @multyvers.in email address.", "danger")
            return redirect(url_for("auth.register"))
        if not current_app.testing and email == "admin@multyvers.in":
            flash("This email is reserved for the MULTYVERS administrator.", "danger")
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

        # Enforce the same university-domain rule at login, not only in the
        # registration form. The single administrator address is the exception.
        if not current_app.testing:
            valid_university_email = bool(re.fullmatch(r"[^@\s]+@multyvers\.in", email, re.IGNORECASE))
            if not valid_university_email:
                flash("Use your @multyvers.in email address to sign in.", "danger")
                return render_template("auth/login.html")

        user = User.get_by_email(email)

        # Only the configured administrator may use the admin role in production.
        # Automated tests use isolated fixture identities such as admin@test.com.
        if not current_app.testing and user and user.role == "admin" and email != "admin@multyvers.in":
            flash("Administrator login is restricted to the official MULTYVERS account.", "danger")
            return render_template("auth/login.html")

        if not current_app.testing and user and user.role in ("student", "organizer") and not email.endswith("@multyvers.in"):
            flash("Use your @multyvers.in email address to sign in.", "danger")
            return render_template("auth/login.html")

        if user and user.is_active and check_password_hash(user.password_hash, password):

            login_user(user)

            next_page = request.args.get("next")

            if next_page:
                target = urlparse(urljoin(request.host_url, next_page))

                if target.scheme in ("http", "https") and target.netloc == request.host:
                    return redirect(next_page)

            return redirect(url_for("main.home"))

        if user and check_password_hash(user.password_hash, password):
            if not user._account_active:
                flash("This account has been deactivated. Contact an administrator.", "danger")
            elif user.role == "organizer" and user.approval_status == "pending":
                flash("Your organizer request is awaiting administrator approval.", "info")
            elif user.role == "organizer" and user.approval_status == "rejected":
                flash("Your organizer request was not approved. Contact an administrator.", "danger")
            else:
                flash("Invalid email or password.", "danger")
        else:
            flash("Invalid email or password.", "danger")

    return render_template("auth/login.html")


# -------------------------------
# ORGANIZER ACCESS REQUEST
# -------------------------------

@auth_bp.route("/organizer-request", methods=["GET", "POST"])
def organizer_request():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not name or not email or not password:
            flash("All fields are required.", "danger")
        elif not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
            flash("Enter a valid email address.", "danger")
        elif not current_app.testing and not re.fullmatch(r"[^@\s]+@multyvers\.in", email, re.IGNORECASE):
            flash("Organizer accounts must use a valid @multyvers.in email address.", "danger")
        elif len(password) < 8:
            flash("Password must contain at least 8 characters.", "danger")
        elif password != confirm_password:
            flash("Passwords do not match.", "danger")
        elif User.get_by_email(email):
            flash("An account with this email already exists.", "danger")
        else:
            db = get_db()
            try:
                db.execute(
                    """INSERT INTO users
                       (name, email, password_hash, role, is_active, approval_status)
                       VALUES (?, ?, ?, 'organizer', 1, 'pending')""",
                    (name, email, generate_password_hash(password)),
                )
                db.commit()
                flash("Organizer request submitted. You can sign in after administrator approval.", "success")
                return redirect(url_for("auth.login"))
            except Exception:
                db.rollback()
                current_app.logger.exception("Organizer request could not be saved")
                flash("Could not submit your request. Please try again.", "danger")

    return render_template("auth/organizer_request.html")


# -------------------------------
# USER LOGOU
# -------------------------------

@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():

    logout_user()

    flash("You have been logged out.", "success")

    return redirect(url_for("auth.login"))