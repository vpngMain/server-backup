# Blooms – Import Workflow Improvements

Analysis and proposal for a clearer, safer, and more maintainable import system **without redesigning the whole application**.

---

## 1. Suggested data model improvements

### 1.1 Keep existing, add new columns

**Do not remove** `raw_data_json`, `matched_product_id`, `action_taken`, `message` – they keep current behaviour and UI working. Add new columns in a **single additive migration** so existing migrations stay valid.

### 1.2 ImportRow – new columns (all nullable for backward compatibility)

| Column | Type | Purpose |
|--------|------|---------|
| **Source (from Excel)** | | |
| `source_description` | String(500) | Raw description from file |
| `source_pot_size` | String(100) | Raw pot size |
| `source_sales_price` | Numeric(18,4) | Sales price from file |
| `source_qty` | Numeric(18,4) | Qty from file |
| `source_unit_per_cc` | Numeric(18,4) | Unit per CC from file |
| `source_ean` | String(50) | EAN from file |
| `source_vbn` | String(50) | VBN from file |
| **Computed (business formulas)** | | |
| `computed_purchase_price` | Numeric(18,4) | Cena + doprava |
| `computed_margin_7_price` | Numeric(18,4) | 7% marže + doprava |
| `computed_vip_eur` | Numeric(18,4) | VIP Eur |
| `computed_vip_czk` | Numeric(18,4) | VIP CZK |
| `computed_d1` | Numeric(18,4) | D1 obchod |
| `computed_d4` | Numeric(18,4) | D4 (if present in file) |
| **Current effective (from product at match time)** | | |
| `current_effective_vip_eur` | Numeric(18,4) | Product effective at review |
| `current_effective_vip_czk` | Numeric(18,4) | |
| `current_effective_d1` | Numeric(18,4) | |
| **Review / flags** | | |
| `delta_vip_eur_pct` | Numeric(8,2) | % change VIP Eur (computed vs current) |
| `delta_vip_czk_pct` | Numeric(8,2) | |
| `delta_d1_pct` | Numeric(8,2) | |
| `match_confidence` | String(20) | `exact_match` \| `probable_match` \| `no_match` |
| `review_flags_json` | Text | JSON: e.g. `{"missing_unit_per_cc": true, "override_conflict": true}` |

**Why this helps**

- **Source_***: Clear what came from the file; no need to parse `raw_data_json` for display.
- **Computed_***: Prices from business formulas in one place; same formulas used in one function.
- **Current_effective_***: Snapshot at match time so review UI can show “current vs new” even if product is edited later.
- **Delta_*** and **review_flags_json**: Review step can filter “price change > X%”, “missing unit_per_cc”, “override conflict” without recomputing.

### 1.3 Product model

No change. Rule: **import must never overwrite `*_override`**. Only `*_imported` fields are updated by import.

---

## 2. Matching logic

### 2.1 Priority

1. **EAN** – if row has EAN and a product with that `ean_code` exists → `exact_match`.
2. **VBN** – else if row has VBN and a product with that `vbn_code` exists → `exact_match`.
3. **Normalized product key** – `product_key_normalized == normalize(description) + "::" + normalize(pot_size)` → `probable_match`.
4. Else → `no_match` (new product or skip).

### 2.2 Match confidence

- `exact_match` – matched by EAN or VBN.
- `probable_match` – matched by description + pot_size only.
- `no_match` – no product found (row can still create a new product or be skipped).

### 2.3 Behaviour

- One product per identifier: EAN and VBN should be unique in DB (or take first match and flag duplicates in review).
- If both EAN and product_key match the same product, prefer EAN (exact_match).

---

## 3. Service layer refactor

### 3.1 Responsibilities (single place each)

