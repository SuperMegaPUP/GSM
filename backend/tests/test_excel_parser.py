"""Тесты парсера Excel-каталогов."""

from pathlib import Path

from app.services.excel_parser import (
    cleanse_value,
    detect_column_groups,
    parse_japanese_catalog,
    list_sheets,
)

KATALOG_PATH = "/home/gsm/katalog_gsm.xlsx"


class TestCleanseValue:
    def test_nan_returns_none(self):
        import pandas as pd
        assert cleanse_value(pd.NA) is None
        assert cleanse_value(pd.NA) is None

    def test_empty_values_return_none(self):
        assert cleanse_value("-") is None
        assert cleanse_value("—") is None
        assert cleanse_value("T/M") is None
        assert cleanse_value("") is None
        assert cleanse_value(" ") is None

    def test_viscosity_cleaning(self):
        assert cleanse_value("10W-30(5W-30)") == "10W-30"
        assert cleanse_value("5W-30") == "5W-30"

    def test_api_class_cleaning(self):
        assert cleanse_value("SH(SJ/GF-2)") == "SH"

    def test_volume_cleaning(self):
        assert cleanse_value("4.2(4.5)") == "4.2"

    def test_collapse_spaces(self):
        assert cleanse_value("G-Box ATF  G-Box ATF") == "G-Box ATF G-Box ATF"

    def test_normal_value_passes(self):
        assert cleanse_value("0W-20") == "0W-20"
        assert cleanse_value("API SN") == "API SN"


class TestListSheets:
    def test_returns_all_sheets(self):
        sheets = list_sheets(KATALOG_PATH)
        assert len(sheets) == 10
        assert "Toyota" in sheets or "TOYOTA" in sheets
        assert "Honda" in sheets or "HONDA" in sheets


class TestDetectColumnGroups:
    def test_groups_detected(self):
        import pandas as pd
        df = pd.read_excel(KATALOG_PATH, header=[0, 1], sheet_name="TOYOTA", nrows=1)
        groups = detect_column_groups(df)
        identifiers = [g for g in groups if g.is_identifier]
        nodes = [g for g in groups if g.node_type]
        assert len(identifiers) >= 1
        assert len(nodes) >= 1


class TestParseJapaneseCatalog:
    def test_parse_toyota_first_10(self):
        result = parse_japanese_catalog(KATALOG_PATH, sheet_name="TOYOTA", max_rows=10)
        assert result.total_excel_rows >= 10
        assert len(result.rows) > 0
        assert result.errors == []

    def test_parse_all_sheets(self):
        sheets = list_sheets(KATALOG_PATH)
        total_rows = 0
        total_errors = 0
        for sheet in sheets:
            result = parse_japanese_catalog(KATALOG_PATH, sheet_name=sheet)
            total_rows += len(result.rows)
            total_errors += len(result.errors)
        assert total_rows > 0
        assert total_errors == 0

    def test_row_has_required_fields(self):
        result = parse_japanese_catalog(KATALOG_PATH, sheet_name="TOYOTA", max_rows=5)
        for row in result.rows:
            assert row.brand is not None
            assert row.model is not None
            assert row.node_type is not None
