"""Jednotné vzorce cen pro import a produkt. Vše zaokrouhleno na 2 desetinná místa."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

PRICE_QUANTIZE = Decimal("0.01")


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
# • D1 (cena obchod, CZK) = cena + doprava×eurKurz×1.12×2
#   = sales×eurKurz + (doprava_eur/unit_cc)×eurKurz×1.12×2
#
# D4 = průměr mezi VIP Eur a Sales Price (EUR).


def doprava_per_unit_eur(
    shipping_eur: Optional[Decimal],
    unit_per_cc: Optional[Decimal],
) -> Decimal:
    """Doprava na jednotku v EUR. Při chybějícím unit_cc vrací 0."""
    if not unit_per_cc or unit_per_cc <= 0:
        return Decimal(0)
    shipping = shipping_eur if shipping_eur is not None else Decimal(0)
    return _q(shipping / unit_per_cc)


def compute_purchase_price(
    sales_price: Optional[Decimal],
    doprava_per_unit: Decimal,
) -> Optional[Decimal]:
    """Cena + doprava (Purchase) = sales_price + doprava_per_unit (EUR)."""
    if sales_price is None:
        return None
    return _q(sales_price + doprava_per_unit)


def compute_margin_7(
    purchase_price: Optional[Decimal],
) -> Optional[Decimal]:
    """7% marže + doprava = (cena + doprava) × 1.07 (EUR)."""
    if purchase_price is None:
        return None
    return _q(purchase_price * Decimal("1.07"))


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
    sales_price: Optional[Decimal],
    doprava_per_unit: Decimal,
    exchange_rate: Optional[Decimal],
) -> Optional[Decimal]:
    """D1 (cena obchod, CZK) = cena + doprava×eurKurz×1.12×2.
    cena (CZK) = sales×eurKurz, doprava část (CZK) = doprava_per_unit×eurKurz×1.12×2.
    """
    if sales_price is None or not exchange_rate or exchange_rate <= 0:
        return None
    cena_czk = sales_price * exchange_rate
    doprava_czk = doprava_per_unit * exchange_rate * Decimal("1.12") * 2
    return _q(cena_czk + doprava_czk)


def compute_d4_price(
    sales_price: Optional[Decimal],
    vip_eur: Optional[Decimal],
) -> Optional[Decimal]:
    """D4 = průměr mezi VIP Eur a Sales Price (v EUR)."""
    if sales_price is None or vip_eur is None:
        return None
    return _q((sales_price + vip_eur) / 2)


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

    out["purchase_price_imported"] = compute_purchase_price(sales, doprava_per_unit)
    out["margin_7_imported"] = compute_margin_7(out["purchase_price_imported"])

    vip_eur = compute_vip_eur(out["purchase_price_imported"], unit_cc)
    out["vip_eur_imported"] = vip_eur if vip_eur is not None else _decimal(row.get("vip_eur_imported"))

    out["vip_czk_imported"] = compute_vip_czk(vip_eur, exchange_rate)
    if out["vip_czk_imported"] is None:
        out["vip_czk_imported"] = _decimal(row.get("vip_czk_imported"))

    out["trade_price_imported"] = compute_trade_price_d1(sales, doprava_per_unit, exchange_rate)
    if out["trade_price_imported"] is None:
        out["trade_price_imported"] = _decimal(row.get("trade_price_imported"))

    # D4 = průměr mezi VIP Eur a Sales Price
    out["d4_price_imported"] = compute_d4_price(sales, out["vip_eur_imported"])
    if out["d4_price_imported"] is None:
        out["d4_price_imported"] = _decimal(row.get("d4_price_imported"))

    return out