| Function | Responsibility | Input / Output |
|----------|----------------|----------------|
| `parse_confirmation_file(path) -> ParsedXlsResult` | Parse Excel only; no DB, no prices | Path → rows as dicts, errors, warnings |
| `match_import_rows_to_products(db, rows, batch_context) -> list[MatchedRow]` | Resolve each row to product (or none); set match_confidence | Rows + batch → matched rows with product_id or None |
| `calculate_business_prices(rows, shipping_eur, exchange_rate) -> list[RowWithPrices]` | Apply formulas; fill computed_* | Rows + batch params → rows with computed_* |
| `detect_price_changes(db, rows_with_prices) -> list[RowWithReview]` | Snapshot product effective prices, deltas, flags | Rows + DB → rows with current_*, delta_*, review_flags |
| `apply_import_to_products(db, rows, *, only_imported=True)` | Write to DB: create/update products; **only *_imported**, never *_override | Rows + DB |

### 3.2 Batch context

Pass once per file/batch:

```python
@dataclass
class ImportBatchContext:
    shipping_eur: Optional[Decimal]
    exchange_rate: Optional[Decimal]
```

### 3.3 Orchestrator (keep thin)

High-level flow in one place, e.g. `run_import_from_folder` or `process_one_file`:

1. Parse file → `parse_confirmation_file(path)`  
2. For each row: match → `match_import_rows_to_products(db, parsed.rows, context)`  
3. Compute prices → `calculate_business_prices(matched_rows, context)`  
4. Detect changes → `detect_price_changes(db, rows_with_prices)`  
5. Persist: create `ImportBatch`, `ImportFile`, `ImportRow` (with new columns), then call `apply_import_to_products(db, rows)` so products get only `*_imported` updates.

Flask routes only: receive upload, call orchestrator, redirect to review (e.g. first file’s file_detail).

---

## 4. Example Python code (key functions)

### 4.1 Match confidence enum

```python
# app/models/import_batch.py or app/services/import_constants.py
class MatchConfidence(str, enum.Enum):
    exact_match = "exact_match"    # EAN or VBN
    probable_match = "probable_match"  # product_key only
    no_match = "no_match"
```

### 4.2 Matching (new function)

```python
def match_row_to_product(db: Session, row: dict) -> tuple[Optional[Product], MatchConfidence]:
    """
    Resolve one confirmation row to a product.
    Priority: EAN → VBN → product_key_normalized.
    Returns (product or None, confidence).
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
```

### 4.3 Calculate business prices (extract from current logic)

```python
def calculate_business_prices(
    row: dict,
    shipping_eur: Optional[Decimal],
    exchange_rate: Optional[Decimal],
) -> dict[str, Optional[Decimal]]:
    """
    Pure function: row + batch params → computed prices.
    No DB. Used for computed_* on ImportRow and for review.
    """
    sales = _decimal(row.get("sales_price"))
    unit_cc = _decimal(row.get("unit_per_cc"))
    shipping = shipping_eur or Decimal(0)
    if unit_cc is None or unit_cc <= 0 or sales is None:
        return {
            "computed_purchase_price": None,
            "computed_margin_7_price": None,
            "computed_vip_eur": None,
            "computed_vip_czk": None,
            "computed_d1": None,
        }
    doprava_per_unit = shipping / unit_cc
    cena_plus_doprava = doprava_per_unit + sales
    out = {
        "computed_purchase_price": cena_plus_doprava,
        "computed_margin_7_price": (sales * Decimal("1.07")) + doprava_per_unit,
        "computed_vip_eur": cena_plus_doprava + (Decimal(100) / unit_cc),
        "computed_vip_czk": None,
        "computed_d1": None,
    }
    if exchange_rate and exchange_rate > 0:
        out["computed_vip_czk"] = (out["computed_vip_eur"] * exchange_rate).quantize(Decimal("0.01"))
        out["computed_d1"] = (exchange_rate * (sales + doprava_per_unit * Decimal("1.12") * 2)).quantize(Decimal("0.01"))
    return out
```

### 4.4 Detect price changes and review flags

