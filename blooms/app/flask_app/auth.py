"""Přihlášení a odhlášení – Flask-Login."""
from flask import Blueprint, g, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user

from app.services.auth_service import authenticate_user

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    error = request.args.get("error")
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if not username or not password:
            return redirect(url_for("auth.login", error="empty"))
        user = authenticate_user(g.db, username, password)
        if not user:
            return redirect(url_for("auth.login", error="invalid"))
        login_user(user)
        return redirect(url_for("main.dashboard"))
    return render_template("auth/login.html", error=error, current_user=current_user, request=request, dev_skip_auth=False)


@auth_bp.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
