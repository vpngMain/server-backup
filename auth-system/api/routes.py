"""API endpoint pro ověření přihlášení – používají ho odberos, objednavac, DPD."""
import os
import re
import secrets
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify
from config import PIN_MIN_LENGTH, PIN_MAX_LENGTH, SSO_SECRET, SSO_TOKEN_TTL_SECONDS
from models import db, User, LoginLog, Branch, Warehouse, user_branches, SSOToken

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/branches", methods=["GET"])
def branches_list():
    """Seznam všech poboček (pro sync do Odběros, Objednávač, DPD)."""
    branches = Branch.query.order_by(Branch.name).all()
    return jsonify([{"id": b.id, "name": b.name, "code": b.code or ""} for b in branches]), 200


@api_bp.route("/warehouses", methods=["GET"])
def warehouses_list():
    """Seznam všech skladů (pro sync do Objednávače)."""
    warehouses = Warehouse.query.order_by(Warehouse.name).all()
    return jsonify([{"id": w.id, "name": w.name, "code": w.code or ""} for w in warehouses]), 200


def _pin_valid(pin: str) -> bool:
    if not pin or not isinstance(pin, str):
        return False
    pin = pin.strip()
    return PIN_MIN_LENGTH <= len(pin) <= PIN_MAX_LENGTH and re.match(r"^\d+$", pin) is not None


def _user_can_access_app(user, application):
    """Vrátí True, pokud má uživatel přístup k dané aplikaci (podle allowed_apps). Admin má přístup všude. Směrovač (smeros) může každý."""
    if getattr(user, "role", None) == "admin":
        return True
    if not application or not isinstance(application, str):
        return True
    app_code = application.strip().lower()
    if not app_code:
        return True
    if app_code == "smeros":
        return True
    allowed = user.get_allowed_app_codes()
    return app_code in [a.lower() for a in allowed] if allowed else False


def _user_branches_payload(user):
    """Vrátí seznam {id, name} poboček uživatele. Čte z user_branches, fallback na relationship a user.branch."""
    out = []
    try:
        branches = Branch.query.join(user_branches, Branch.id == user_branches.c.branch_id).filter(
            user_branches.c.user_id == user.id
        ).all()
        for b in branches:
            out.append({"id": b.id, "name": b.name})
    except Exception:
        pass
    if not out:
        try:
            for b in user.branches.all():
                out.append({"id": b.id, "name": b.name})
        except Exception:
            pass
    if not out and getattr(user, "branch", None) and user.branch:
        out.append({"id": 0, "name": user.branch})
    return out


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

    user = User.find_by_username(username)
    if not user or not user.check_pin(pin):
        return jsonify({"ok": False, "error": "Neplatné přihlašovací údaje."}), 401

    # Kontrola přístupu k aplikaci (pokud je application uvedené)
    if application and not _user_can_access_app(user, application):
        return jsonify({"ok": False, "error": "Nemáte přístup k této aplikaci."}), 403

    # Log
    log = LoginLog(
        username=user.username,
        ip=request.remote_addr,
        application=application,
    )
    db.session.add(log)
    db.session.commit()

    branches_payload = _user_branches_payload(user)
    branch_name = (branches_payload[0]["name"] if branches_payload else None) or getattr(user, "branch", None) or ""

    payload = {
        "ok": True,
        "username": user.username,
        "role": user.role,
        "branch": branch_name,
        "branches": branches_payload,
        "allowed_apps": user.get_allowed_app_codes(),
    }

    # Pro Objednávač: vrátit objednavac_role a warehouse
    if application == "objednavac" and user.objednavac_role:
        payload["role"] = user.objednavac_role
        payload["warehouse"] = user.warehouse or ""

    return jsonify(payload), 200


# ---------- SSO (jednorázový token pro přechod ze Směrosu) ----------
def _user_payload(user):
    """Vrátí dict stejný jako /api/login pro daného uživatele."""
    branches_payload = _user_branches_payload(user)
    branch_name = (branches_payload[0]["name"] if branches_payload else None) or getattr(user, "branch", None) or ""
    out = {
        "ok": True,
        "username": user.username,
        "role": user.role,
        "branch": branch_name,
        "branches": branches_payload,
        "allowed_apps": user.get_allowed_app_codes(),
    }
    if user.objednavac_role:
        out["role"] = user.objednavac_role
        out["warehouse"] = user.warehouse or ""
    return out


@api_bp.route("/sso/create-token", methods=["POST"])
def sso_create_token():
    """Vytvoří jednorázový SSO token. Volá Směros (ověření SSO_SECRET)."""
    secret = (request.headers.get("X-SSO-Secret") or request.form.get("secret") or (request.get_json(silent=True) or {}).get("secret") or "").strip()
    if not SSO_SECRET or secret != SSO_SECRET:
        return jsonify({"ok": False, "error": "Neplatný požadavek."}), 403
    username = (request.form.get("username") or (request.get_json(silent=True) or {}).get("username") or "").strip()
    if not username:
        return jsonify({"ok": False, "error": "Chybí username."}), 400
    user = User.query.filter_by(username=username, active=True).first()
    if not user:
        return jsonify({"ok": False, "error": "Uživatel nenalezen."}), 404
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(seconds=SSO_TOKEN_TTL_SECONDS)
    sso = SSOToken(token=token, username=user.username, expires_at=expires_at)
    db.session.add(sso)
    db.session.commit()
    return jsonify({"ok": True, "token": token}), 200


@api_bp.route("/sso/verify", methods=["GET", "POST"])
def sso_verify():
    """Ověří SSO token a vrátí data uživatele (jako /api/login). Token se označí jako použitý."""
    token = (request.args.get("token") or request.form.get("token") or (request.get_json(silent=True) or {}).get("token") or "").strip()
    if not token:
        return jsonify({"ok": False, "error": "Chybí token."}), 400
    sso = SSOToken.query.filter_by(token=token, used=False).first()
    if not sso:
        return jsonify({"ok": False, "error": "Neplatný nebo již použitý token."}), 401
    if datetime.utcnow() > sso.expires_at:
        sso.used = True
        db.session.commit()
        return jsonify({"ok": False, "error": "Token vypršel."}), 401
    user = User.find_by_username(sso.username)
    if not user:
        sso.used = True
        db.session.commit()
        return jsonify({"ok": False, "error": "Uživatel nenalezen."}), 401
    application = (request.args.get("application") or request.form.get("application") or (request.get_json(silent=True) or {}).get("application") or "").strip() or None
    if application and not _user_can_access_app(user, application):
        return jsonify({"ok": False, "error": "Nemáte přístup k této aplikaci."}), 403
    sso.used = True
    db.session.commit()
    return jsonify(_user_payload(user)), 200