```python
def detect_price_changes(
    db: Session,
    row: dict,
    matched_product_id: Optional[int],
    computed: dict[str, Optional[Decimal]],
    threshold_pct: float = 5.0,
) -> dict:
    """
    Returns dict with current_effective_*, delta_*_pct, and review_flags.
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

    result["delta_vip_eur_pct"] = delta_pct(computed.get("computed_vip_eur"), result["current_effective_vip_eur"])
    result["delta_vip_czk_pct"] = delta_pct(computed.get("computed_vip_czk"), result["current_effective_vip_czk"])
    result["delta_d1_pct"] = delta_pct(computed.get("computed_d1"), result["current_effective_d1"])

    if result["delta_vip_eur_pct"] is not None and abs(result["delta_vip_eur_pct"]) > threshold_pct:
        result["review_flags"].append("large_price_change_vip_eur")
    if result["delta_vip_czk_pct"] is not None and abs(result["delta_vip_czk_pct"]) > threshold_pct:
        result["review_flags"].append("large_price_change_vip_czk")
    if result["delta_d1_pct"] is not None and abs(result["delta_d1_pct"]) > threshold_pct:
        result["review_flags"].append("large_price_change_d1")

    if _decimal(row.get("unit_per_cc")) is None or _decimal(row.get("unit_per_cc")) <= 0:
        result["review_flags"].append("missing_unit_per_cc")
    if _decimal(row.get("sales_price")) is None:
        result["review_flags"].append("missing_sales_price")

    # Override conflict: product has override set → effective != imported
    if product.vip_eur_override is not None or product.vip_czk_override is not None or product.trade_price_override is not None:
        result["review_flags"].append("override_conflict")

    return result
```

### 4.5 Apply import to products (never touch override)

```python
def apply_import_to_products(
    db: Session,
    row: dict,
    product: Product,
    now: datetime,
    *,
    only_imported: bool = True,
) -> None:
    """
    Update product from import row. Only *_imported fields are written.
    *_override is never modified by import.
    """
    assert only_imported  # enforce rule
    product.description2 = _str(row.get("description2")) or product.description2
    product.ean_code = _str(row.get("ean_code")) or product.ean_code
    product.vbn_code = _str(row.get("vbn_code")) or product.vbn_code
    # ... other non-price fields ...
    product.unit_per_cc = _decimal(row.get("unit_per_cc"))
    product.sales_price_imported = _decimal(row.get("sales_price"))
    product.purchase_price_imported = _decimal(row.get("purchase_price_imported"))
    product.margin_7_imported = _decimal(row.get("margin_7_imported"))
    product.vip_eur_imported = _decimal(row.get("vip_eur_imported"))
    product.vip_czk_imported = _decimal(row.get("vip_czk_imported"))
    product.trade_price_imported = _decimal(row.get("trade_price_imported"))
    product.d4_price_imported = _decimal(row.get("d4_price_imported"))
    # Do NOT set product.*_override
    product.last_imported_at = now
    product.updated_at = now
```

---

## 5. Review logic (UI filters)

Use `review_flags_json` (or individual boolean columns if you prefer) to drive the UI:

- **Price change > X%** – e.g. `large_price_change_vip_eur`, `large_price_change_vip_czk`, `large_price_change_d1` (X configurable, e.g. 5%).
- **Missing unit_per_cc** – `missing_unit_per_cc`.
- **Missing sales price** – `missing_sales_price`.
- **Override conflict** – `override_conflict` (product has at least one *_override set so effective price won’t change after import).

Filtering in the file_detail view: e.g. “Show only: [ ] Override conflict [ ] Large price change [ ] Missing data” and filter the list of `ImportRow` by these flags.

---

## 6. Migration strategy

### 6.1 Single additive migration

- Add all new columns to `import_rows` as **nullable**, no default required.
- Do **not** drop `raw_data_json` or change `action_taken`/`matched_product_id` in this step.

Example (Alembic):

