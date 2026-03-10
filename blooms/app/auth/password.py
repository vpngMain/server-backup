"""Hashování hesel. Použití bcrypt přímo (bez passlib) – limit 72 bajtů obcházíme SHA256."""
import hashlib
import bcrypt


def _to_bcrypt_input(password: str) -> bytes:
    """Převede heslo na 64 bajtů (SHA256 hex), aby bcrypt nikdy nedostal víc než 72 bajtů."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest().encode("utf-8")


def hash_password(password: str) -> str:
    data = _to_bcrypt_input(password)
    return bcrypt.hashpw(data, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    if not hashed or not hashed.startswith("$2"):
        return False
    hashed_b = hashed.encode("utf-8")
    # Nový způsob: bcrypt(SHA256(heslo)) – libovolná délka hesla
    if bcrypt.checkpw(_to_bcrypt_input(plain), hashed_b):
        return True
    # Zpětná kompatibilita: staré záznamy jsou bcrypt(heslo) – heslo max 72 bajtů
    try:
        raw = plain.encode("utf-8")[:72]
        return bcrypt.checkpw(raw, hashed_b)
    except (ValueError, Exception):
        return False
