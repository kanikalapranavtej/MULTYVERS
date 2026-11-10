from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect


# User authentication and session management
login_manager = LoginManager()


# Cross-Site Request Forgery protection
csrf = CSRFProtect()


def init_extensions(app):
    """Initialize Flask extensions."""

    login_manager.init_app(app)

    csrf.init_app(app)

    # Redirect unauthenticated users to login
    login_manager.login_view = "auth.login"

    # Category for login-related messages
    login_manager.login_message_category = "info"