"""Importní service – orchestrace importu složky .xls do DB, summary a report po řádcích."""
from __future__ import annotations

import json
import logging
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Product, ImportBatch, ImportFile, ImportRow
from app.models.import_batch import ImportStatus, RowAction, MatchConfidence
from app.utils.normalizer import product_key_normalized
from app.services.import_parser import parse_xls_file, ParsedXlsResult, RowParseError
from app.services.order_number_parser import extract_order_number
from app.services.price_formulas import compute_prices_from_row as compute_prices_from_formulas

logger = logging.getLogger(__name__)


@dataclass
class FileImportSummary:
    """Shrnutí importu jednoho souboru."""
    filename: str
    order_number: Optional[str]
    row_count: int
    new_products: int
    existing_products: int
    skipped_rows: int
    error_rows: int
    warnings: list[str] = field(default_factory=list)
    row_errors: list[tuple[int, str]] = field(default_factory=list)  # (row_index, message)


@dataclass
class ImportSummary:
    """Celkové shrnutí importní dávky."""
    source_folder: str
    total_files: int
    total_rows: int
    new_products: int
    existing_products: int
    error_rows: int
    files: list[FileImportSummary] = field(default_factory=list)

    def to_text(self) -> str:
        lines = [
            f"Složka: {self.source_folder}",
            f"Soubory: {self.total_files} | Řádky: {self.total_rows}",
            f"Nové produkty: {self.new_products} | Existující: {self.existing_products} | Chyby: {self.error_rows}",
            "",
        ]
        for f in self.files:
            lines.append(f"  {f.filename}: {f.row_count} řádků, {f.new_products} nových, {f.existing_products} exist., {f.error_rows} chyb")
        return "\n".join(lines)


def _decimal(val) -> Optional[Decimal]:
    if val is None:
        return None
    try:
        return Decimal(str(val))
    except Exception:
        return None


def _decimal2(val) -> Optional[Decimal]:
    """Decimal zaokrouhlený na 2 desetinná místa (pro ceny)."""
    d = _decimal(val)
    if d is None:
        return None
    try:
        return d.quantize(_PRICE_QUANTIZE)
    except Exception:
        return d


_PRICE_QUANTIZE = Decimal("0.01")  # 2 desetinná místa (zápis do DB)


def _str(val) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


def match_row_to_product(db: Session, row: dict) -> tuple[Optional[Product], MatchConfidence]:
    """
    Přiřadí řádek potvrzení k produktu. Priorita: EAN → VBN → product_key_normalized.
    Vrací (produkt nebo None, confidence).
    """
    ean = _str(row.get("ean_code"))
    vbn = _str(row.get("vbn_code"))
    desc = _str(row.get("description"))
    pot = _str(row.get("pot_size"))
    key = product_key_normalized(desc, pot) if desc else None

    if ean:
        product = db.query(Product).filter(Product.ean_code == ean).first()
        if product:
            return product, MatchConfidence.exact_match
    if vbn:
        product = db.query(Product).filter(Product.vbn_code == vbn).first()
        if product:
            return product, MatchConfidence.exact_match
    if key:
        product = db.query(Product).filter(Product.product_key_normalized == key).first()
        if product:
            return product, MatchConfidence.probable_match
    return None, MatchConfidence.no_match


