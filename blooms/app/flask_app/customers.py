"""Odběratelé – CRUD + import z ARES."""
from sqlalchemy import or_

from flask import Blueprint, flash, g, redirect, render_template, request, url_for, jsonify, current_app
from flask_login import login_required, current_user

from app.models import Customer
from app.services.ares_service import fetch_by_ico, search_by_name, AresResult
from app.utils.loaders import get_customer_or_404

customers_bp = Blueprint("customers", __name__)


def _ctx():
    return {"request": request, "current_user": current_user, "dev_skip_auth": False}


def _ares_to_customer(a: AresResult) -> Customer:
    """Vytvoří Customer z AresResult."""
    return Customer(
        company_name=a.company_name,
        ico=a.ico,
        dic=a.dic,
        street=a.street,
        city=a.city,
        zip_code=a.zip_code,
        country=a.country,
    )


@customers_bp.route("/import_ares", methods=["GET", "POST"])
@customers_bp.route("/import-ares", methods=["GET", "POST"])
@login_required
def import_ares():
    """Import odběratele z ARES – podle IČO nebo obchodního názvu."""
    if request.method == "GET":
        return render_template("customers/import_ares.html", **_ctx(), results=[], error=None, query="")
    query = (request.form.get("q") or request.args.get("q") or "").strip()
    if not query:
        return render_template("customers/import_ares.html", **_ctx(), results=[], error="Zadejte IČO nebo obchodní název.", query="")
    ico_digits = "".join(c for c in query if c.isdigit())
    if len(ico_digits) == 8:
        result = fetch_by_ico(query)
        if result.error:
            return render_template("customers/import_ares.html", **_ctx(), results=[], error=result.error, query=query)
        if request.form.get("confirm") == "1":
            c = _ares_to_customer(result)
            g.db.add(c)
            g.db.commit()
            return redirect(url_for("customers.detail", customer_id=c.id))
        return render_template("customers/import_ares.html", **_ctx(), results=[result], error=None, query=query)
    results, err = search_by_name(query)
    if err:
        return render_template("customers/import_ares.html", **_ctx(), results=[], error=err, query=query)
    if request.form.get("confirm_ico"):
        chosen_ico = request.form.get("confirm_ico")
        chosen = next((r for r in results if r.ico == chosen_ico), None)
        if chosen:
            c = _ares_to_customer(chosen)
            g.db.add(c)
            g.db.commit()
            return redirect(url_for("customers.detail", customer_id=c.id))
    return render_template("customers/import_ares.html", **_ctx(), results=results, error=None, query=query)


@customers_bp.route("/ares_lookup")
@customers_bp.route("/ares-lookup")
@login_required
def ares_lookup():
    """API: Načte data z ARES – podle IČO (ico=) nebo názvu (q=). Vrací JSON."""
    ico = (request.args.get("ico") or "").strip().replace(" ", "")
    q = (request.args.get("q") or "").strip()
    if len(ico) == 8:
        result = fetch_by_ico(ico)
        if result.error:
            return jsonify({"error": result.error})
        return jsonify({
            "ok": True,
            "result": {
                "company_name": result.company_name,
                "ico": result.ico,
                "dic": result.dic,
                "street": result.street,
                "city": result.city,
                "zip_code": result.zip_code,
                "country": result.country,
            },
        })
    if q:
        results, err = search_by_name(q, limit=10)
        if err:
            return jsonify({"error": err})
        return jsonify({
            "ok": True,
            "results": [
                {"company_name": r.company_name, "ico": r.ico, "dic": r.dic,
                 "street": r.street, "city": r.city, "zip_code": r.zip_code, "country": r.country}
                for r in results
            ],
        })
    return jsonify({"error": "Zadejte IČO (8 číslic) nebo název (parametr q)"})


