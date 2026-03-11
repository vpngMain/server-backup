import os
from datetime import date, datetime, timedelta

try:
    import requests
except ImportError:
    requests = None

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
    session,
    send_file,
)
import io
import csv

from config import PIN_MIN_LENGTH, PIN_MAX_LENGTH
from models import (
    db,
    Branch,
    User,
    Entry,
    OBALKA_DENOMINATIONS,
    KASA_DENOMINATIONS,
    week_start,
    week_end,
    datum_splatnosti,
)
from auth import pin_valid, login_required, admin_required, get_redirect_after_login


def cs_date(d, format="short"):
    """Český formát data: short = dd/mm/yy."""
    if d is None:
        return ""
    if hasattr(d, "strftime"):
        return d.strftime("%d/%m/%y")
    return str(d)


class PrintEntryPreview:
    """Virtuální entry pro tisk obálky z dat formuláře (bez uložení)."""

    def __init__(self, obalka_dict, datum, tyden_zacatek, tyden_konec, datum_splatnosti, k_zaplaceni=None):
        self.datum = datum
        self.datum_splatnosti = datum_splatnosti
        self.tyden_zacatek = tyden_zacatek
        self.tyden_konec = tyden_konec
        self.k_zaplaceni = k_zaplaceni
        self._obalka = {str(k): int(v) if v else 0 for k, v in (obalka_dict or {}).items()}

    def obalka_dict(self):
        return self._obalka

    def celkem_obalka(self):
        return sum(
            (self._obalka.get(str(d), 0) or 0) * d
            for d in OBALKA_DENOMINATIONS
        )


