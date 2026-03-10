"""Extrakce čísla objednávky z názvu souboru."""
import re
from typing import Optional


# Regex vzory pro číslo objednávky v názvu souboru
ORDER_PATTERNS = [
    r"objednavka\s*[_\s-]*(\d+)",
    r"objednávka\s*[_\s-]*(\d+)",
    r"order\s*[_\s-]*(\d+)",
    r"obj[_\s-]*(\d+)",
    r"(\d{5,})",  # alespoň 5 číslic za sebou
    r"[\s_-](\d{4,})[\s_.-]",  # 4+ číslice ohraničené
]


def extract_order_number(filename: str) -> Optional[str]:
    """
    Z názvu souboru (bez cesty) zkusí vyčíst číslo objednávky.
    Vrátí řetězec čísla nebo None.
    """
    if not filename or not filename.strip():
        return None
    # Pouze basename, lowercase pro matching
    name = filename.lower().strip()
    # Odstranit příponu
    if name.endswith(".xls"):
        name = name[:-4]
    elif name.endswith(".xlsx"):
        name = name[:-5]

    for pattern in ORDER_PATTERNS:
        m = re.search(pattern, name, re.IGNORECASE)
        if m:
            return m.group(1)
    return None