@customers_bp.route("")
@login_required
def customer_list():
    q = request.args.get("q", "")
    query = g.db.query(Customer)
    if q:
        query = query.filter(
            or_(
                Customer.company_name.ilike(f"%{q}%"),
                Customer.ico.ilike(f"%{q}%"),
                Customer.email.ilike(f"%{q}%"),
            )
        )
    customers = query.order_by(Customer.company_name).limit(300).all()
    use_tabulator = bool(current_app.config.get("USE_TABULATOR", True))
    customers_rows_compact = []
    if use_tabulator:
        for c in customers:
            customers_rows_compact.append({
                "id": c.id,
                "company_name": c.company_name or "",
                "ico": c.ico or "",
                "city": c.city or "",
                "email": c.email or "",
                "price_level": c.price_level or "",
                "detail_url": url_for("customers.detail", customer_id=c.id),
            })
    return render_template(
        "customers/list.html",
        **_ctx(),
        customers=customers,
        q=q,
        use_tabulator=use_tabulator,
        customers_rows_compact=customers_rows_compact,
    )


@customers_bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    if request.method == "POST":
        c = Customer(
            company_name=request.form.get("company_name", "").strip(),
            ico=(request.form.get("ico") or "").strip() or None,
            dic=(request.form.get("dic") or "").strip() or None,
            street=(request.form.get("street") or "").strip() or None,
            city=(request.form.get("city") or "").strip() or None,
            zip_code=(request.form.get("zip_code") or "").strip() or None,
            country=(request.form.get("country") or "").strip() or None,
            provozovna_street=(request.form.get("provozovna_street") or "").strip() or None,
            provozovna_city=(request.form.get("provozovna_city") or "").strip() or None,
            provozovna_zip_code=(request.form.get("provozovna_zip_code") or "").strip() or None,
            provozovna_country=(request.form.get("provozovna_country") or "").strip() or None,
            contact_person=(request.form.get("contact_person") or "").strip() or None,
            phone=(request.form.get("phone") or "").strip() or None,
            email=(request.form.get("email") or "").strip() or None,
            note=(request.form.get("note") or "").strip() or None,
            price_level=(request.form.get("price_level") or "").strip() or None,
        )
        g.db.add(c)
        g.db.commit()
        flash("Odběratel byl vytvořen.", "success")
        return redirect(url_for("customers.customer_list"))
    return render_template("customers/form.html", **_ctx(), customer=None)


@customers_bp.route("/<int:customer_id>")
@login_required
def detail(customer_id):
    customer = get_customer_or_404(g.db, customer_id)
    return render_template("customers/detail.html", **_ctx(), customer=customer)


@customers_bp.route("/<int:customer_id>/edit", methods=["GET", "POST"])
@login_required
def edit(customer_id):
    customer = get_customer_or_404(g.db, customer_id)
    if request.method == "POST":
        customer.company_name = request.form.get("company_name", "").strip()
        customer.ico = (request.form.get("ico") or "").strip() or None
        customer.dic = (request.form.get("dic") or "").strip() or None
        customer.street = (request.form.get("street") or "").strip() or None
        customer.city = (request.form.get("city") or "").strip() or None
        customer.zip_code = (request.form.get("zip_code") or "").strip() or None
        customer.country = (request.form.get("country") or "").strip() or None
        customer.provozovna_street = (request.form.get("provozovna_street") or "").strip() or None
        customer.provozovna_city = (request.form.get("provozovna_city") or "").strip() or None
        customer.provozovna_zip_code = (request.form.get("provozovna_zip_code") or "").strip() or None
        customer.provozovna_country = (request.form.get("provozovna_country") or "").strip() or None
        customer.contact_person = (request.form.get("contact_person") or "").strip() or None
        customer.phone = (request.form.get("phone") or "").strip() or None
        customer.email = (request.form.get("email") or "").strip() or None
        customer.note = (request.form.get("note") or "").strip() or None
        customer.price_level = (request.form.get("price_level") or "").strip() or None
        g.db.commit()
        flash("Změny u odběratele byly uloženy.", "success")
        return redirect(url_for("customers.detail", customer_id=customer_id))
    return render_template("customers/form.html", **_ctx(), customer=customer)
