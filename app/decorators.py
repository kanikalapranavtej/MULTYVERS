from functools import wraps

from flask import abort
from flask_login import current_user, login_required


def role_required(*roles):
    """
    Restrict access to users with specified roles.
    """

    def decorator(view_function):

        @wraps(view_function)
        @login_required
        def decorated_function(*args, **kwargs):

            if current_user.role not in roles:
                abort(403)

            return view_function(*args, **kwargs)

        return decorated_function

    return decorator