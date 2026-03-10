"""Import .xls - stranka, history, detail."""
import json
import logging
from decimal import Decimal

from flask import Blueprint, flash, g, redirect, render_template, request, url_for, abort
from flask_login import login_required, current_user

from app.services.import_service import (
    run_import_from_uploaded_files,
    get_price_conflicts_for_file,
    get_price_comparisons_for_file,
    apply_import_price,
    PRICE_FIELD_LABELS,
    ROW_DISPLAY_ONLY,
    ROW_EDIT_FIELDS,
    update_import_row_from_form,
)
from app.models import ImportBatch, ImportFile
from app.utils.loaders import get_import_batch_or_404, get_import_file_or_404, get_import_row_or_404

logger = logging.getLogger(__name__)
import_bp = Blueprint("import", __name__)

ERROR_MSGS = {
    "no_files": "Vyberte nebo přetáhněte alespoň jeden soubor .xls nebo .xlsx.",
    "empty_path": "Vyberte nebo přetáhněte alespoň jeden soubor .xls nebo .xlsx.",  # zpětná kompatibilita
    "import_failed": "Import se nezdařil.",
}


def _ctx():
    return {"request": request, "current_user": current_user, "dev_skip_auth": False}


@import_bp.route("/test-upload")
@login_required
def test_upload_page():
    """Minimální testovací formulář – když hlavní nefunguje."""
    return """<!DOCTYPE html><html><head><meta charset="utf-8"><title>Test</title></head><body>
<h1>Test uploadu</h1>
<form method="post" action="/import" enctype="multipart/form-data">
<input type="file" name="files" accept=".xls,.xlsx" required>
<button type="submit">Odeslat</button>
</form></body></html>"""


@import_bp.route("", methods=["GET", "POST"])
@login_required
def import_page():
    err_key = request.args.get("error") if request.method == "GET" else None
    if request.method == "GET" and err_key == "empty_path":
        return redirect("/import?error=no_files", code=302)
    if request.method == "POST":
        files = []
        for key in list(request.files.keys()):
            files.extend(request.files.getlist(key))
        xls = [f for f in files if f and getattr(f, "filename", None) and (f.filename.lower().endswith(".xls") or f.filename.lower().endswith(".xlsx"))]
        if not xls:
            return redirect("/import?error=no_files", code=302)  # když vidíš empty_path, restartuj server
        try:
            shipping_eur = None
            exchange_rate = None
            try:
                s = (request.form.get("shipping_eur") or "").strip().replace(",", ".")
                if s:
                    shipping_eur = Decimal(s)
            except Exception:
                pass
            try:
                e = (request.form.get("exchange_rate") or "").strip().replace(",", ".")
                if e:
                    exchange_rate = Decimal(e)
            except Exception:
                pass
            batch = run_import_from_uploaded_files(
                xls, g.db, created_by_user_id=current_user.id,
                shipping_eur=shipping_eur, exchange_rate=exchange_rate,
            )
            g.db.commit()
            g.db.refresh(batch)
            flash("Import proběhl. Zkontroluj níže všechny kontroly a ceny.", "success")
            # Hned přesměrovat na okno s kompletní kontrolou (první soubor z dávky)
            files = list(batch.import_files) if batch.import_files else []
            if files:
                first = files[0]
                return redirect(url_for("import.file_detail", batch_id=batch.id, file_id=first.id, just_imported=1))
            return redirect(url_for("import.history", success=1))
        except Exception:
            logger.exception("Import failed")
            flash("Import se nezdařil.", "danger")
            return redirect(url_for("import.import_page", error="import_failed"))
    error = ERROR_MSGS.get(err_key, err_key) if err_key else None
    return render_template("import/import.html", **_ctx(), error=error)


@import_bp.route("/history")
@login_required
def history():
    batches = g.db.query(ImportBatch).order_by(ImportBatch.imported_at.desc()).limit(100).all()
    return render_template("import/history.html", **_ctx(), batches=batches, success=request.args.get("success"))


