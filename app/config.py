import os
from pathlib import Path


# Project root directory
BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    """Base configuration for MULTYVERS."""

    # Application security
    SECRET_KEY = os.environ.get(
        "MULTYVERS_SECRET_KEY",
        "development-only-change-this-key"
    )

    # Database configuration
    DATABASE = str(
        BASE_DIR / "database" / "multyvers.db"
    )

    # Session security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Enable secure cookies when deployed over HTTPS
    SESSION_COOKIE_SECURE = (
        os.environ.get("COOKIE_SECURE", "false").lower() == "true"
    )

    # CSRF protection
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600

    # Application settings
    DEBUG = False
    TESTING = False