def detect_price_changes(
    db: Session,
    matched_product_id: Optional[int],
    computed: dict,
    row: dict,
    threshold_pct: float = 5.0,
) -> dict:
    """
    Pro review: aktuální efektivní ceny produktu, delta %, příznaky.
    computed: výstup z price_formulas.compute_prices_from_row (klíče vip_eur_imported, vip_czk_imported, trade_price_imported).
    """
    result = {
        "current_effective_vip_eur": None,
        "current_effective_vip_czk": None,
        "current_effective_d1": None,
        "delta_vip_eur_pct": None,
        "delta_vip_czk_pct": None,
        "delta_d1_pct": None,
        "review_flags": [],
    }
    if not matched_product_id:
        result["review_flags"].append("no_product")
        return result
    product = db.query(Product).filter(Product.id == matched_product_id).first()
    if not product:
        return result
    result["current_effective_vip_eur"] = product.effective_vip_eur()
    result["current_effective_vip_czk"] = product.effective_vip_czk()
    result["current_effective_d1"] = product.effective_trade_price()

    def delta_pct(new_val, old_val):
        if new_val is None or old_val is None or old_val == 0:
            return None
        return float((new_val - old_val) / old_val * 100)

    result["delta_vip_eur_pct"] = delta_pct(computed.get("vip_eur_imported"), result["current_effective_vip_eur"])
    result["delta_vip_czk_pct"] = delta_pct(computed.get("vip_czk_imported"), result["current_effective_vip_czk"])
    result["delta_d1_pct"] = delta_pct(computed.get("trade_price_imported"), result["current_effective_d1"])

    for name, pct in (("vip_eur", result["delta_vip_eur_pct"]), ("vip_czk", result["delta_vip_czk_pct"]), ("d1", result["delta_d1_pct"])):
        if pct is not None and abs(pct) > threshold_pct:
            result["review_flags"].append(f"large_price_change_{name}")
    if _decimal(row.get("unit_per_cc")) is None or _decimal(row.get("unit_per_cc")) <= 0:
        result["review_flags"].append("missing_unit_per_cc")
    if _decimal(row.get("sales_price")) is None:
        result["review_flags"].append("missing_sales_price")
    if product.vip_eur_override is not None or product.vip_czk_override is not None or product.trade_price_override is not None:
        result["review_flags"].append("override_conflict")
    return result


def apply_import_to_products(db: Session, product: Product, row: dict, now: datetime) -> None:
    """
    Aktualizuje produkt z importního řádku. Zapisuje POUZE *_imported, NIKDY nemění *_override.
    """
    product.description2 = _str(row.get("description2")) or product.description2
    product.ean_code = _str(row.get("ean_code")) or product.ean_code
    product.vbn_code = _str(row.get("vbn_code")) or product.vbn_code
    product.plant_passport_no = _str(row.get("plant_passport_no")) or product.plant_passport_no
    product.customer_line_info = _str(row.get("customer_line_info")) or product.customer_line_info
    product.image_reference = _str(row.get("image_reference")) or product.image_reference
    product.qty = _decimal(row.get("qty"))
    product.ordered_qty = _decimal(row.get("ordered_qty"))
    product.per_unit = _str(row.get("per_unit"))
    product.qty_per_shelf = _decimal(row.get("qty_per_shelf"))
    product.shelf_per_cc = _decimal(row.get("shelf_per_cc"))
    product.unit_per_cc = _decimal(row.get("unit_per_cc"))
    product.sales_price_imported = _decimal2(row.get("sales_price"))
    product.amount_imported = _decimal(row.get("amount"))
    product.purchase_price_imported = _decimal2(row.get("purchase_price_imported"))
    product.margin_7_imported = _decimal2(row.get("margin_7_imported"))
    product.vip_eur_imported = _decimal2(row.get("vip_eur_imported"))
    product.vip_czk_imported = _decimal2(row.get("vip_czk_imported"))
    product.trade_price_imported = _decimal2(row.get("trade_price_imported"))
    product.d4_price_imported = _decimal2(row.get("d4_price_imported"))
    product.last_imported_at = now
    product.updated_at = now


# Sloupce pouze na zobrazení (needitovatelné v tabulce)
ROW_DISPLAY_ONLY = [
    ("description", "Description"),
    ("description2", "Description 2"),
    ("pot_size", "Pot-Size"),
    ("qty", "Qty"),
    ("ordered_qty", "Ordered Qty"),
    ("per_unit", "Per Unit"),
    ("qty_per_shelf", "Qty per Shelf"),
    ("shelf_per_cc", "Shelf per CC"),
    ("unit_per_cc", "Unit per CC"),
    ("sales_price", "Sales Price"),
    ("amount", "Amount"),
]

# Pole editovatelná v „Řádky (po řádcích)“ – jen ceny a EAN
ROW_EDIT_FIELDS = [
    ("purchase_price_imported", "Cena + doprava"),
    ("margin_7_imported", "7% marže + doprava"),
    ("vip_eur_imported", "VIP Eur"),
    ("vip_czk_imported", "VIP CZK"),
    ("trade_price_imported", "D1 obchod"),
    ("d4_price_imported", "D4"),
    ("ean_code", "EAN Code"),
]

NUMERIC_ROW_KEYS = frozenset({
    "qty", "ordered_qty", "qty_per_shelf", "shelf_per_cc", "unit_per_cc",
    "sales_price", "amount", "purchase_price_imported", "margin_7_imported",
    "vip_eur_imported", "vip_czk_imported", "trade_price_imported", "d4_price_imported",
})