@import_bp.route("/history/<int:batch_id>")
@login_required
def batch_detail(batch_id):
    batch = get_import_batch_or_404(g.db, batch_id)
    return render_template("import/detail.html", **_ctx(), batch=batch)


@import_bp.route("/history/<int:batch_id>/files/<int:file_id>/apply-import-price", methods=["POST"])
@login_required
def apply_import_price_route(batch_id, file_id):
    from decimal import Decimal
    get_import_batch_or_404(g.db, batch_id)
    get_import_file_or_404(g.db, batch_id, file_id)
    value_override = None
    raw = (request.form.get("value") or "").strip().replace(",", ".")
    if raw:
        try:
            value_override = Decimal(raw)
        except Exception:
            pass
    err = apply_import_price(
        g.db,
        int(request.form.get("import_row_id")),
        request.form.get("field_key"),
        value_override=value_override,
    )
    if not err:
        g.db.commit()
        flash("Cena uložena do produktu.", "success")
    else:
        flash(f"Chyba: {err}", "danger")
    return redirect(url_for("import.file_detail", batch_id=batch_id, file_id=file_id))


@import_bp.route("/history/<int:batch_id>/files/<int:file_id>")
@login_required
def file_detail(batch_id, file_id):
    batch = get_import_batch_or_404(g.db, batch_id)
    ifile = get_import_file_or_404(g.db, batch_id, file_id)
    rows_sorted = sorted(ifile.rows, key=lambda r: (r.row_index, r.id))
    rows_with_data = []
    for r in rows_sorted:
        try:
            data = json.loads(r.raw_data_json) if r.raw_data_json else {}
        except Exception:
            data = {}
        try:
            review_flags = json.loads(r.review_flags_json) if r.review_flags_json else []
        except Exception:
            review_flags = []
        rows_with_data.append({"row": r, "data": data, "review_flags": review_flags})
    filter_review = request.args.get("filter_review", "").strip()
    if filter_review:
        rows_with_data = [x for x in rows_with_data if filter_review in x.get("review_flags", [])]
    price_conflicts = get_price_conflicts_for_file(g.db, ifile)
    price_comparisons_by_row = get_price_comparisons_for_file(g.db, ifile)
    just_imported = request.args.get("just_imported") == "1"
    return render_template(
        "import/file_detail.html", **_ctx(),
        batch_id=batch_id, file_id=file_id, import_file=ifile, batch=batch,
        rows_with_data=rows_with_data,
        price_conflicts=price_conflicts,
        price_comparisons_by_row=price_comparisons_by_row,
        price_field_labels=PRICE_FIELD_LABELS,
        row_display_only=ROW_DISPLAY_ONLY,
        row_edit_fields=ROW_EDIT_FIELDS,
        just_imported=just_imported,
    )


@import_bp.route("/history/<int:batch_id>/files/<int:file_id>/rows/<int:row_id>/edit", methods=["GET", "POST"])
@login_required
def row_edit(batch_id, file_id, row_id):
    get_import_batch_or_404(g.db, batch_id)
    ifile = get_import_file_or_404(g.db, batch_id, file_id)
    row = get_import_row_or_404(g.db, file_id, row_id)
    try:
        data = json.loads(row.raw_data_json) if row.raw_data_json else {}
    except Exception:
        data = {}

    if request.method == "POST":
        form_data = {key: request.form.get(key) for key, _ in ROW_EDIT_FIELDS}
        err = update_import_row_from_form(g.db, row, form_data)
        if not err:
            g.db.commit()
            flash("Řádek a produkt (pokud existuje) byly uloženy.", "success")
            return redirect(url_for("import.file_detail", batch_id=batch_id, file_id=file_id))
        flash(f"Chyba: {err}", "danger")

    return render_template(
        "import/row_edit.html", **_ctx(),
        batch_id=batch_id, file_id=file_id, import_file=ifile, row=row, data=data,
        row_edit_fields=ROW_EDIT_FIELDS,
    )
