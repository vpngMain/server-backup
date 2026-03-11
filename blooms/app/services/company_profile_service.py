"""Načtení/uložení firemního profilu + předvyplnění z ARES."""
from __future__ import annotations

import json
import os
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

from app.config import BASE_DIR


def _profile_path() -> Path:
    p = BASE_DIR / "instance" / "company_profile.json"
    p.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    return p


def default_profile_from_config(config) -> dict:
    return {
        "name": config.get("COMPANY_NAME", ""),
        "street": config.get("COMPANY_STREET", ""),
        "city": config.get("COMPANY_CITY", ""),
        "zip": config.get("COMPANY_ZIP", ""),
        "country": config.get("COMPANY_COUNTRY", ""),
        "ico": config.get("COMPANY_ICO", ""),
        "dic": config.get("COMPANY_DIC", ""),
        "phone": config.get("COMPANY_PHONE", ""),
        "email": config.get("COMPANY_EMAIL", ""),
    }


def load_company_profile(config) -> dict:
    defaults = default_profile_from_config(config)
    p = _profile_path()
    if not p.exists():
        return defaults
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return defaults
        out = dict(defaults)
        out.update({k: str(v) for k, v in data.items() if k in out and v is not None})
        return out
    except Exception:
        return defaults


def save_company_profile(config, profile: dict) -> dict:
    allowed = default_profile_from_config(config).keys()
    out = {k: (str(profile.get(k, "")).strip() if profile.get(k) is not None else "") for k in allowed}
    p = _profile_path()
    content = json.dumps(out, ensure_ascii=False, indent=2)
    # Atomický zápis: temp soubor ve stejné složce, pak rename
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix="company_profile.", suffix=".tmp")
    try:
        os.write(fd, content.encode("utf-8"))
        os.close(fd)
        fd = None
        Path(tmp).replace(p)
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if Path(tmp).exists():
            Path(tmp).unlink(missing_ok=True)
    return out


def _digits_only(value: str) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def fetch_company_from_ares(ico: str) -> dict:
    ico_clean = _digits_only(ico)
    if not ico_clean:
        raise ValueError("Zadejte IČO.")
    url = f"https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/{urllib.parse.quote(ico_clean)}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("ARES nevrátil platná data.")

    sidlo = data.get("sidlo") or {}
    street = " ".join([
        str(sidlo.get("nazevUlice") or "").strip(),
        str(sidlo.get("cisloDomovni") or "").strip(),
        str(sidlo.get("cisloOrientacni") or "").strip(),
    ]).strip()
    profile = {
        "name": str(data.get("obchodniJmeno") or data.get("nazev") or "").strip(),
        "street": street,
        "city": str(sidlo.get("nazevObce") or "").strip(),
        "zip": str(sidlo.get("psc") or "").strip(),
        "country": str(sidlo.get("nazevStatu") or "Česká republika").strip(),
        "ico": ico_clean,
        "dic": str(data.get("dic") or "").strip(),
        "phone": "",
        "email": "",
    }
    return profile
