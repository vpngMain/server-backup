import re
from functools import wraps
from flask import session, redirect, request

from config import PIN_MIN_LENGTH, PIN_MAX_LENGTH


def pin_valid(pin: str) -> bool:
    """PIN 4–6 číslic."""
    if not pin or not isinstance(pin, str):
        return False
    pin = pin.strip()
    return (
        PIN_MIN_LENGTH <= len(pin) <= PIN_MAX_LENGTH
        and re.match(r"^\d+$", pin) is not None
    )


def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/login")
        return f(*args, **kwargs)
    return wrapped


def admin_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/login")
        if not session.get("is_admin"):
            return redirect("/user")
        return f(*args, **kwargs)
    return wrapped


def get_redirect_after_login():
    """Po přihlášení: admin -> /admin, user -> /user."""
    if session.get("is_admin"):
        return redirect("/admin")
    return redirect("/user")
