"""Testy matchování produktu podle Description + Pot-Size při importu."""
from datetime import datetime, timezone

from app.utils.normalizer import product_key_normalized
from app.services.import_service import (
    _create_product_from_row,
    _update_product_from_row,
    _str,
)
from app.models import Product


def _utc_now():
    """Aktuální čas UTC (kompatibilní s Python 3.11+)."""
    return datetime.now(timezone.utc)


def _row(description: str, pot_size: str | None = None, **kwargs) -> dict:
    d = {"description": description, "pot_size": pot_size}
    d.update(kwargs)
    return d


class TestProductMatchingKey:
    """Stejný produkt = stejný normalizovaný klíč (Description + Pot-Size)."""

    def test_same_description_same_pot_size_same_key(self):
        key1 = product_key_normalized("Pelargonie", "10")
        key2 = product_key_normalized("pelargonie", "10")
        assert key1 == key2

    def test_same_description_different_pot_size_different_key(self):
        key1 = product_key_normalized("Pelargonie", "10")
        key2 = product_key_normalized("Pelargonie", "11")
        assert key1 != key2

    def test_different_description_same_pot_size_different_key(self):
        key1 = product_key_normalized("Pelargonie", "10")
        key2 = product_key_normalized("Petúnie", "10")
        assert key1 != key2

    def test_empty_description_different_from_any(self):
        key_empty = product_key_normalized("", "10")
        key_filled = product_key_normalized("A", "10")
        assert key_empty != key_filled


class TestCreateProductFromRow:
    """Vytvoření nového produktu z řádku – product_key_normalized musí odpovídat."""

    def test_key_from_description_and_pot_size(self):
        row = _row("Růže červená", "C2")
        product = _create_product_from_row(row, _utc_now())
        assert product.product_key_normalized == product_key_normalized("Růže červená", "C2")
        assert product.description == "Růže červená"
        assert product.pot_size == "C2"

    def test_key_with_none_pot_size(self):
        row = _row("Růže", None)
        product = _create_product_from_row(row, _utc_now())
        assert product.product_key_normalized == product_key_normalized("Růže", None)
        assert product.pot_size is None

    def test_matching_uses_same_key_logic(self):
        row1 = _row("  Pelargonie  ", "  C2  ")
        product1 = _create_product_from_row(row1, _utc_now())
        row2 = _row("Pelargonie", "C2")
        product2 = _create_product_from_row(row2, _utc_now())
        assert product1.product_key_normalized == product2.product_key_normalized


class TestUpdateProductFromRow:
    """Při matched produktu se aktualizují pole, klíč (description, pot_size) se nemění z řádku."""

    def test_existing_product_updated_not_recreated(self):
        now = _utc_now()
        existing = Product(
            id=1,
            description="Růže",
            pot_size="C2",
            product_key_normalized=product_key_normalized("Růže", "C2"),
            active=True,
            created_at=now,
            updated_at=now,
        )
        row = _row("Růže", "C2", description2="Doplňek", ean_code="123")
        _update_product_from_row(existing, row, now)
        assert existing.description2 == "Doplňek"
        assert existing.ean_code == "123"
        assert existing.description == "Růže"
        assert existing.pot_size == "C2"


class TestStrHelper:
    """Pomocná _str pro konzistenci s importem."""

    def test_none_empty(self):
        assert _str(None) is None

    def test_strip(self):
        assert _str("  a  ") == "a"

    def test_empty_string_becomes_none(self):
        assert _str("") is None
        assert _str("   ") is None
