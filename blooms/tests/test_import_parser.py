"""Testy parseru .xls – mapování hlaviček a struktura výsledku."""
import pytest
from pathlib import Path

from app.services.import_parser import (
    _normalize_header,
    _header_matches,
    _find_column_index,
    parse_xls_file,
    ParsedXlsResult,
    COLUMN_ALIASES,
)


class TestNormalizeHeader:
    def test_bom_stripped(self):
        assert _normalize_header("\ufeffDescription") == "description"

    def test_lowercase(self):
        assert _normalize_header("Description") == "description"

    def test_collapse_spaces(self):
        assert _normalize_header("  Pot   Size  ") == "pot size"

    def test_none_empty(self):
        assert _normalize_header(None) == ""


class TestHeaderMatches:
    def test_exact_match(self):
        assert _header_matches("description", "description") is True

    def test_alias_contained_in_header(self):
        assert _header_matches("description (1)", "description") is True

    def test_short_header_in_alias(self):
        assert _header_matches("desc", "description") is True

    def test_no_match(self):
        assert _header_matches("price", "description") is False


class TestFindColumnIndex:
    def test_finds_description_exact(self):
        row = ["ID", "Description", "Qty"]
        assert _find_column_index(row, "description") == 1

    def test_finds_description_case_insensitive(self):
        row = ["DESCRIPTION", "Other"]
        assert _find_column_index(row, "description") == 0

    def test_finds_pot_size_variant(self):
        row = ["Description", "Pot-Size", "Qty"]
        assert _find_column_index(row, "pot_size") == 1

    def test_finds_czech_header(self):
        row = ["Popis", "Množství"]
        assert _find_column_index(row, "description") == 0
        assert _find_column_index(row, "qty") == 1

    def test_not_found_returns_none(self):
        row = ["Col1", "Col2"]
        assert _find_column_index(row, "description") is None


class TestParseXlsFile:
    """Testy parse_xls_file – vyžadují nebo nemusí mít .xls soubor."""

    def test_missing_file_returns_warnings_and_empty_rows(self):
        result = parse_xls_file(Path("/nonexistent/file_import_parser_test.xls"))
        assert isinstance(result, ParsedXlsResult)
        assert result.rows == []
        assert len(result.warnings) >= 1