def update_import_row_from_form(db: Session, row: ImportRow, form_data: dict) -> Optional[str]:
    """
    Aktualizuje ImportRow a přiřazený produkt (pokud existuje) z dat formuláře.
    form_data: dict s klíči z ROW_EDIT_FIELDS (hodnoty z request.form).
    Vrátí chybovou zprávu nebo None při úspěchu.
    """
    now = datetime.now(timezone.utc)
    try:
        existing = json.loads(row.raw_data_json) if row.raw_data_json else {}
    except Exception:
        existing = {}
    row_data = dict(existing)
    for key, _label in ROW_EDIT_FIELDS:
        val = form_data.get(key)
        if val is not None and isinstance(val, str):
            val = val.strip() or None
        if key in NUMERIC_ROW_KEYS and val is not None and val != "":
            try:
                row_data[key] = str(Decimal(str(val).replace(",", ".")))
            except Exception:
                row_data[key] = val
        else:
            row_data[key] = val if (val is None or val == "") else str(val)

    product = None
    if row.matched_product_id:
        product = db.query(Product).filter(Product.id == row.matched_product_id).first()
        if not product:
            return "Produkt nenalezen"

    if product:
        desc = _str(row_data.get("description")) or product.description
        pot = _str(row_data.get("pot_size")) or product.pot_size
        product.description = desc or ""
        product.pot_size = pot
        product.product_key_normalized = product_key_normalized(desc, pot)
        product.description2 = _str(row_data.get("description2")) or product.description2
        product.ean_code = _str(row_data.get("ean_code"))
        product.vbn_code = _str(row_data.get("vbn_code"))
        product.plant_passport_no = _str(row_data.get("plant_passport_no"))
        product.customer_line_info = _str(row_data.get("customer_line_info"))
        product.image_reference = _str(row_data.get("image_reference"))
        product.qty = _decimal(row_data.get("qty"))
        product.ordered_qty = _decimal(row_data.get("ordered_qty"))
        product.per_unit = _str(row_data.get("per_unit"))
        product.qty_per_shelf = _decimal(row_data.get("qty_per_shelf"))
        product.shelf_per_cc = _decimal(row_data.get("shelf_per_cc"))
        product.unit_per_cc = _decimal(row_data.get("unit_per_cc"))
        product.sales_price_imported = _decimal2(row_data.get("sales_price"))
        product.amount_imported = _decimal(row_data.get("amount"))
        product.purchase_price_imported = _decimal2(row_data.get("purchase_price_imported"))
        product.margin_7_imported = _decimal2(row_data.get("margin_7_imported"))
        product.vip_eur_imported = _decimal2(row_data.get("vip_eur_imported"))
        product.vip_czk_imported = _decimal2(row_data.get("vip_czk_imported"))
        product.trade_price_imported = _decimal2(row_data.get("trade_price_imported"))
        product.d4_price_imported = _decimal2(row_data.get("d4_price_imported"))
        product.sales_price_override = None
        product.purchase_price_override = None
        product.margin_7_override = None
        product.vip_eur_override = None
        product.vip_czk_override = None
        product.trade_price_override = None
        product.d4_price_override = None
        product.last_imported_at = now
        product.updated_at = now

    row.raw_data_json = json.dumps(row_data, ensure_ascii=False, default=str)
    return None


def _update_product_from_row(product: Product, row: dict, now: datetime) -> None:
    """Aktualizuje existující produkt z importního řádku (row může obsahovat dopočítané ceny)."""
    product.description2 = _str(row.get("description2")) or product.description2
    product.ean_code = _str(row.get("ean_code")) or product.ean_code
    product.vbn_code = _str(row.get("vbn_code")) or product.vbn_code
    product.plant_passport_no = _str(row.get("plant_passport_no")) or product.plant_passport_no
    product.customer_line_info = _str(row.get("customer_line_info")) or product.customer_line_info
    product.image_reference = _str(row.get("image_reference")) or product.image_reference
    product.qty = _decimal(row.get("qty"))
    product.ordered_qty = _decimal(row.get("ordered_qty"))
    product.per_unit = _str(row.get("per_unit"))
    product.qty_per_shelf = _decimal(row.get("qty_per_shelf"))
    product.shelf_per_cc = _decimal(row.get("shelf_per_cc"))
    product.unit_per_cc = _decimal(row.get("unit_per_cc"))
    product.sales_price_imported = _decimal2(row.get("sales_price"))
    product.amount_imported = _decimal(row.get("amount"))
    product.purchase_price_imported = _decimal2(row.get("purchase_price_imported"))
    product.margin_7_imported = _decimal2(row.get("margin_7_imported"))
    product.vip_eur_imported = _decimal2(row.get("vip_eur_imported"))
    product.vip_czk_imported = _decimal2(row.get("vip_czk_imported"))
    product.trade_price_imported = _decimal2(row.get("trade_price_imported"))
    product.d4_price_imported = _decimal2(row.get("d4_price_imported"))
    product.last_imported_at = now
    product.updated_at = now


