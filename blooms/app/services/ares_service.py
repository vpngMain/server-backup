"""Import dat o firmě z ARES (Administrativní registr ekonomických subjektů)."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

ARES_BASE = "https://ares.gov.cz/ekonomicke-subjekty-v-be/rest"

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


@dataclass
class AresResult:
    """Výsledek z ARES – data pro vytvoření/aktualizaci odběratele."""
    company_name: str
    ico: Optional[str] = None
    dic: Optional[str] = None
    street: Optional[str] = None
    city: Optional[str] = None
    zip_code: Optional[str] = None
    country: Optional[str] = None
    error: Optional[str] = None


def _clean(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    t = str(s).strip()
    return t if t else None


def fetch_by_ico(ico: str) -> AresResult:
    """
    Načte data firmy z ARES podle IČO.
    IČO může být s nebo bez mezer.
    """
    ico_clean = "".join(c for c in str(ico).strip() if c.isdigit())
    if not ico_clean or len(ico_clean) != 8:
        return AresResult(company_name="", error=f"Neplatné IČO: očekáváno 8 číslic")
    try:
        url = f"{ARES_BASE}/ekonomicke-subjekty/{ico_clean}"
        with httpx.Client(timeout=15.0, headers=HEADERS, follow_redirects=True) as client:
            r = client.get(url)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return AresResult(company_name="", error=f"Subjekt s IČO {ico_clean} nebyl v ARES nalezen")
        return AresResult(company_name="", error=f"ARES API chyba: {e.response.status_code}")
    except Exception as e:
        logger.exception("ARES fetch by ICO failed")
        return AresResult(company_name="", error=f"Chyba při načítání z ARES: {e}")
    return _parse_ares_json(data, ico_clean)


def search_by_name(name: str, limit: int = 10) -> tuple[list[AresResult], Optional[str]]:
    """
    Vyhledá firmy v ARES podle obchodního názvu.
    Vrátí (seznam výsledků, chybová hláška).
    Název může obsahovat * jako zástupný znak.
    """
    name_clean = (name or "").strip()
    if not name_clean:
        return [], "Zadejte obchodní název"
    if len(name_clean) < 2:
        return [], "Název musí mít alespoň 2 znaky"
    # API vyhledává prefix; * na konci někdy vrací 0 výsledků, zkoušíme bez něj
    if "*" not in name_clean:
        name_clean = name_clean.rstrip()
    try:
        url = f"{ARES_BASE}/ekonomicke-subjekty/vyhledat"
        payload = {
            "obchodniJmeno": name_clean,
            "start": 0,
            "pocet": min(limit, 20),
            "razeni": [],
        }
        with httpx.Client(timeout=15.0, headers=HEADERS) as client:
            r = client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPStatusError as e:
        return [], f"ARES API chyba: {e.response.status_code}"
    except Exception as e:
        logger.exception("ARES search by name failed")
        return [], f"Chyba při vyhledávání v ARES: {e}"
    results = []
    items = data.get("ekonomickeSubjekty") or data.get("items") or []
    if isinstance(items, dict):
        items = [items]
    for item in items[:limit]:
        parsed = _parse_ares_json(item, None)
        if parsed.company_name or parsed.ico:
            results.append(parsed)
    return results, None


def _parse_ares_json(data: dict, fallback_ico: Optional[str]) -> AresResult:
    """Parsuje JSON odpověď z ARES do AresResult. Struktura dle oficiálního API ares.gov.cz."""
    if isinstance(data, list):
        data = data[0] if data else {}
    ico = _clean(data.get("ico") or fallback_ico)
    obchodni_jmeno = _clean(data.get("obchodniJmeno") or data.get("obchodni_jmeno") or data.get("nazev") or data.get("name"))
    dic = _clean(data.get("dic"))
    sídlo = data.get("sidlo") or data.get("adresa") or {}
    if isinstance(sídlo, list):
        sídlo = sídlo[0] if sídlo else {}
    # Oficiální API vrací: nazevUlice, cisloDomovni, cisloOrientacni
    ulice = _clean(
        sídlo.get("nazevUlice") or sídlo.get("ulice") or sídlo.get("street") or sídlo.get("adresaUlice")
    )
    cp = _clean(
        sídlo.get("cisloDomovni")
        or sídlo.get("cisloPopisne")
        or sídlo.get("cislo_popisne")
        or sídlo.get("cp")
    )
    co = _clean(sídlo.get("cisloOrientacni"))
    if ulice and cp and co:
        street = f"{ulice} {cp}/{co}"
    elif ulice and cp:
        street = f"{ulice} {cp}"
    elif ulice:
        street = ulice
    else:
        # textovaAdresa obsahuje celou adresu (např. "S. K. Neumanna 2007/4, Libeň, 18200 Praha 8")
        street = _clean(sídlo.get("textovaAdresa"))
    city = _clean(sídlo.get("nazevObce") or sídlo.get("nazev_obce") or sídlo.get("obec") or sídlo.get("mesto"))
    psc_val = sídlo.get("psc") or sídlo.get("zip") or sídlo.get("zipCode")
    zip_code = _clean(str(psc_val) if psc_val is not None else None)
    country = _clean(sídlo.get("nazevStatu") or sídlo.get("nazev_statu") or sídlo.get("stat") or "Česká republika")
    return AresResult(
        company_name=obchodni_jmeno or "(bez názvu)",
        ico=ico,
        dic=dic,
        street=street,
        city=city,
        zip_code=zip_code,
        country=country,
    )
