"""Normalizace textu pro produktový klíč (Description + Pot-Size)."""
import re
from typing import Optional


def normalize(value: Optional[str]) -> str:
    """
    Normalizuje řetězec pro porovnání:
    - trim
    - lowercase
    - odstranění vícenásobných mezer
    - odstranění běžných rušivých znaků
    - null/empty -> prázdný řetězec
    """
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value).strip()
    else:
        value = value.strip()
    value = value.lower()
    # Vícenásobné mezery na jednu
    value = re.sub(r"\s+", " ", value)
    # Rušivé znaky (např. nulové znaky, řídicí znaky)
    value = re.sub(r"[\x00-\x1f\x7f]", "", value)
    return value


def product_key_normalized(description: Optional[str], pot_size: Optional[str]) -> str:
    """
    Vytvoří normalizovaný klíč produktu: normalized(description) + "::" + normalized(pot_size).
    Používá se pro rozpoznání stejného produktu.
    """
    d = normalize(description) if description is not None else ""
    p = normalize(pot_size) if pot_size is not None else ""
    return f"{d}::{p}"


def base_description_for_key(description: Optional[str], pot_size: Optional[str]) -> str:
    """
    Pro klíč produktu odřízne suffix ve tvaru ' K{pot_size}' pokud je přítomen.
    Např. 'OCIMUM BASILICUM K11' + pot_size '11' -> 'OCIMUM BASILICUM'
    """
    d = (description or "").strip()
    p = (pot_size or "").strip()
    if not d or not p:
        return d
    suffix = f" K{p}"
    if d.upper().endswith(suffix.upper()):
        return d[: -len(suffix)].rstrip()
    return d