def _create_product_from_row(row: dict, now: datetime) -> Product:
    """Vytvoří nový produkt z importního řádku (row může obsahovat dopočítané ceny)."""
    description = _str(row.get("description")) or ""
    pot_size = _str(row.get("pot_size"))
    key = product_key_normalized(description, pot_size)
    product = Product(
        description=description,
        description2=_str(row.get("description2")),
        pot_size=pot_size,
        product_key_normalized=key,
        ean_code=_str(row.get("ean_code")),
        vbn_code=_str(row.get("vbn_code")),
        plant_passport_no=_str(row.get("plant_passport_no")),
        customer_line_info=_str(row.get("customer_line_info")),
        image_reference=_str(row.get("image_reference")),
        qty=_decimal(row.get("qty")),
        ordered_qty=_decimal(row.get("ordered_qty")),
        per_unit=_str(row.get("per_unit")),
        qty_per_shelf=_decimal(row.get("qty_per_shelf")),
        shelf_per_cc=_decimal(row.get("shelf_per_cc")),
        unit_per_cc=_decimal(row.get("unit_per_cc")),
        sales_price_imported=_decimal(row.get("sales_price")),
        amount_imported=_decimal(row.get("amount")),
        purchase_price_imported=_decimal(row.get("purchase_price_imported")),
        margin_7_imported=_decimal(row.get("margin_7_imported")),
        vip_eur_imported=_decimal(row.get("vip_eur_imported")),
        vip_czk_imported=_decimal(row.get("vip_czk_imported")),
        trade_price_imported=_decimal(row.get("trade_price_imported")),
        d4_price_imported=_decimal(row.get("d4_price_imported")),
        active=True,
        first_imported_at=now,
        last_imported_at=now,
        created_at=now,
        updated_at=now,
    )
    return product


def _add_import_row(
    db: Session,
    import_file_id: int,
    row_index: int,
    row: Optional[dict],
    matched_product_id: Optional[int],
    action_taken: str,
    message: Optional[str],
    *,
    source_description: Optional[str] = None,
    source_pot_size: Optional[str] = None,
    source_sales_price: Optional[Decimal] = None,
    source_qty: Optional[Decimal] = None,
    source_unit_per_cc: Optional[Decimal] = None,
    source_ean: Optional[str] = None,
    source_vbn: Optional[str] = None,
    computed_purchase_price: Optional[Decimal] = None,
    computed_margin_7_price: Optional[Decimal] = None,
    computed_vip_eur: Optional[Decimal] = None,
    computed_vip_czk: Optional[Decimal] = None,
    computed_d1: Optional[Decimal] = None,
    computed_d4: Optional[Decimal] = None,
    current_effective_vip_eur: Optional[Decimal] = None,
    current_effective_vip_czk: Optional[Decimal] = None,
    current_effective_d1: Optional[Decimal] = None,
    delta_vip_eur_pct: Optional[float] = None,
    delta_vip_czk_pct: Optional[float] = None,
    delta_d1_pct: Optional[float] = None,
    match_confidence: Optional[str] = None,
    review_flags_json: Optional[str] = None,
) -> None:
    raw_json = json.dumps(row or {}, ensure_ascii=False, default=str)
    ir = ImportRow(
        import_file_id=import_file_id,
        row_index=row_index,
        raw_data_json=raw_json,
        matched_product_id=matched_product_id,
        action_taken=action_taken,
        message=message,
        source_description=source_description,
        source_pot_size=source_pot_size,
        source_sales_price=source_sales_price,
        source_qty=source_qty,
        source_unit_per_cc=source_unit_per_cc,
        source_ean=source_ean,
        source_vbn=source_vbn,
        computed_purchase_price=computed_purchase_price,
        computed_margin_7_price=computed_margin_7_price,
        computed_vip_eur=computed_vip_eur,
        computed_vip_czk=computed_vip_czk,
        computed_d1=computed_d1,
        computed_d4=computed_d4,
        current_effective_vip_eur=current_effective_vip_eur,
        current_effective_vip_czk=current_effective_vip_czk,
        current_effective_d1=current_effective_d1,
        delta_vip_eur_pct=delta_vip_eur_pct,
        delta_vip_czk_pct=delta_vip_czk_pct,
        delta_d1_pct=delta_d1_pct,
        match_confidence=match_confidence,
        review_flags_json=review_flags_json,
    )
    db.add(ir)