def create_app():
    app = Flask(__name__)
    app.config.from_object("config")
    db.init_app(app)
    app.jinja_env.filters["cs_date"] = cs_date

    os.makedirs(os.path.join(app.root_path, "instance"), exist_ok=True)

    def _auth_api_login(username_val, pin_val):
        """Ověří přihlášení přes centrální auth API. Vrátí (data, None) nebo (None, error)."""
        if not requests:
            return None, "Modul requests není nainstalován."
        auth_url = (os.environ.get("AUTH_API_URL") or "http://localhost:8080").rstrip("/")
        try:
            r = requests.post(
                auth_url + "/api/login",
                json={"username": username_val, "pin": pin_val, "application": "dpd"},
                timeout=10,
            )
            data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            if r.status_code == 200 and data.get("ok"):
                return data, None
            return None, data.get("error", "Neplatné přihlašovací údaje.")
        except requests.RequestException as e:
            return None, str(e)

    # ---------- Login ----------
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "GET":
            if "user_id" in session:
                return get_redirect_after_login()
            return render_template("login.html")
        username = (request.get_json() or {}).get("username", "") if request.is_json else request.form.get("username", "")
        pin = (request.get_json() or {}).get("pin", "") if request.is_json else request.form.get("pin", "")
        username = (username or "").strip()
        pin = (pin or "").strip()
        if not username:
            if request.is_json:
                return jsonify({"ok": False, "error": "Zadejte uživatelské jméno."}), 400
            return render_template("login.html", error="Zadejte uživatelské jméno.")
        if not pin_valid(pin):
            if request.is_json:
                return jsonify({"ok": False, "error": "Zadejte platný PIN (4–6 číslic)."}), 400
            return render_template("login.html", error="Zadejte platný PIN (4–6 číslic).")
        data, err = _auth_api_login(username, pin)
        if err:
            if request.is_json:
                return jsonify({"ok": False, "error": err}), 401
            return render_template("login.html", error=err)
        role = data.get("role", "user")
        branch_name = (data.get("branch") or "").strip()
        branch = None
        if branch_name:
            branch = Branch.query.filter_by(name=branch_name).first()
            if not branch:
                branch = Branch(name=branch_name)
                db.session.add(branch)
                db.session.commit()
        user = User.query.filter_by(name=username).first()
        if not user:
            user = User(name=username, role=role, branch_id=branch.id if branch else None)
            user.set_pin(pin)
            db.session.add(user)
            db.session.commit()
        else:
            user.role = role
            user.branch_id = branch.id if branch else user.branch_id
            db.session.commit()
        session["user_id"] = user.id
        session["user_name"] = user.name
        session["branch_id"] = user.branch_id
        session["is_admin"] = user.is_admin
        session.permanent = True
        if request.is_json:
            return jsonify({"ok": True, "redirect": "/admin" if user.is_admin else "/user"})
        return get_redirect_after_login()

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    # ---------- User: formulář Obálka + Kasička ----------
    @app.route("/user")
    @login_required
    def user_index():
        branches = Branch.query.order_by(Branch.name).all() if session.get("is_admin") else None
        return render_template(
            "user_index.html",
            obalka_denoms=OBALKA_DENOMINATIONS,
            kasa_denoms=KASA_DENOMINATIONS,
            branches=branches,
        )

    @app.route("/api/entry/today")
    @login_required
    def api_entry_today():
        branch_id = session.get("branch_id")
        if session.get("is_admin"):
            branch_id = request.args.get("branch_id", type=int) or branch_id
        if not branch_id:
            return jsonify({"ok": True, "entry": None})
        today = date.today()
        entry = Entry.query.filter_by(branch_id=branch_id, datum=today).first()
        if not entry:
            return jsonify({"ok": True, "entry": None})
        out = {
            "obalka": entry.obalka_dict(),
            "kasa": entry.kasa_dict(),
        }
        if entry.k_zaplaceni is not None:
            out["k_zaplaceni"] = float(entry.k_zaplaceni)
        return jsonify({"ok": True, "entry": out})

    @app.route("/api/entry", methods=["POST"])
    @login_required
    def api_entry():
        data = request.get_json() or {}
        if not isinstance(data, dict):
            return jsonify({"ok": False, "error": "Neplatná data."}), 400
        branch_id = session.get("branch_id")
        if session.get("is_admin"):
            bid = data.get("branch_id")
            if bid is not None:
                try:
                    branch_id = int(bid)
                except (TypeError, ValueError):
                    branch_id = None
            if not branch_id:
                return jsonify({"ok": False, "error": "Vyberte pobočku."}), 400
            if not Branch.query.get(branch_id):
                return jsonify({"ok": False, "error": "Neplatná pobočka."}), 400
        elif not branch_id:
            return jsonify({"ok": False, "error": "Nemáte přiřazenou pobočku."}), 403
        today = date.today()
        tyden_z = week_start(today)
        tyden_k = week_end(today)
        splatnost = datum_splatnosti(today)

        obalka = data.get("obalka") if isinstance(data.get("obalka"), dict) else {}
        kasa = data.get("kasa") if isinstance(data.get("kasa"), dict) else {}

        tyden_z_param = data.get("tyden_zacatek")
        if tyden_z_param:
            try:
                d = datetime.strptime(tyden_z_param, "%Y-%m-%d").date()
                if d.weekday() != 0:
                    return jsonify({"ok": False, "error": "Datum týdne musí být pondělí."}), 400
                if d > today:
                    return jsonify({"ok": False, "error": "Týden nesmí být v budoucnosti."}), 400
                max_back = today - timedelta(days=7 * 4)
                if d < max_back:
                    return jsonify({"ok": False, "error": "Lze evidovat nejvýše 4 týdny dozadu."}), 400
                tyden_z = d
                tyden_k = week_end(tyden_z)
                splatnost = datum_splatnosti(tyden_z)
            except (ValueError, TypeError):
                pass

        def safe_int(v):
            try:
                n = int(v)
                return max(0, n)
            except (TypeError, ValueError):
                return 0

        obalka_vals = [safe_int(obalka.get(str(d), 0)) for d in OBALKA_DENOMINATIONS]
        kasa_vals = [safe_int(kasa.get(str(d), 0)) for d in KASA_DENOMINATIONS]

        k_zaplaceni_val = None
        if data.get("k_zaplaceni") is not None and data.get("k_zaplaceni") != "":
            try:
                k_zaplaceni_val = float(data["k_zaplaceni"])
                if k_zaplaceni_val < 0:
                    k_zaplaceni_val = None
            except (TypeError, ValueError):
                pass

        existing = Entry.query.filter_by(branch_id=branch_id, datum=today).first()
        if existing:
            for col, val in zip(Entry.OBALKA_COLS, obalka_vals):
                setattr(existing, col, val)
            for col, val in zip(Entry.KASA_COLS, kasa_vals):
                setattr(existing, col, val)
            existing.tyden_zacatek = tyden_z
            existing.tyden_konec = tyden_k
            existing.datum_splatnosti = splatnost
            existing.k_zaplaceni = k_zaplaceni_val
            entry = existing
        else:
            entry = Entry(
                branch_id=branch_id,
                user_id=session["user_id"],
                datum=today,
                datum_splatnosti=splatnost,
                tyden_zacatek=tyden_z,
                tyden_konec=tyden_k,
                k_zaplaceni=k_zaplaceni_val,
            )
            for col, val in zip(Entry.OBALKA_COLS, obalka_vals):
                setattr(entry, col, val)
            for col, val in zip(Entry.KASA_COLS, kasa_vals):
                setattr(entry, col, val)
            db.session.add(entry)
        db.session.commit()
        msg = "Data byla aktualizována." if existing else "Data byla uložena."
        return jsonify({"ok": True, "message": msg, "entry_id": entry.id})

    # ---------- Tisk obálky ----------
    @app.route("/print/obalka", methods=["GET", "POST"])
    @login_required
    def print_obalka():
        branch_id = session.get("branch_id")
        branch = Branch.query.get(branch_id) if branch_id else None
        branch_name = branch.name if branch else ""

        if request.method == "POST" and request.is_json:
            data = request.get_json() or {}
            bid = data.get("branch_id")
            if bid is not None:
                try:
                    bid = int(bid)
                    b = Branch.query.get(bid)
                    if b:
                        branch_id = bid
                        branch = b
                        branch_name = b.name
                except (TypeError, ValueError):
                    pass
            obalka = data.get("obalka") if isinstance(data.get("obalka"), dict) else {}
            today = date.today()
            datum = today
            if data.get("datum"):
                try:
                    datum = datetime.strptime(data["datum"], "%Y-%m-%d").date()
                except (ValueError, TypeError):
                    pass
            tyden_z = data.get("tyden_zacatek")
            tyden_k = data.get("tyden_konec")
            splatnost = data.get("datum_splatnosti")
            if tyden_z:
                try:
                    tyden_z = datetime.strptime(tyden_z, "%Y-%m-%d").date()
                except (ValueError, TypeError):
                    tyden_z = week_start(datum)
            else:
                tyden_z = week_start(datum)
            if tyden_k:
                try:
                    tyden_k = datetime.strptime(tyden_k, "%Y-%m-%d").date()
                except (ValueError, TypeError):
                    tyden_k = week_end(datum)
            else:
                tyden_k = week_end(datum)
            if splatnost:
                try:
                    splatnost = datetime.strptime(splatnost, "%Y-%m-%d").date()
                except (ValueError, TypeError):
                    splatnost = datum_splatnosti(datum)
            else:
                splatnost = datum_splatnosti(datum)
            k_zaplaceni_preview = None
            if data.get("k_zaplaceni") is not None and data.get("k_zaplaceni") != "":
                try:
                    k_zaplaceni_preview = float(data["k_zaplaceni"])
                    if k_zaplaceni_preview < 0:
                        k_zaplaceni_preview = None
                except (TypeError, ValueError):
                    pass
            entry = PrintEntryPreview(obalka, datum, tyden_z, tyden_k, splatnost, k_zaplaceni_preview)
            return render_template(
                "print_obalka.html",
                entry=entry,
                branch_name=branch_name,
                denoms=OBALKA_DENOMINATIONS,
            )

        today = date.today()
        entry = Entry.query.filter_by(branch_id=branch_id, datum=today).first() if branch_id else None
        if not entry and branch_id:
            entry = Entry.query.filter_by(branch_id=branch_id).order_by(Entry.datum.desc()).first()
        if not entry:
            return render_template("print_obalka.html", entry=None, branch_name=branch_name)
        return render_template(
            "print_obalka.html",
            entry=entry,
            branch_name=branch_name,
            denoms=OBALKA_DENOMINATIONS,
        )

    # ---------- Admin ----------
    @app.route("/admin")
    @login_required
    @admin_required
    def admin_dashboard():
        branches = Branch.query.order_by(Branch.name).all()
        return render_template("admin_dashboard.html", branches=branches)

    @app.route("/admin/branches")
    @login_required
    @admin_required
    def admin_branches():
        return render_template("admin_branches.html")

    @app.route("/admin/users")
    @login_required
    @admin_required
    def admin_users():
        branches = Branch.query.order_by(Branch.name).all()
        return render_template("admin_users.html", branches=branches)

    @app.route("/api/admin/branches", methods=["GET", "POST"])
    @login_required
    @admin_required
    def api_admin_branches():
        if request.method == "GET":
            branches = Branch.query.order_by(Branch.name).all()
            return jsonify([{"id": b.id, "name": b.name, "code": b.code or ""} for b in branches])
        data = request.get_json() or {}
        name = (data.get("name") or "").strip()
        code = (data.get("code") or "").strip()
        if not name:
            return jsonify({"ok": False, "error": "Název pobočky je povinný."}), 400
        if Branch.query.filter(Branch.name == name).first():
            return jsonify({"ok": False, "error": "Pobočka s tímto názvem již existuje."}), 400
        branch = Branch(name=name, code=code)
        db.session.add(branch)
        db.session.commit()
        return jsonify({"ok": True, "branch": {"id": branch.id, "name": branch.name, "code": branch.code or ""}})

    @app.route("/api/admin/branches/<int:branch_id>", methods=["GET", "PUT", "DELETE"])
    @login_required
    @admin_required
    def api_admin_branch(branch_id):
        branch = Branch.query.get(branch_id)
        if not branch:
            return jsonify({"ok": False, "error": "Pobočka nenalezena."}), 404
        if request.method == "GET":
            return jsonify({"ok": True, "branch": {"id": branch.id, "name": branch.name, "code": branch.code or ""}})
        if request.method == "DELETE":
            if User.query.filter_by(branch_id=branch_id).first():
                return jsonify({"ok": False, "error": "Pobočka má přiřazené uživatele. Nejprve je odeberte."}), 400
            db.session.delete(branch)
            db.session.commit()
            return jsonify({"ok": True})
        data = request.get_json() or {}
        name = (data.get("name") or "").strip()
        code = (data.get("code") or "").strip()
        if not name:
            return jsonify({"ok": False, "error": "Název pobočky je povinný."}), 400
        other = Branch.query.filter(Branch.name == name, Branch.id != branch_id).first()
        if other:
            return jsonify({"ok": False, "error": "Pobočka s tímto názvem již existuje."}), 400
        branch.name = name
        branch.code = code
        db.session.commit()
        return jsonify({"ok": True, "branch": {"id": branch.id, "name": branch.name, "code": branch.code or ""}})

    @app.route("/api/admin/users", methods=["GET", "POST"])
    @login_required
    @admin_required
    def api_admin_users():
        if request.method == "GET":
            users = User.query.order_by(User.name).all()
            out = []
            for u in users:
                branch = Branch.query.get(u.branch_id) if u.branch_id else None
                out.append({
                    "id": u.id,
                    "name": u.name,
                    "branch_id": u.branch_id,
                    "branch_name": branch.name if branch else "",
                    "role": u.role or "user",
                })
            return jsonify(out)
        data = request.get_json() or {}
        name = (data.get("name") or "").strip()
        branch_id = data.get("branch_id")
        role = (data.get("role") or "user").strip()
        pin = (data.get("pin") or "").strip()
        if not name:
            return jsonify({"ok": False, "error": "Jméno je povinné."}), 400
        if role not in ("user", "admin"):
            return jsonify({"ok": False, "error": "Neplatná role."}), 400
        if not pin_valid(pin):
            return jsonify({"ok": False, "error": f"PIN musí mít {PIN_MIN_LENGTH}–{PIN_MAX_LENGTH} číslic."}), 400
        if branch_id is not None and branch_id != "":
            branch_id = int(branch_id)
            if not Branch.query.get(branch_id):
                return jsonify({"ok": False, "error": "Neplatná pobočka."}), 400
        else:
            branch_id = None
        user = User(name=name, branch_id=branch_id, role=role)
        user.set_pin(pin)
        db.session.add(user)
        db.session.commit()
        return jsonify({"ok": True, "user": {"id": user.id, "name": user.name, "branch_id": user.branch_id, "branch_name": Branch.query.get(user.branch_id).name if user.branch_id else "", "role": user.role}})

    @app.route("/api/admin/users/<int:user_id>", methods=["GET", "PUT", "DELETE"])
    @login_required
    @admin_required
    def api_admin_user(user_id):
        user = User.query.get(user_id)
        if not user:
            return jsonify({"ok": False, "error": "Uživatel nenalezen."}), 404
        if request.method == "GET":
            branch = Branch.query.get(user.branch_id) if user.branch_id else None
            return jsonify({"ok": True, "user": {"id": user.id, "name": user.name, "branch_id": user.branch_id, "branch_name": branch.name if branch else "", "role": user.role}})
        if request.method == "DELETE":
            db.session.delete(user)
            db.session.commit()
            return jsonify({"ok": True})
        data = request.get_json() or {}
        name = (data.get("name") or "").strip()
        branch_id = data.get("branch_id")
        role = (data.get("role") or "user").strip()
        pin = (data.get("pin") or "").strip()
        if not name:
            return jsonify({"ok": False, "error": "Jméno je povinné."}), 400
        if role not in ("user", "admin"):
            return jsonify({"ok": False, "error": "Neplatná role."}), 400
        if branch_id is not None and branch_id != "":
            branch_id = int(branch_id)
            if not Branch.query.get(branch_id):
                return jsonify({"ok": False, "error": "Neplatná pobočka."}), 400
        else:
            branch_id = None
        user.name = name
        user.branch_id = branch_id
        user.role = role
        if pin:
            if not pin_valid(pin):
                return jsonify({"ok": False, "error": f"PIN musí mít {PIN_MIN_LENGTH}–{PIN_MAX_LENGTH} číslic."}), 400
            user.set_pin(pin)
        db.session.commit()
        return jsonify({"ok": True, "user": {"id": user.id, "name": user.name, "branch_id": user.branch_id, "branch_name": Branch.query.get(user.branch_id).name if user.branch_id else "", "role": user.role}})

    @app.route("/api/admin/entries")
    @login_required
    @admin_required
    def api_admin_entries():
        branch_id = request.args.get("branch_id", type=int)
        tyden = request.args.get("tyden")  # YYYY-MM-DD pondělí
        mesic = request.args.get("mesic")  # YYYY-MM
        q = Entry.query.join(Branch).order_by(Entry.datum.desc())
        if branch_id:
            q = q.filter(Entry.branch_id == branch_id)
        if tyden:
            try:
                d = datetime.strptime(tyden, "%Y-%m-%d").date()
                q = q.filter(Entry.tyden_zacatek == d)
            except ValueError:
                pass
        if mesic:
            try:
                year, month = int(mesic[:4]), int(mesic[5:7])
                from calendar import monthrange
                first = date(year, month, 1)
                last_day = monthrange(year, month)[1]
                last = date(year, month, last_day)
                q = q.filter(Entry.datum >= first, Entry.datum <= last)
            except (ValueError, IndexError):
                pass
        entries = q.limit(500).all()
        out = []
        for e in entries:
            branch = Branch.query.get(e.branch_id)
            out.append({
                "id": e.id,
                "branch_id": e.branch_id,
                "datum": e.datum.isoformat(),
                "tyden_zacatek": e.tyden_zacatek.isoformat(),
                "tyden_konec": e.tyden_konec.isoformat(),
                "pobocka": branch.name if branch else "",
                "k_zaplaceni": float(e.k_zaplaceni) if e.k_zaplaceni is not None else None,
                "obalka_celkem": e.celkem_obalka(),
                "kasa_celkem": e.celkem_kasa(),
            })
        return jsonify(out)

    @app.route("/api/admin/entries/<int:entry_id>")
    @login_required
    @admin_required
    def api_admin_entry_detail(entry_id):
        entry = Entry.query.get(entry_id)
        if not entry:
            return jsonify({"ok": False, "error": "Záznam nenalezen."}), 404
        branch = Branch.query.get(entry.branch_id)
        user = User.query.get(entry.user_id)
        return jsonify({
            "ok": True,
            "entry": {
                "id": entry.id,
                "datum": entry.datum.isoformat(),
                "tyden_zacatek": entry.tyden_zacatek.isoformat(),
                "tyden_konec": entry.tyden_konec.isoformat(),
                "datum_splatnosti": entry.datum_splatnosti.isoformat(),
                "pobocka": branch.name if branch else "",
                "uzivatel": user.name if user else "",
                "k_zaplaceni": float(entry.k_zaplaceni) if entry.k_zaplaceni is not None else None,
                "obalka": entry.obalka_dict(),
                "kasa": entry.kasa_dict(),
                "obalka_celkem": entry.celkem_obalka(),
                "kasa_celkem": entry.celkem_kasa(),
            },
        })

    @app.route("/api/admin/export")
    @login_required
    @admin_required
    def api_admin_export():
        branch_id = request.args.get("branch_id", type=int)
        tyden = request.args.get("tyden")
        q = Entry.query.join(Branch).order_by(Entry.datum.desc())
        if branch_id:
            q = q.filter(Entry.branch_id == branch_id)
        if tyden:
            try:
                d = datetime.strptime(tyden, "%Y-%m-%d").date()
                q = q.filter(Entry.tyden_zacatek == d)
            except ValueError:
                pass
        entries = q.limit(2000).all()
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["Datum", "Týden (po-ne)", "Pobočka", "K zaplacení", "V hotovosti (Obálka)", "Zbylo v kasičce"])
        for e in entries:
            branch = Branch.query.get(e.branch_id)
            tyden_str = f"{e.tyden_zacatek} – {e.tyden_konec}" if e.tyden_zacatek else ""
            w.writerow([
                e.datum,
                tyden_str,
                branch.name if branch else "",
                e.k_zaplaceni or "",
                e.celkem_obalka(),
                e.celkem_kasa(),
            ])
        buf.seek(0)
        return send_file(
            io.BytesIO(buf.getvalue().encode("utf-8-sig")),
            mimetype="text/csv",
            as_attachment=True,
            download_name="evidence_hotovosti.csv",
        )

    # ---------- Root ----------
    @app.route("/")
    def index():
        if "user_id" in session:
            return get_redirect_after_login()
        return redirect(url_for("login"))

    return app


app = create_app()


@app.cli.command("init-db")
def init_db():
    """Vytvoří tabulky a výchozí data (1 pobočka, 1 user, 1 admin)."""
    db.create_all()
    if Branch.query.first() is None:
        b1 = Branch(name="Praha", code="PRA")
        b2 = Branch(name="Brno", code="BRN")
        db.session.add_all([b1, b2])
        db.session.commit()
        u1 = User(name="Pepa", branch_id=b1.id, role="user")
        u1.set_pin("1234")
        u2 = User(name="Evžen", branch_id=b2.id, role="user")
        u2.set_pin("1234")
        admin = User(name="Admin", branch_id=None, role="admin")
        admin.set_pin("0000")
        db.session.add_all([u1, u2, admin])
        db.session.commit()
        print("DB inicializována. User PIN: 1234, Admin PIN: 0000")
    else:
        print("DB již existuje.")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
