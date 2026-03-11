"""Jednotné vzorce cen pro import a produkt.
Interně počítáme a ukládáme na 4 desetinná místa, v UI se může zobrazovat 2.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

PRICE_QUANTIZE = Decimal("0.0001")


def _q(d: Decimal) -> Decimal:
    return d.quantize(PRICE_QUANTIZE)


def _decimal(val) -> Optional[Decimal]:
    if val is None:
        return None
    try:
        return Decimal(str(val))
    except Exception:
        return None


# --- Vzorce (vše na jednotku, ceny v EUR kromě D1 a VIP CZK) ---
#
# • Cena + doprava (Purchase) = sales_price + (doprava_eur / unit_per_cc)
# • 7% marže + doprava = (sales_price × 1.07) + (doprava_eur / unit_per_cc)
# • VIP Eur = (cena + doprava) + (100 / unit_per_cc)
# • VIP CZK = VIP Eur × eurKurz
# • D1 (cena obchod, CZK) = (cena + doprava) × eurKurz × 1.12 × 2
#
# D4 = průměr mezi VIP CZK a Cena obchod (D1) – obojí v CZK.


def doprava_per_unit_eur(
    shipping_eur: Optional[Decimal],
    unit_per_cc: Optional[Decimal],
) -> Decimal:
    """Doprava na jednotku v EUR. Při chybějícím unit_cc vrací 0.
    Nezaokrouhluje se zde, aby nevznikala odchylka v navazujících vzorcích.
    """
    if not unit_per_cc or unit_per_cc <= 0:
        return Decimal(0)
    shipping = shipping_eur if shipping_eur is not None else Decimal(0)
    return shipping / unit_per_cc


def compute_purchase_price(
    sales_price: Optional[Decimal],
    doprava_per_unit: Decimal,
) -> Optional[Decimal]:
    """Cena + doprava (Purchase) = sales_price + doprava_per_unit (EUR)."""
    if sales_price is None:
        return None
    return _q(sales_price + doprava_per_unit)


def compute_margin_7(
    sales_price: Optional[Decimal],
    doprava_per_unit: Decimal,
) -> Optional[Decimal]:
    """7% marže + doprava = (doprava/unit_cc) + (sales × 1.07)."""
    if sales_price is None:
        return None
    return _q(doprava_per_unit + (sales_price * Decimal("1.07")))


def compute_vip_eur(
    purchase_price: Optional[Decimal],
    unit_per_cc: Optional[Decimal],
) -> Optional[Decimal]:
    """VIP Eur = (cena + doprava) + (100 / unit_per_cc)."""
    if purchase_price is None or not unit_per_cc or unit_per_cc <= 0:
        return None
    return _q(purchase_price + (Decimal(100) / unit_per_cc))


def compute_vip_czk(vip_eur: Optional[Decimal], exchange_rate: Optional[Decimal]) -> Optional[Decimal]:
    """VIP CZK = VIP Eur × eurKurz."""
    if vip_eur is None or not exchange_rate or exchange_rate <= 0:
        return None
    return _q(vip_eur * exchange_rate)


def compute_trade_price_d1(
    purchase_price: Optional[Decimal],
    exchange_rate: Optional[Decimal],
) -> Optional[Decimal]:
    """D1 (cena obchod, CZK) = (cena + doprava) × kurz × 1.12 × 2."""
    if purchase_price is None or not exchange_rate or exchange_rate <= 0:
        return None
    return _q(purchase_price * exchange_rate * Decimal("1.12") * 2)


def compute_d4_price(
    vip_czk: Optional[Decimal],
    trade_price: Optional[Decimal],
) -> Optional[Decimal]:
    """D4 = průměr mezi VIP CZK a Cena obchod (D1)."""
    if vip_czk is None or trade_price is None:
        return None
    return _q((vip_czk + trade_price) / 2)


def compute_prices_from_row(
    row: dict,
    shipping_eur: Optional[Decimal],
    exchange_rate: Optional[Decimal],
) -> dict[str, Optional[Decimal]]:
    """
    Dopočítá ceny podle vzorců.
    Vzorce mají přednost, aby výpočty byly konzistentní v celém importu.
    """
    sales = _decimal(row.get("sales_price"))
    unit_cc = _decimal(row.get("unit_per_cc"))
    shipping = shipping_eur if shipping_eur is not None else Decimal(0)

    out = {
        "purchase_price_imported": None,
        "margin_7_imported": None,
        "vip_eur_imported": None,
        "vip_czk_imported": None,
        "trade_price_imported": None,
        "d4_price_imported": None,
    }

    # Bez sales_price nemůžeme dopočítat nic smysluplného
    if sales is None:
        # Když chybí sales, jen zachováme případné importované hodnoty
        out["purchase_price_imported"] = _decimal(row.get("purchase_price_imported"))
        out["margin_7_imported"] = _decimal(row.get("margin_7_imported"))
        out["vip_eur_imported"] = _decimal(row.get("vip_eur_imported"))
        out["vip_czk_imported"] = _decimal(row.get("vip_czk_imported"))
        out["trade_price_imported"] = _decimal(row.get("trade_price_imported"))
        out["d4_price_imported"] = _decimal(row.get("d4_price_imported"))
        return out

    doprava_per_unit = doprava_per_unit_eur(shipping, unit_cc)
    purchase_raw = sales + doprava_per_unit

    # Zaokrouhlujeme až na konci každého výsledku (ne průběžně).
    out["purchase_price_imported"] = _q(purchase_raw)
    out["margin_7_imported"] = _q(doprava_per_unit + (sales * Decimal("1.07")))

    vip_eur = None
    if unit_cc is not None and unit_cc > 0:
        vip_eur = _q(purchase_raw + (Decimal(100) / unit_cc))
    out["vip_eur_imported"] = vip_eur if vip_eur is not None else _decimal(row.get("vip_eur_imported"))

    out["vip_czk_imported"] = compute_vip_czk(vip_eur, exchange_rate)
    if out["vip_czk_imported"] is None:
        out["vip_czk_imported"] = _decimal(row.get("vip_czk_imported"))

    out["trade_price_imported"] = _q(purchase_raw * exchange_rate * Decimal("1.12") * 2) if (exchange_rate and exchange_rate > 0) else None
    if out["trade_price_imported"] is None:
        out["trade_price_imported"] = _decimal(row.get("trade_price_imported"))

    # D4 = průměr mezi VIP CZK a Cena obchod (D1)
    out["d4_price_imported"] = compute_d4_price(out["vip_czk_imported"], out["trade_price_imported"])
    if out["d4_price_imported"] is None:
        out["d4_price_imported"] = _decimal(row.get("d4_price_imported"))

    return out
