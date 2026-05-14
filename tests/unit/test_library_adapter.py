"""
Unit tests for library_adapter: parse_with_library(content, encoding).
"""

import pytest

from src.core.library_adapter import parse_with_library
from src.core.parsing import parse_mt940_custom


@pytest.mark.unit
class TestParseWithLibrary:
    """parse_with_library(content) -> (rows, account) or (None, None)."""

    def test_empty_content_returns_none_or_empty(self) -> None:
        rows, account = parse_with_library("", "utf-8")
        # Library may return None,None or ([], "") depending on mt-940 version
        if rows is None:
            assert account is None
        else:
            assert rows == []
            assert account == ""

    def test_valid_content_consistent_with_custom_parser(
        self, sample_mt940_content: str
    ) -> None:
        lib_rows, lib_account = parse_with_library(sample_mt940_content, "utf-8")
        custom_rows, custom_account = parse_mt940_custom(sample_mt940_content)
        # If library succeeds, row count should match custom; if not, custom is fallback
        assert len(custom_rows) >= 1
        assert custom_account == "NL00TEST0123456789EUR"
        if lib_rows is not None and len(lib_rows) > 0:
            assert len(lib_rows) == len(custom_rows)
            assert lib_account == custom_account
