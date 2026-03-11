"""API endpoint pro ověření přihlášení – používají ho odberos, objednavac, DPD."""
import re
from flask import Blueprint, request, jsonify
from config import PIN_MIN_LENGTH, PIN_MAX_LENGTH
from models import db, User, LoginLog

api_bp = Blueprint("api", __name__, url_prefix="/api")


def _pin_valid(pin: str) -> bool:
    if not pin or not isinstance(pin, str):
        return False
    pin = pin.strip()
    return PIN_MIN_LENGTH <= len(pin) <= PIN_MAX_LENGTH and re.match(r"^\d+$", pin) is not None


@api_bp.route("/login", methods=["POST"])
def login():
    """Ověří username + PIN, vrátí username, role, branch (a pro objednavac i role/warehouse)."""
    data = request.get_json(silent=True) or request.form
    username = (data.get("username") or "").strip()
    pin = (data.get("pin") or "").strip()
    application = (data.get("application") or request.headers.get("X-Application") or "").strip() or None

    if not username:
        return jsonify({"ok": False, "error": "Zadejte uživatelské jméno."}), 401
    if not _pin_valid(pin):
        return jsonify({"ok": False, "error": f"PIN musí být {PIN_MIN_LENGTH}-{PIN_MAX_LENGTH} číslic."}), 401

    user = User.query.filter_by(username=username, active=True).first()
    if not user or not user.check_pin(pin):
        return jsonify({"ok": False, "error": "Neplatné přihlašovací údaje."}), 401

    # Log
    log = LoginLog(
        username=user.username,
        ip=request.remote_addr,
        application=application,
    )
    db.session.add(log)
    db.session.commit()

    # Základní odpověď
    payload = {
        "ok": True,
        "username": user.username,
        "role": user.role,
        "branch": user.branch or "",
    }

    # Pro Objednávač: vrátit objednavac_role a warehouse
    if application == "objednavac" and user.objednavac_role:
        payload["role"] = user.objednavac_role
        payload["warehouse"] = user.warehouse or ""

    return jsonify(payload), 200
