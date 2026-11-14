from flask_login import UserMixin

from app.database import get_db
from app.extensions import login_manager


class User(UserMixin):
    """
    Represents an authenticated MULTYVERS user.
    """

    def __init__(
        self,
        user_id,
        name,
        email,
        password_hash,
        role,
        created_at,
        is_active=1,
        approval_status="approved"
    ):

        self.id = user_id
        self.name = name
        self.email = email
        self.password_hash = password_hash
        self.role = role
        self.created_at = created_at

        self._account_active = bool(is_active)
        self.approval_status = approval_status

    @property
    def is_active(self):
        """
        Return whether the user account is active.
        """

        return self._account_active and (
            self.role != "organizer" or self.approval_status == "approved"
        )

    @is_active.setter
    def is_active(self, value):
        """
        Allow account status to be updated.
        """

        self._account_active = bool(value)

    @classmethod
    def from_row(cls, row):
        """
        Convert a SQLite row into a User object.
        """

        if row is None:
            return None

        return cls(
            user_id=row["user_id"],
            name=row["name"],
            email=row["email"],
            password_hash=row["password_hash"],
            role=row["role"],
            created_at=row["created_at"],
            is_active=row["is_active"] if "is_active" in row.keys() else 1,
            approval_status=(row["approval_status"] if "approval_status" in row.keys() else "approved")
        )

    @classmethod
    def get_by_id(cls, user_id):
        """
        Retrieve a user using their unique ID.
        """

        try:
            user_id = int(user_id)

        except (ValueError, TypeError):
            return None

        db = get_db()

        row = db.execute(
            """
            SELECT user_id, name, email,
                   password_hash, role, created_at, is_active, approval_status
            FROM users
            WHERE user_id = ?
            """,
            (user_id,)
        ).fetchone()

        return cls.from_row(row)

    @classmethod
    def get_by_email(cls, email):
        """
        Retrieve a user using their email.
        """

        db = get_db()

        row = db.execute(
            """
            SELECT user_id, name, email,
                   password_hash, role, created_at, is_active, approval_status
            FROM users
            WHERE email = ?
            """,
            (email,)
        ).fetchone()

        return cls.from_row(row)


@login_manager.user_loader
def load_user(user_id):
    """
    Load an authenticated user from their session ID.
    """

    return User.get_by_id(user_id)