def run_import_from_uploaded_files(
    files: list,
    db: Session,
    created_by_user_id: Optional[int] = None,
    shipping_eur: Optional[Decimal] = None,
    exchange_rate: Optional[Decimal] = None,
) -> ImportBatch:
    """
    Z nahraných souborů (Flask request.files nebo [(filename, bytes), ...]).
    Uloží do temp složky, spustí import, smaže temp.
    """
    if not files:
        raise ValueError("Žádné soubory k importu")
    with tempfile.TemporaryDirectory(prefix="blooms_import_") as tmpdir:
        tmp = Path(tmpdir)
        for f in files:
            if hasattr(f, "filename") and hasattr(f, "save"):
                # Flask FileStorage
                fn = getattr(f, "filename", "") or "file.xls"
                if not (fn.lower().endswith(".xls") or fn.lower().endswith(".xlsx")):
                    continue
                f.save(str(tmp / fn))
            elif isinstance(f, (list, tuple)) and len(f) >= 2:
                fn, content = f[0], f[1]
                low = str(fn).lower()
                if not (low.endswith(".xls") or low.endswith(".xlsx")):
                    continue
                (tmp / fn).write_bytes(content)
        return run_import_from_folder(
            str(tmp), db, created_by_user_id=created_by_user_id,
            shipping_eur=shipping_eur, exchange_rate=exchange_rate,
        )


def run_import_from_folder(
    folder_path: str,
    db: Session,
    created_by_user_id: Optional[int] = None,
    shipping_eur: Optional[Decimal] = None,
    exchange_rate: Optional[Decimal] = None,
) -> ImportBatch:
    """
    Načte všechny .xls soubory ze složky, zpracuje je a uloží do DB.
    Vrátí ImportBatch. Chyby po řádcích se logují a ukládají do ImportRow.
    """
    folder = Path(folder_path)
    if not folder.is_dir():
        raise ValueError(f"Složka neexistuje: {folder_path}")

    now = datetime.now(timezone.utc)
    batch = ImportBatch(
        source_folder=str(folder.resolve()),
        shipping_eur=shipping_eur,
        exchange_rate=exchange_rate,
        imported_at=now,
        total_files=0,
        total_rows=0,
        new_products=0,
        existing_products=0,
        error_rows=0,
        status=ImportStatus.running.value,
        created_by_user_id=created_by_user_id,
    )
    db.add(batch)
    db.flush()

    xls_files = sorted(
        f for f in folder.iterdir()
        if f.is_file() and f.suffix.lower() in (".xls", ".xlsx")
    )
    batch.total_files = len(xls_files)
    summary = ImportSummary(
        source_folder=str(folder.resolve()),
        total_files=len(xls_files),
        total_rows=0,
        new_products=0,
        existing_products=0,
        error_rows=0,
    )

    for file_path in xls_files:
        try:
            ifile, file_summary = _process_one_file(db, batch, file_path, now)
            summary.files.append(file_summary)
            batch.total_rows += ifile.row_count
            batch.new_products += file_summary.new_products
            batch.existing_products += file_summary.existing_products
            batch.error_rows += file_summary.error_rows
        except Exception as e:
            logger.exception("Chyba při importu souboru %s", file_path)
            batch.error_rows += 1
            summary.files.append(FileImportSummary(
                filename=file_path.name,
                order_number=extract_order_number(file_path.name),
                row_count=0,
                new_products=0,
                existing_products=0,
                skipped_rows=0,
                error_rows=1,
                warnings=[],
                row_errors=[(0, str(e))],
            ))
            ifile = ImportFile(
                import_batch_id=batch.id,
                filename=file_path.name,
                file_path=str(file_path.resolve()),
                order_number=extract_order_number(file_path.name),
                imported_at=now,
                row_count=0,
                new_products=0,
                existing_products=0,
                error_rows=1,
                status=ImportStatus.failed.value,
                report_text=f"Výjimka: {e}",
            )
            db.add(ifile)

    summary.total_rows = batch.total_rows
    summary.new_products = batch.new_products
    summary.existing_products = batch.existing_products
    summary.error_rows = batch.error_rows
    logger.info("Import summary: %s", summary.to_text())

    batch.status = ImportStatus.completed.value
    db.commit()
    db.refresh(batch)
    return batch


