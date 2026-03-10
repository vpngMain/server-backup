"""Uživatelé - pouze admin."""
from flask import Blueprint, flash, g, redirect, render_template, request, url_for, abort
from flask_login import login_required, current_user

from app.models import User
from app.models.user import UserRole
from app.auth.password import hash_password
from app.utils.loaders import get_user_or_404

users_bp = Blueprint("users", __name__)


def _ctx():
    return {"request": request, "current_user": current_user, "dev_skip_auth": False}


def _require_admin():
    if not current_user.is_authenticated or not current_user.is_admin():
        abort(403)


@users_bp.route("")
@login_required
def list_():
    _require_admin()
    users = g.db.query(User).order_by(User.username).all()
    return render_template("users/list.html", **_ctx(), users=users)


@users_bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    _require_admin()
    if request.method == "POST":
        username_clean = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "user")
        if not username_clean:
            return redirect(url_for("users.new", error="empty_username"))
        if len(password) < 6:
            return redirect(url_for("users.new", error="short_password"))
        if g.db.query(User).filter(User.username == username_clean).first():
            return redirect(url_for("users.new", error="exists"))
        user = User(
            username=username_clean,
            password_hash=hash_password(password),
            role=role if role in ("admin", "user") else UserRole.user.value,
            is_active=True,
        )
        g.db.add(user)
        g.db.commit()
        flash("Uživatel byl vytvořen.", "success")
        return redirect(url_for("users.list_"))
    return render_template("users/form.html", **_ctx(), user=None)


@users_bp.route("/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
def edit(user_id):
    _require_admin()
    user = get_user_or_404(g.db, user_id)
    if request.method == "POST":
        user.username = request.form.get("username", "").strip()
        role = request.form.get("role", user.role)
        user.role = role if role in ("admin", "user") else user.role
        password = request.form.get("password", "")
        if password:
            user.password_hash = hash_password(password)
        g.db.commit()
        flash("Změny u uživatele byly uloženy.", "success")
        return redirect(url_for("users.list_"))
    return render_template("users/form.html", **_ctx(), user=user)