```python
def upgrade():
    op.add_column("import_rows", sa.Column("source_description", sa.String(500), nullable=True))
    op.add_column("import_rows", sa.Column("source_pot_size", sa.String(100), nullable=True))
    op.add_column("import_rows", sa.Column("source_sales_price", sa.Numeric(18, 4), nullable=True))
    op.add_column("import_rows", sa.Column("source_qty", sa.Numeric(18, 4), nullable=True))
    op.add_column("import_rows", sa.Column("source_unit_per_cc", sa.Numeric(18, 4), nullable=True))
    op.add_column("import_rows", sa.Column("source_ean", sa.String(50), nullable=True))
    op.add_column("import_rows", sa.Column("source_vbn", sa.String(50), nullable=True))
    op.add_column("import_rows", sa.Column("computed_purchase_price", sa.Numeric(18, 4), nullable=True))
    op.add_column("import_rows", sa.Column("computed_margin_7_price", sa.Numeric(18, 4), nullable=True))
    op.add_column("import_rows", sa.Column("computed_vip_eur", sa.Numeric(18, 4), nullable=True))
    op.add_column("import_rows", sa.Column("computed_vip_czk", sa.Numeric(18, 4), nullable=True))
    op.add_column("import_rows", sa.Column("computed_d1", sa.Numeric(18, 4), nullable=True))
    op.add_column("import_rows", sa.Column("computed_d4", sa.Numeric(18, 4), nullable=True))
    op.add_column("import_rows", sa.Column("current_effective_vip_eur", sa.Numeric(18, 4), nullable=True))
    op.add_column("import_rows", sa.Column("current_effective_vip_czk", sa.Numeric(18, 4), nullable=True))
    op.add_column("import_rows", sa.Column("current_effective_d1", sa.Numeric(18, 4), nullable=True))
    op.add_column("import_rows", sa.Column("delta_vip_eur_pct", sa.Numeric(8, 2), nullable=True))
    op.add_column("import_rows", sa.Column("delta_vip_czk_pct", sa.Numeric(8, 2), nullable=True))
    op.add_column("import_rows", sa.Column("delta_d1_pct", sa.Numeric(8, 2), nullable=True))
    op.add_column("import_rows", sa.Column("match_confidence", sa.String(20), nullable=True))
    op.add_column("import_rows", sa.Column("review_flags_json", sa.Text(), nullable=True))
```

### 6.2 Backfill (optional)

- Existing rows keep `raw_data_json` and old behaviour; new columns stay NULL.
- New imports fill source_*, computed_*, current_*, delta_*, match_confidence, review_flags.
- Optionally: one-off script to backfill new columns from `raw_data_json` for recent batches (and recompute formulas) if you need historical review.

### 6.3 No breaking changes

- Routes and templates can keep using `raw_data_json` and existing fields until you switch UI to the new columns.
- Then gradually: show source_* and computed_* in review, add filters by review_flags, and use match_confidence in the table.

---

## 7. Why this design is better

| Aspect | Before | After |
|--------|--------|--------|
| **Responsibilities** | Parse + match + calculate + apply in one big step | Parse → match → calculate → detect → apply in clear steps |
| **Override safety** | Easy to overwrite by mistake in ad‑hoc edits | `apply_import_to_products` only writes *_imported; override never touched |
| **Review** | Infer from raw_data_json and live product | Stored current_*, computed_*, delta_*, review_flags → filter and show without recomputing |
| **Matching** | Only product_key | EAN → VBN → product_key; match_confidence for trust |
| **Maintainability** | One large function | Small, testable functions; Flask routes stay thin |
| **Compatibility** | — | Additive migration; existing data and UI keep working while you adopt new columns and logic |

---

## 8. Suggested implementation order

1. Add migration for new `ImportRow` columns (all nullable).
2. Introduce `MatchConfidence` and `match_row_to_product()`; in orchestrator call it and set `match_confidence` and `matched_product_id`; keep creating/updating products as today.
3. Extract `calculate_business_prices()` and fill `computed_*` when creating `ImportRow`.
4. Add `detect_price_changes()` and fill `current_effective_*`, `delta_*`, `review_flags_json`.
5. Refactor apply step into `apply_import_to_products()` that only updates `*_imported` (and fix any existing code that cleared overrides).
6. In file_detail (or new review view), add filters by review flags and show match_confidence and deltas.
7. Optionally backfill recent batches for the new columns.

This keeps the existing architecture, makes the workflow clearer and safer, and keeps the door open for a future “review then apply” UI (e.g. apply only selected rows or only after explicit confirm).