def _process_one_file(
    db: Session,
    batch: ImportBatch,
    file_path: Path,
    now: datetime,
) -> tuple[ImportFile, FileImportSummary]:
    """Zpracuje jeden .xls soubor. Vrátí (ImportFile, FileImportSummary)."""
    parsed = parse_xls_file(file_path)
    order_number = extract_order_number(file_path.name)
    shipping_eur = getattr(batch, "shipping_eur", None)
    exchange_rate = getattr(batch, "exchange_rate", None)

    ifile = ImportFile(
        import_batch_id=batch.id,
        filename=file_path.name,
        file_path=str(file_path.resolve()),
        order_number=order_number,
        imported_at=now,
        row_count=0,
        new_products=0,
        existing_products=0,
        error_rows=0,
        status=ImportStatus.completed.value,
    )
    db.add(ifile)
    db.flush()

    file_summary = FileImportSummary(
        filename=file_path.name,
        order_number=order_number,
        row_count=0,
        new_products=0,
        existing_products=0,
        skipped_rows=0,
        error_rows=0,
        warnings=list(parsed.warnings),
        row_errors=[(e.row_index, e.message) for e in parsed.row_errors],
    )

    report_lines = []
    if parsed.detected_headers:
        report_lines.append("Mapování sloupců (název v souboru -> použitý klíč):")
        for key, orig in sorted(parsed.detected_headers.items()):
            report_lines.append(f"  {key}: \"{orig}\"")
        report_lines.append("")
    for w in parsed.warnings:
        report_lines.append(f"Varování: {w}")

    # Chyby z parseru (řádek se nepodařilo přečíst)
    for err in parsed.row_errors:
        _add_import_row(db, ifile.id, err.row_index, None, None, RowAction.error.value, err.message)
        report_lines.append(f"Řádek {err.row_index + 1}: {err.message}")
        file_summary.error_rows += 1

    new_count = 0
    existing_count = 0
    skipped_count = 0
    error_count = file_summary.error_rows

    for row_index, row in enumerate(parsed.rows):
        description = _str(row.get("description"))
        if not description:
            skipped_count += 1
            msg = "Chybí Description, řádek přeskočen (včetně souhrnného řádku z order confirmation)."
            report_lines.append(f"Řádek {row_index + 1}: {msg}")
            _add_import_row(db, ifile.id, row_index, row, None, RowAction.skipped.value, msg)
            continue

        computed = compute_prices_from_formulas(row, shipping_eur, exchange_rate)
        row_merged = dict(row)
        for k, v in computed.items():
            if v is not None:
                row_merged[k] = float(v)
        pot_size = _str(row_merged.get("pot_size"))

        existing, match_confidence = match_row_to_product(db, row_merged)
        review = {}
        if existing:
            review = detect_price_changes(db, existing.id, computed, row_merged, threshold_pct=5.0)

        try:
            if existing:
                apply_import_to_products(db, existing, row_merged, now)
                existing_count += 1
                _add_import_row(
                    db, ifile.id, row_index, row_merged, existing.id, RowAction.matched.value, None,
                    source_description=description,
                    source_pot_size=pot_size,
                    source_sales_price=_decimal(row_merged.get("sales_price")),
                    source_qty=_decimal(row_merged.get("qty")),
                    source_unit_per_cc=_decimal(row_merged.get("unit_per_cc")),
                    source_ean=_str(row_merged.get("ean_code")),
                    source_vbn=_str(row_merged.get("vbn_code")),
                    computed_purchase_price=computed.get("purchase_price_imported"),
                    computed_margin_7_price=computed.get("margin_7_imported"),
                    computed_vip_eur=computed.get("vip_eur_imported"),
                    computed_vip_czk=computed.get("vip_czk_imported"),
                    computed_d1=computed.get("trade_price_imported"),
                    computed_d4=_decimal(row_merged.get("d4_price_imported")),
                    current_effective_vip_eur=review.get("current_effective_vip_eur"),
                    current_effective_vip_czk=review.get("current_effective_vip_czk"),
                    current_effective_d1=review.get("current_effective_d1"),
                    delta_vip_eur_pct=review.get("delta_vip_eur_pct"),
                    delta_vip_czk_pct=review.get("delta_vip_czk_pct"),
                    delta_d1_pct=review.get("delta_d1_pct"),
                    match_confidence=match_confidence.value if match_confidence else None,
                    review_flags_json=json.dumps(review.get("review_flags", []), ensure_ascii=False) if review.get("review_flags") else None,
                )
            else:
                product = _create_product_from_row(row_merged, now)
                db.add(product)
                db.flush()
                new_count += 1
                _add_import_row(
                    db, ifile.id, row_index, row_merged, product.id, RowAction.new.value, None,
                    source_description=description,
                    source_pot_size=pot_size,
                    source_sales_price=_decimal(row_merged.get("sales_price")),
                    source_qty=_decimal(row_merged.get("qty")),
                    source_unit_per_cc=_decimal(row_merged.get("unit_per_cc")),
                    source_ean=_str(row_merged.get("ean_code")),
                    source_vbn=_str(row_merged.get("vbn_code")),
                    computed_purchase_price=computed.get("purchase_price_imported"),
                    computed_margin_7_price=computed.get("margin_7_imported"),
                    computed_vip_eur=computed.get("vip_eur_imported"),
                    computed_vip_czk=computed.get("vip_czk_imported"),
                    computed_d1=computed.get("trade_price_imported"),
                    computed_d4=_decimal(row_merged.get("d4_price_imported")),
                    match_confidence=match_confidence.value if match_confidence else None,
                )
        except Exception as e:
            error_count += 1
            msg = str(e)
            report_lines.append(f"Řádek {row_index + 1}: {msg}")
            logger.warning("Import řádek %s soubor %s: %s", row_index + 1, file_path.name, msg)
            _add_import_row(db, ifile.id, row_index, row, None, RowAction.error.value, msg)

    ifile.row_count = len(parsed.rows) + len(parsed.row_errors)
    ifile.new_products = new_count
    ifile.existing_products = existing_count
    ifile.error_rows = error_count
    file_summary.row_count = ifile.row_count
    file_summary.new_products = new_count
    file_summary.existing_products = existing_count
    file_summary.skipped_rows = skipped_count
    file_summary.error_rows = error_count

    # Shrnutí do reportu
    report_lines.append("")
    report_lines.append(f"Shrnutí: {len(parsed.rows)} řádků, {new_count} nových, {existing_count} existujících, {skipped_count} přeskočeno, {error_count} chyb.")
    ifile.report_text = "\n".join(report_lines) if report_lines else None

    return ifile, file_summary


