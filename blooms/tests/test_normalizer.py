"""Testy normalizace a produktového klíče (Description + Pot-Size)."""
import pytest

from app.utils.normalizer import normalize, product_key_normalized


class TestNormalize:
    def test_none_returns_empty(self):
        assert normalize(None) == ""

    def test_empty_string_returns_empty(self):
        assert normalize("") == ""
        assert normalize("   ") == ""

    def test_lowercase(self):
        assert normalize("ABC") == "abc"

    def test_trim(self):
        assert normalize("  foo  ") == "foo"

    def test_collapse_multiple_spaces(self):
        assert normalize("a   b   c") == "a b c"

    def test_control_chars_removed(self):
        assert "\x00" not in normalize("a\x00b")

    def test_non_string_coerced(self):
        assert normalize(123) == "123"


class TestProductKeyNormalized:
    def test_both_filled(self):
        assert product_key_normalized("Ruze cervena", "C2") == "ruze cervena::c2"

    def test_description_only(self):
        assert product_key_normalized("Ruze", None) == "ruze::"

    def test_both_empty(self):
        assert product_key_normalized(None, None) == "::"

    def test_different_description_same_pot_different_key(self):
        k1 = product_key_normalized("Ruze A", "C2")
        k2 = product_key_normalized("Ruze B", "C2")
        assert k1 != k2

    def test_same_description_different_pot_different_key(self):
        k1 = product_key_normalized("Ruze", "C2")
        k2 = product_key_normalized("Ruze", "C3")
        assert k1 != k2

    def test_same_description_same_pot_same_key(self):
        k1 = product_key_normalized("Ruze", "C2")
        k2 = product_key_normalized("RUZE", "c2")
        assert k1 == k2
