"""Tests for the data preview helper (Resources/data_preview.py)."""

from datetime import datetime

import numpy as np
import pandas as pd
import pytest

import data_preview as dp


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------


def test_format_value_none():
    assert dp.format_value(None) == "<null>"


def test_format_value_nan():
    assert dp.format_value(float("nan")) == "<missing>"


def test_format_value_inf():
    assert dp.format_value(float("inf")) == "+inf"
    assert dp.format_value(float("-inf")) == "-inf"


def test_format_value_empty_string():
    assert dp.format_value("") == "<empty>"


def test_format_value_bytes():
    assert dp.format_value(b"\x01\x02") == "0x0102"


def test_format_value_datetime():
    assert dp.format_value(datetime(2020, 1, 2, 3, 4, 5)) == "2020-01-02T03:04:05"


def test_format_value_collapses_whitespace():
    assert dp.format_value("  a\n\tb  ") == "a b"


def test_display_width_ascii_and_cjk():
    assert dp.display_width("ab") == 2
    assert dp.display_width("中文") == 4
    assert dp.display_width("a中") == 3


def test_clip_short_text_unchanged():
    assert dp.clip("abc", 4) == "abc"


def test_clip_long_text_truncated():
    assert dp.clip("abcdef", 4) == "abc…"


def test_human_size():
    assert dp.human_size(0) == "0 B"
    assert dp.human_size(1024) == "1.0 KiB"
    assert dp.human_size(1536) == "1.5 KiB"


def test_can_offer_all_rows():
    assert dp.can_offer_all_rows(100, 10) is True
    assert dp.can_offer_all_rows(2001, 1) is False  # exceeds MAX_FULL_ROWS
    assert dp.can_offer_all_rows(1000, 200) is False  # exceeds MAX_FULL_CELLS
    assert dp.can_offer_all_rows(0, 5) is True
    assert dp.can_offer_all_rows(100, 0) is True  # no columns -> max(1, 0)


# ---------------------------------------------------------------------------
# Integration: DTA preview (text mode)
# ---------------------------------------------------------------------------


def _write_dta(path, nrows, with_labels=False):
    df = pd.DataFrame(
        {
            "a": np.arange(nrows, dtype=float),
            "b": [f"x{i}" for i in range(nrows)],
        }
    )
    kwargs = {"write_index": False}
    if with_labels:
        kwargs["variable_labels"] = {"a": "Numeric column", "b": "String column"}
    df.to_stata(str(path), **kwargs)


@pytest.mark.parametrize("nrows", [3, 50, 501, 2000, 2001])
def test_preview_dta_row_bounds(tmp_path, capsys, nrows):
    path = tmp_path / "test.dta"
    _write_dta(path, nrows)
    dp.preview_dta(path)
    out = capsys.readouterr().out
    assert "DATA PREVIEW" in out
    assert "Structure:" in out


def test_preview_dta_reports_row_count(tmp_path, capsys):
    path = tmp_path / "test.dta"
    _write_dta(path, 42)
    dp.preview_dta(path)
    out = capsys.readouterr().out
    assert "42 rows" in out
    assert "2 variables" in out


def test_preview_dta_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        dp.preview_dta(tmp_path / "does-not-exist.dta")


# ---------------------------------------------------------------------------
# Integration: Parquet preview (text mode)
# ---------------------------------------------------------------------------


def _write_parquet(path, nrows):
    df = pd.DataFrame(
        {
            "a": np.arange(nrows, dtype=float),
            "b": [f"x{i}" for i in range(nrows)],
        }
    )
    df.to_parquet(str(path))


def test_preview_parquet_reports_structure(tmp_path, capsys):
    path = tmp_path / "test.parquet"
    _write_parquet(path, 10)
    dp.preview_parquet(path)
    out = capsys.readouterr().out
    assert "DATA PREVIEW" in out
    assert "Apache Parquet" in out
    assert "10 rows" in out


def test_preview_parquet_empty(tmp_path, capsys):
    path = tmp_path / "empty.parquet"
    pd.DataFrame({"a": pd.Series(dtype="float64")}).to_parquet(str(path))
    dp.preview_parquet(path)
    out = capsys.readouterr().out
    assert "DATA PREVIEW" in out