# Mapování: klíč v importním řádku -> (název pro UI, product.*_imported, *override, effective getter)
_PRICE_FIELD_MAP = [
    ("sales_price", "Sales Price", "sales_price_imported", "sales_price_override", "effective_sales_price"),
    ("purchase_price_imported", "Cena+doprava", "purchase_price_imported", "purchase_price_override", "effective_purchase_price"),
    ("margin_7_imported", "7% marže+doprava", "margin_7_imported", "margin_7_override", "effective_margin_7"),
    ("vip_eur_imported", "VIP Eur", "vip_eur_imported", "vip_eur_override", "effective_vip_eur"),
    ("vip_czk_imported", "VIP CZK", "vip_czk_imported", "vip_czk_override", "effective_vip_czk"),
    ("trade_price_imported", "D1 obchod", "trade_price_imported", "trade_price_override", "effective_trade_price"),
    ("d4_price_imported", "D4", "d4_price_imported", "d4_price_override", "effective_d4_price"),
]

# Pro šablony (kompatibilita)
PRICE_FIELD_LABELS = [(row_key, label) for row_key, label, *_ in _PRICE_FIELD_MAP]


def _prices_equal(a: Optional[Decimal], b: Optional[Decimal]) -> bool:
    """Porovnání cen pro kompatibilitu (None == None, čísla na 4 des. místa)."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    q = Decimal("0.0001")
    return a.quantize(q) == b.quantize(q)


@dataclass
class PriceConflict:
    """Jeden cenový rozdíl: import vs DB (effective)."""
    import_row_id: int
    product_id: int
    product_description: str
    pot_size: Optional[str]
    row_index: int
    field_key: str
    field_label: str
    value_import: Optional[Decimal]
    value_db: Optional[Decimal]


def get_price_conflicts_for_file(db: Session, import_file: ImportFile) -> list[PriceConflict]:
    """
    Pro řádky se action_taken=matched porovná ceny z importu s effective cenou v DB.
    Vrátí seznam konfliktů (kde se hodnoty liší).
    """
    conflicts: list[PriceConflict] = []
    for row in import_file.rows:
        if row.action_taken != RowAction.matched.value or not row.matched_product_id:
            continue
        product = db.query(Product).filter(Product.id == row.matched_product_id).first()
        if not product:
            continue
        try:
            data = json.loads(row.raw_data_json) if row.raw_data_json else {}
        except Exception:
            data = {}
        for row_key, field_label, _imported_attr, _override_attr, effective_attr in _PRICE_FIELD_MAP:
            val_import = _decimal(data.get(row_key))
            getter = getattr(product, effective_attr)
            val_db = getter() if callable(getter) else getter
            if not _prices_equal(val_import, val_db):
                conflicts.append(PriceConflict(
                    import_row_id=row.id,
                    product_id=product.id,
                    product_description=product.description or "",
                    pot_size=product.pot_size,
                    row_index=row.row_index,
                    field_key=row_key,
                    field_label=field_label,
                    value_import=val_import,
                    value_db=val_db,
                ))
    return conflicts


@dataclass
class PriceComparison:
    """Jedno pole cenového porovnání: import vs DB (pro kompletní kontrolu)."""
    field_key: str
    field_label: str
    value_import: Optional[Decimal]
    value_db: Optional[Decimal]
    is_changed: bool


def get_price_comparisons_for_file(db: Session, import_file: ImportFile) -> dict[int, list[PriceComparison]]:
    """
    Pro každý matched řádek vrátí kompletní porovnání všech cen (import vs DB).
    Klíč = import_row.id, hodnota = seznam PriceComparison (všechna pole z _PRICE_FIELD_MAP).
    Použito pro zvýraznění změněných cen v kontrole importu.
    """
    result: dict[int, list[PriceComparison]] = {}
    for row in import_file.rows:
        if row.action_taken != RowAction.matched.value or not row.matched_product_id:
            continue
        product = db.query(Product).filter(Product.id == row.matched_product_id).first()
        if not product:
            continue
        try:
            data = json.loads(row.raw_data_json) if row.raw_data_json else {}
        except Exception:
            data = {}
        comparisons: list[PriceComparison] = []
        for row_key, field_label, _imported_attr, _override_attr, effective_attr in _PRICE_FIELD_MAP:
            val_import = _decimal(data.get(row_key))
            getter = getattr(product, effective_attr)
            val_db = getter() if callable(getter) else getter
            is_changed = not _prices_equal(val_import, val_db)
            comparisons.append(PriceComparison(
                field_key=row_key,
                field_label=field_label,
                value_import=val_import,
                value_db=val_db,
                is_changed=is_changed,
            ))
        result[row.id] = comparisons
    return result


def apply_import_price(
    db: Session,
    import_row_id: int,
    field_key: str,
    value_override: Optional[Decimal] = None,
) -> Optional[str]:
    """
    Uloží cenu do produktu: nastaví _imported (a zruší override).
    value_override: pokud je zadané, použije se místo hodnoty z importního řádku (umožňuje editaci před uložením).
    Vrátí chybovou zprávu nebo None při úspěchu.
    """
    row = db.query(ImportRow).filter(ImportRow.id == import_row_id).first()
    if not row or not row.matched_product_id:
        return "Řádek nebo produkt nenalezen"
    product = db.query(Product).filter(Product.id == row.matched_product_id).first()
    if not product:
        return "Produkt nenalezen"
    try:
        data = json.loads(row.raw_data_json) if row.raw_data_json else {}
    except Exception:
        return "Neplatná data řádku"
    for rk, _label, imported_attr, override_attr, _eff in _PRICE_FIELD_MAP:
        if rk != field_key:
            continue
        value = value_override if value_override is not None else _decimal(data.get(rk))
        setattr(product, imported_attr, value)
        setattr(product, override_attr, None)
        return None
    return "Neznámé pole"