# ---------------------------------------------------------------------------
# DTA header parsing (no pandas private-attribute dependency)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("version", [114, 117, 118, 119])
def test_read_dta_header_matches_pandas(tmp_path, version):
    nrows = 123
    df = pd.DataFrame({"a": np.arange(nrows, dtype=float)})
    path = tmp_path / f"test_{version}.dta"
    df.to_stata(str(path), write_index=False, version=version)

    parsed_version, parsed_nobs = dp.read_dta_header(path)
    assert parsed_version == version
    assert parsed_nobs == nrows

    # Cross-check against pandas' own reported row count.
    with pd.io.stata.StataReader(
        path, convert_categoricals=False, convert_dates=True, preserve_dtypes=True
    ) as reader:
        reader.read(nrows=1, convert_categoricals=False, convert_dates=True, preserve_dtypes=True)
        assert int(reader._nobs) == nrows
        assert int(reader._format_version) == version


def test_read_dta_header_rejects_non_dta(tmp_path):
    path = tmp_path / "not.dta"
    path.write_bytes(b"this is not a dta file at all")
    with pytest.raises(ValueError):
        dp.read_dta_header(path)


# ---------------------------------------------------------------------------
# Value label matching
# ---------------------------------------------------------------------------


def test_value_label_for_matches_numpy_key_to_float_value():
    mapping = {np.int32(1): "Male", np.int32(2): "Female"}
    assert dp.value_label_for(mapping, 1.0) == "Male"
    assert dp.value_label_for(mapping, np.int8(2)) == "Female"
    assert dp.value_label_for(mapping, 3.0) is None
    assert dp.value_label_for(mapping, None) is None


# ---------------------------------------------------------------------------
# Metadata display (variable labels / value labels / data label / timestamp)
# ---------------------------------------------------------------------------


def _write_labeled_dta(path):
    df = pd.DataFrame({"sex": [1.0, 2.0, 1.0, np.nan]})
    df.to_stata(
        str(path),
        write_index=False,
        variable_labels={"sex": "Gender of respondent"},
        value_labels={"sex": {1.0: "Male", 2.0: "Female"}},
    )


def test_preview_dta_shows_metadata_by_default(tmp_path, capsys):
    path = tmp_path / "labeled.dta"
    _write_labeled_dta(path)
    assert dp.SHOW_METADATA is True  # default
    dp.preview_dta(path)
    out = capsys.readouterr().out
    assert "Gender of respondent" in out
    assert "Male" in out
    assert "Female" in out


def test_preview_dta_hides_metadata_when_disabled(tmp_path, capsys, monkeypatch):
    path = tmp_path / "labeled.dta"
    _write_labeled_dta(path)
    monkeypatch.setattr(dp, "SHOW_METADATA", False)
    dp.preview_dta(path)
    out = capsys.readouterr().out
    assert "Gender of respondent" not in out
    assert "Male" not in out


def test_preview_dta_html_includes_value_labels_and_label_row(
    tmp_path, capsys, monkeypatch
):
    path = tmp_path / "labeled.dta"
    _write_labeled_dta(path)
    monkeypatch.setattr(dp, "OUTPUT_HTML", True)
    dp.preview_dta(path)
    out = capsys.readouterr().out
    assert '<summary>Value labels</summary>' in out
    assert "Gender of respondent" in out
    assert 'class="label"' in out


def test_preview_dta_html_hides_metadata_when_disabled(
    tmp_path, capsys, monkeypatch
):
    path = tmp_path / "labeled.dta"
    _write_labeled_dta(path)
    monkeypatch.setattr(dp, "OUTPUT_HTML", True)
    monkeypatch.setattr(dp, "SHOW_METADATA", False)
    dp.preview_dta(path)
    out = capsys.readouterr().out
    assert '<summary>Value labels</summary>' not in out
    assert "Gender of respondent" not in out
    assert 'class="label"' not in out


# ---------------------------------------------------------------------------
# Boolean columns align right (regression guard)
# ---------------------------------------------------------------------------


def test_preview_boolean_column_is_numeric(tmp_path, capsys, monkeypatch):
    path = tmp_path / "bool.dta"
    pd.DataFrame({"flag": [True, False, True]}).to_stata(str(path), write_index=False)
    monkeypatch.setattr(dp, "OUTPUT_HTML", True)
    dp.preview_dta(path)
    out = capsys.readouterr().out
    # The boolean column should be marked numeric (right-aligned).
    assert "numeric" in out


def test_preview_parquet_html_omits_internal_metadata(tmp_path, capsys, monkeypatch):
    path = tmp_path / "test.parquet"
    pd.DataFrame({"a": [1.0, 2.0, 3.0]}).to_parquet(str(path))
    monkeypatch.setattr(dp, "OUTPUT_HTML", True)
    dp.preview_parquet(path)
    out = capsys.readouterr().out
    # pyarrow/pandas write internal blobs; these must not be shown as metadata.
    assert "ARROW:schema" not in out
    assert "pandas" not in out
