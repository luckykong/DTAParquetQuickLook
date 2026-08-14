#!/usr/bin/env python3
"""Fast, bounded text and HTML previews for Stata DTA and Apache Parquet files."""

from __future__ import annotations

import math
import os
import re
import struct
import sys
import unicodedata
from datetime import date, datetime
from html import escape as escape_html
from numbers import Number
from pathlib import Path
from typing import Any, Callable


INITIAL_ROWS = 50
EXTENDED_ROWS = 500
MAX_FULL_ROWS = 2_000
MAX_FULL_CELLS = 100_000
MAX_CELL_WIDTH = 28
MAX_HTML_CELL_WIDTH = 120
OUTPUT_HTML = False

# Metadata (variable labels, value labels, data label, timestamp) is shown by
# default and can be turned off via the DTA_PARQUET_SHOW_METADATA environment
# variable, which the render service derives from config.json's "show_metadata".
SHOW_METADATA = os.environ.get("DTA_PARQUET_SHOW_METADATA", "1").strip().lower() not in (
    "",
    "0",
    "false",
    "no",
    "off",
)


def can_offer_all_rows(total_rows: int, variable_count: int) -> bool:
    """Keep full previews bounded by both observations and rendered cells."""
    return (
        total_rows <= MAX_FULL_ROWS
        and total_rows * max(1, variable_count) <= MAX_FULL_CELLS
    )


def display_width(text: str) -> int:
    return sum(
        2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
        for char in text
        if not unicodedata.combining(char)
    )


def clip(text: str, width: int) -> str:
    if display_width(text) <= width:
        return text
    if width <= 1:
        return "…"[:width]
    output: list[str] = []
    used = 0
    for char in text:
        char_width = 0 if unicodedata.combining(char) else (
            2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
        )
        if used + char_width > width - 1:
            break
        output.append(char)
        used += char_width
    return "".join(output) + "…"


def pad(text: str, width: int, right: bool = False) -> str:
    text = clip(text, width)
    spaces = " " * max(0, width - display_width(text))
    return spaces + text if right else text + spaces


def format_value(value: Any) -> str:
    if value is None:
        return "<null>"
    if isinstance(value, bytes):
        return "0x" + value[:12].hex() + ("…" if len(value) > 12 else "")
    if isinstance(value, float):
        if math.isnan(value):
            return "<missing>"
        if math.isinf(value):
            return "+inf" if value > 0 else "-inf"
        return f"{value:.10g}"
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    try:
        missing = value is not None and bool(value != value)
    except (TypeError, ValueError):
        missing = False
    if missing:
        return "<missing>"
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text if text else "<empty>"


def human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"


def format_rows(total_rows: int | None) -> str:
    """Render a row count, tolerating an unknown total (pandas API drift)."""
    return "?" if total_rows is None else f"{total_rows:,}"


def _normalize_code(value: Any) -> Any:
    """Map numpy scalars and Python numbers to a comparable scalar."""
    if isinstance(value, Number):
        return float(value)
    return str(value)


def value_label_for(mapping: dict[Any, str] | None, value: Any) -> str | None:
    """Return the value label for a cell value, or None if unmapped."""
    if not mapping or value is None:
        return None
    if value in mapping:
        return mapping[value]
    target = _normalize_code(value)
    for code, label in mapping.items():
        if _normalize_code(code) == target:
            return label
    return None


def read_dta_header(path: Path) -> tuple[int, int]:
    """Parse a DTA file header and return (format_version, nobs).

    Mirrors pandas' header layout without depending on its private attributes:

    * New-style formats 117/118/119 begin with the XML-style marker
      ``<stata_dta><header><release>NNN</release>...``.
    * Old-style formats 104-115 encode the version as the first byte.
    """
    with path.open("rb") as handle:
        first = handle.read(1)
        if not first:
            raise ValueError("empty file")
        if first == b"<":
            handle.read(27)  # "stata_dta><header><release>"
            version = int(handle.read(3))
            if version not in (117, 118, 119):
                raise ValueError(f"unsupported dta format version {version}")
            handle.read(21)  # "</release><byteorder>"
            order = handle.read(3)
            byteorder = ">" if order == b"MSF" else "<"
            handle.read(15)  # "</byteorder><K>"
            handle.read(2 if version <= 118 else 4)  # nvar
            handle.read(7)  # "</K><N>"
            width = 8 if version >= 118 else 4
            fmt = "Q" if version >= 118 else "I"
            nobs = struct.unpack(byteorder + fmt, handle.read(width))[0]
            return version, nobs

        version = first[0]
        if version not in (104, 105, 108, 111, 113, 114, 115):
            raise ValueError(f"unsupported dta format version {version}")
        marker = handle.read(1)
        byteorder = ">" if marker == b"\x01" else "<"
        handle.read(2)  # filetype + unused
        handle.read(2)  # nvar (uint16)
        nobs = struct.unpack(byteorder + "I", handle.read(4))[0]
        return version, nobs


def render_table(
    path: Path,
    format_name: str,
    total_rows: int | None,
    columns: list[str],
    types: list[str],
    preview_rows: int,
    value_at: Callable[[int, int], Any],
    all_rows_available: bool,
    variable_labels: dict[str, str] | None = None,
    value_labels: dict[str, dict[Any, str]] | None = None,
    data_label: str = "",
    time_stamp: str = "",
    extra_metadata: dict[str, str] | None = None,
) -> None:
    variable_labels = variable_labels or {}
    value_labels = value_labels or {}
    data_label = data_label or ""
    time_stamp = time_stamp or ""
    extra_metadata = extra_metadata or {}

    if OUTPUT_HTML:
        render_html_table(
            path,
            format_name,
            total_rows,
            columns,
            types,
            preview_rows,
            value_at,
            all_rows_available,
            variable_labels,
            value_labels,
            data_label,
            time_stamp,
            extra_metadata,
        )
        return

    print(f"DATA PREVIEW  {path.name}")
    print(f"Format: {format_name}")
    print(f"File size: {human_size(path.stat().st_size)}")
    print(f"Structure: {format_rows(total_rows)} rows × {len(columns):,} variables")
    if all_rows_available:
        print(f"Showing: all {preview_rows:,} rows × all {len(columns):,} variables")
    else:
        print(f"Showing: first {preview_rows:,} rows × all {len(columns):,} variables")
    print(
        "Read policy: full data is available only when the file has at most "
        f"{MAX_FULL_ROWS:,} rows and {MAX_FULL_CELLS:,} cells; otherwise at most "
        f"the first {EXTENDED_ROWS:,} rows are read."
    )
    if SHOW_METADATA:
        if data_label:
            print(f"Data label: {data_label}")
        if time_stamp:
            print(f"Timestamp: {time_stamp}")
        if variable_labels:
            entries = [f"{col}: {label}" for col, label in variable_labels.items() if label]
            if entries:
                print("Variable labels:")
                for entry in entries:
                    print(f"  {entry}")
        if value_labels:
            print("Value labels:")
            for col, mapping in value_labels.items():
                if mapping:
                    rendered = ", ".join(f"{key} = {label}" for key, label in mapping.items())
                    print(f"  {col}: {rendered}")
        if extra_metadata:
            print("Metadata:")
            for key, value in extra_metadata.items():
                print(f"  {key}: {value}")
    print()

    if not columns:
        print("<no variables>")
        return

    headers = ["#", *columns]
    type_cells = ["type", *[f"<{item}>" for item in types]]
    widths = [max(4, len(str(max(1, preview_rows))))]
    numeric = [True]

    for column_index, header in enumerate(columns):
        width = max(display_width(header), display_width(type_cells[column_index + 1]), 4)
        is_numeric = True
        for row_index in range(preview_rows):
            value = value_at(row_index, column_index)
            is_numeric = is_numeric and (value is None or isinstance(value, Number))
            width = max(width, display_width(format_value(value)))
        widths.append(min(MAX_CELL_WIDTH, width))
        numeric.append(is_numeric)

    def output_row(cells: list[str], type_row: bool = False) -> None:
        print(
            "| "
            + " | ".join(
                pad(cell, widths[index], right=(numeric[index] and not type_row))
                for index, cell in enumerate(cells)
            )
            + " |"
        )

    output_row(headers, type_row=True)
    output_row(type_cells, type_row=True)
    print("+-" + "-+-".join("-" * width for width in widths) + "-+")
    for row_index in range(preview_rows):
        output_row(
            [str(row_index + 1)]
            + [format_value(value_at(row_index, column_index)) for column_index in range(len(columns))]
        )


def render_html_table(
    path: Path,
    format_name: str,
    total_rows: int | None,
    columns: list[str],
    types: list[str],
    preview_rows: int,
    value_at: Callable[[int, int], Any],
    all_rows_available: bool,
    variable_labels: dict[str, str],
    value_labels: dict[str, dict[Any, str]],
    data_label: str,
    time_stamp: str,
    extra_metadata: dict[str, str],
) -> None:
    numeric: list[bool] = []
    for column_index in range(len(columns)):
        is_numeric = True
        for row_index in range(preview_rows):
            value = value_at(row_index, column_index)
            is_numeric = is_numeric and (value is None or isinstance(value, Number))
        numeric.append(is_numeric)

    print("""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
html, body { margin: 0; height: 100%; overflow: hidden; background: Canvas; color: CanvasText; }
body { display: flex; flex-direction: column; font-family: -apple-system, BlinkMacSystemFont, sans-serif; }
.summary { flex: none; padding: 10px 14px; border-bottom: 1px solid rgba(127,127,127,.35); border-bottom: 1px solid color-mix(in srgb, CanvasText 15%, transparent); background: Canvas; }
.meta { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.badge { padding: 2px 7px; border: 1px solid rgba(127,127,127,.35); border: 1px solid color-mix(in srgb, CanvasText 15%, transparent); border-radius: 999px; font-size: 10px; background: rgba(127,127,127,.08); background: color-mix(in srgb, CanvasText 4%, transparent); }
.metadata { flex: none; margin: 8px 14px 0; font-size: 11px; }
.metadata summary { cursor: pointer; color: rgba(127,127,127,.7); color: color-mix(in srgb, CanvasText 58%, transparent); }
.metadata-body { margin: 6px 0 0; padding: 6px 9px; border-left: 2px solid rgba(127,127,127,.35); border-left: 2px solid color-mix(in srgb, CanvasText 15%, transparent); }
.vl-row { display: flex; gap: 8px; padding: 1px 0; }
.vl-row code { font-weight: 650; }
.vl-map { color: rgba(127,127,127,.7); color: color-mix(in srgb, CanvasText 58%, transparent); }
.table-wrap { flex: 1; width: 100%; overflow: auto; }
table { border-collapse: separate; border-spacing: 0; width: max-content; font: 11.5px/1.3 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
th, td { padding: 4px 7px; border-right: 1px solid rgba(127,127,127,.35); border-right: 1px solid color-mix(in srgb, CanvasText 15%, transparent); border-bottom: 1px solid rgba(127,127,127,.35); border-bottom: 1px solid color-mix(in srgb, CanvasText 15%, transparent); white-space: nowrap; vertical-align: middle; }
thead th { position: sticky; top: 0; z-index: 2; text-align: left; background: Canvas; background: color-mix(in srgb, Canvas 96%, CanvasText 4%); box-shadow: 0 1px 0 rgba(127,127,127,.35); box-shadow: 0 1px 0 color-mix(in srgb, CanvasText 15%, transparent); }
.row-number { position: sticky; left: 0; z-index: 1; min-width: 38px; text-align: right; color: rgba(127,127,127,.7); color: color-mix(in srgb, CanvasText 58%, transparent); background: Canvas; font-variant-numeric: tabular-nums; }
thead .row-number { z-index: 3; }
tbody tr:nth-child(even) td { background: rgba(127,127,127,.08); background: color-mix(in srgb, CanvasText 4%, transparent); }
tbody tr:nth-child(even) .row-number { background: Canvas; background: color-mix(in srgb, Canvas 96%, CanvasText 4%); }
.name { display: block; max-width: 180px; overflow: hidden; text-overflow: ellipsis; font-weight: 650; }
.type { display: block; max-width: 180px; overflow: hidden; text-overflow: ellipsis; margin-top: 1px; color: rgba(127,127,127,.7); color: color-mix(in srgb, CanvasText 58%, transparent); font-size: 9px; font-weight: 400; }
.label { display: block; max-width: 180px; overflow: hidden; text-overflow: ellipsis; margin-top: 1px; color: rgba(127,127,127,.7); color: color-mix(in srgb, CanvasText 58%, transparent); font-size: 9px; font-weight: 400; font-style: italic; }
.cell { display: block; max-width: 220px; overflow: hidden; text-overflow: ellipsis; }
.numeric { text-align: right; font-variant-numeric: tabular-nums; }
.missing { color: rgba(127,127,127,.7); color: color-mix(in srgb, CanvasText 58%, transparent); font-style: italic; }
.mode-toggle { position: absolute; inline-size: 1px; block-size: 1px; opacity: 0; pointer-events: none; }
.mode-controls { display: inline-flex; overflow: hidden; border: 1px solid rgba(127,127,127,.35); border: 1px solid color-mix(in srgb, CanvasText 15%, transparent); border-radius: 7px; }
.mode-button { padding: 2px 8px; color: rgba(127,127,127,.7); color: color-mix(in srgb, CanvasText 58%, transparent); font-size: 10px; cursor: pointer; user-select: none; background: Canvas; }
.mode-button + .mode-button { border-left: 1px solid rgba(127,127,127,.35); border-left: 1px solid color-mix(in srgb, CanvasText 15%, transparent); }
#rows-first:checked ~ .summary .mode-button[for="rows-first"] { color: Canvas; background: CanvasText; }
#rows-extended:checked ~ .summary .mode-button[for="rows-extended"] { color: Canvas; background: CanvasText; }
#rows-first:checked ~ .table-wrap tbody tr:nth-child(n+51) { display: none; }
</style>
</head>
<body>""")
    toggle_available = preview_rows > INITIAL_ROWS
    if toggle_available:
        print('<input class="mode-toggle" type="radio" name="row-mode" id="rows-first" checked>')
        print('<input class="mode-toggle" type="radio" name="row-mode" id="rows-extended">')
    print('<section class="summary">')
    print('<div class="meta">')
    print(f'<span class="badge">{escape_html(format_name)}</span>')
    print(f'<span class="badge">{escape_html(human_size(path.stat().st_size))}</span>')
    print(f'<span class="badge">{format_rows(total_rows)} rows</span>')
    print(f'<span class="badge">{len(columns):,} variables</span>')
    if SHOW_METADATA and data_label:
        print(f'<span class="badge">{escape_html(data_label)}</span>')
    if SHOW_METADATA and time_stamp:
        print(f'<span class="badge">{escape_html(time_stamp)}</span>')
    if toggle_available:
        print('<span class="mode-controls" role="group" aria-label="Rows to display">')
        print(f'<label class="mode-button" for="rows-first">First {INITIAL_ROWS}</label>')
        second_label = f"All {preview_rows:,}" if all_rows_available else f"First {preview_rows:,}"
        print(f'<label class="mode-button" for="rows-extended">{second_label}</label>')
        print('</span>')
    elif all_rows_available:
        print(f'<span class="badge">showing all {preview_rows:,} rows</span>')
    else:
        print(f'<span class="badge">showing first {preview_rows:,} rows</span>')
    print('</div>')
    print('</section>')

    if SHOW_METADATA and value_labels:
        print('<details class="metadata">')
        print('<summary>Value labels</summary>')
        print('<div class="metadata-body">')
        for column, mapping in value_labels.items():
            if not mapping:
                continue
            rendered = ", ".join(
                f"{escape_html(str(key))} = {escape_html(str(label))}"
                for key, label in mapping.items()
            )
            print(f'<div class="vl-row"><code>{escape_html(column)}</code><span class="vl-map">{rendered}</span></div>')
        print('</div>')
        print('</details>')

    if SHOW_METADATA and extra_metadata:
        print('<details class="metadata">')
        print('<summary>Metadata</summary>')
        print('<div class="metadata-body">')
        for key, value in extra_metadata.items():
            print(f'<div class="vl-row"><code>{escape_html(key)}</code><span class="vl-map">{escape_html(value)}</span></div>')
        print('</div>')
        print('</details>')

    if not columns:
        print('<div class="table-wrap"><p>&lt;no variables&gt;</p></div></body></html>')
        return

    print('<div class="table-wrap"><table><thead><tr>')
    print('<th class="row-number">#</th>')
    for column, type_name in zip(columns, types):
        label = variable_labels.get(column, "") if SHOW_METADATA else ""
        label_html = ""
        if label:
            label_html = (
                f'<span class="label" title="{escape_html(label)}">'
                f'{escape_html(clip(label, MAX_HTML_CELL_WIDTH))}</span>'
            )
        print(
            '<th><span class="name">'
            + escape_html(column)
            + '</span><span class="type">'
            + escape_html(type_name)
            + '</span>'
            + label_html
            + '</th>'
        )
    print('</tr></thead><tbody>')

    for row_index in range(preview_rows):
        print(f'<tr><td class="row-number">{row_index + 1}</td>')
        for column_index in range(len(columns)):
            value = value_at(row_index, column_index)
            text = format_value(value)
            shown = clip(text, MAX_HTML_CELL_WIDTH)
            classes = ["numeric"] if numeric[column_index] else []
            if text in {"<null>", "<missing>", "<empty>"}:
                classes.append("missing")
            class_attr = f' class="{" ".join(classes)}"' if classes else ""

            label = value_label_for(value_labels.get(columns[column_index]), value) if SHOW_METADATA else None
            title_attr = f' title="{escape_html(label)}"' if label else ""
            print(
                f'<td{class_attr}><span class="cell"{title_attr}>'
                + escape_html(shown)
                + '</span></td>'
            )
        print('</tr>')
    print('</tbody></table></div></body></html>')


def preview_dta(path: Path) -> None:
    import pandas as pd

    version: int | None = None
    total_rows: int | None = None
    try:
        version, total_rows = read_dta_header(path)
    except Exception:
        version, total_rows = None, None

    with pd.io.stata.StataReader(
        path,
        convert_categoricals=False,
        convert_dates=True,
        preserve_dtypes=True,
    ) as reader:
        variable_labels = reader.variable_labels()
        value_labels = reader.value_labels()
        data_label = reader.data_label or ""
        time_stamp = reader.time_stamp or ""

        frame = reader.read(
            nrows=INITIAL_ROWS,
            convert_categoricals=False,
            convert_dates=True,
            preserve_dtypes=True,
        )

        # Fall back to pandas' private attributes if our header parse failed.
        if total_rows is None:
            raw_nobs = getattr(reader, "_nobs", None)
            total_rows = int(raw_nobs) if raw_nobs is not None else None
        if version is None:
            raw_version = getattr(reader, "_format_version", None)
            version = int(raw_version) if raw_version is not None else None

        if total_rows is None:
            full_preview_allowed = False
            target_rows = EXTENDED_ROWS
        else:
            full_preview_allowed = can_offer_all_rows(total_rows, len(frame.columns))
            target_rows = total_rows if full_preview_allowed else min(EXTENDED_ROWS, total_rows)

        if len(frame) < target_rows:
            try:
                remainder = reader.read(
                    nrows=target_rows - len(frame),
                    convert_categoricals=False,
                    convert_dates=True,
                    preserve_dtypes=True,
                )
                frame = pd.concat([frame, remainder], ignore_index=True)
            except StopIteration:
                pass  # file ended exactly at the boundary

        all_rows_available = total_rows is not None and len(frame) >= total_rows

    columns = [str(column) for column in frame.columns]
    types = [str(frame.dtypes.iloc[index]) for index in range(len(columns))]
    render_table(
        path,
        f"Stata DTA {version}" if version is not None else "Stata DTA",
        total_rows,
        columns,
        types,
        len(frame),
        lambda row, column: frame.iat[row, column],
        all_rows_available,
        variable_labels=variable_labels,
        value_labels=value_labels,
        data_label=data_label,
        time_stamp=time_stamp,
    )


def preview_parquet(path: Path) -> None:
    import pyarrow.parquet as pq

    parquet = pq.ParquetFile(path, memory_map=True, pre_buffer=False)
    columns = list(parquet.schema_arrow.names)
    types = [str(field.type) for field in parquet.schema_arrow]
    total_rows = int(parquet.metadata.num_rows)
    full_preview_allowed = can_offer_all_rows(total_rows, len(columns))
    row_limit = total_rows if full_preview_allowed else min(EXTENDED_ROWS, total_rows)
    all_rows_available = row_limit >= total_rows
    batches = parquet.iter_batches(
        batch_size=max(1, row_limit),
        columns=None,
        use_threads=False,
        use_pandas_metadata=False,
    )
    batch = next(batches, None)
    preview_rows = 0 if batch is None else batch.num_rows

    extra_metadata: dict[str, str] = {}
    raw_metadata = parquet.metadata.metadata
    if raw_metadata:
        for key, value in raw_metadata.items():
            if key == b"pandas":
                continue
            try:
                key_str = key.decode("utf-8") if isinstance(key, bytes) else str(key)
                value_str = value.decode("utf-8") if isinstance(value, bytes) else str(value)
                extra_metadata[key_str] = value_str
            except (UnicodeDecodeError, AttributeError):
                continue

    def value_at(row: int, column: int) -> Any:
        assert batch is not None
        return batch.column(column)[row].as_py()

    render_table(
        path,
        "Apache Parquet",
        total_rows,
        columns,
        types,
        preview_rows,
        value_at,
        all_rows_available,
        extra_metadata=extra_metadata,
    )


def preview_binary(path: Path) -> None:
    """Keep the shared binary UTI fallback bounded for unrelated files."""
    limit = 4096
    with path.open("rb") as handle:
        data = handle.read(limit)
    print(f"BINARY PREVIEW  {path.name}")
    print(f"File size: {human_size(path.stat().st_size)}")
    print(f"Showing: first {len(data):,} bytes (maximum {limit:,}); the full file is not loaded.")
    print()
    for offset in range(0, len(data), 16):
        chunk = data[offset : offset + 16]
        hex_part = " ".join(f"{byte:02x}" for byte in chunk).ljust(16 * 3 - 1)
        ascii_part = "".join(chr(byte) if 32 <= byte <= 126 else "." for byte in chunk)
        print(f"{offset:08x}  {hex_part}  |{ascii_part}|")


def main() -> int:
    global OUTPUT_HTML
    arguments = sys.argv[1:]
    if arguments[:1] == ["--html"]:
        OUTPUT_HTML = True
        arguments = arguments[1:]
    if len(arguments) != 1:
        print("DATA PREVIEW ERROR: expected one .dta or .parquet file path")
        return 0
    path = Path(arguments[0]).expanduser()
    try:
        if not path.is_file():
            raise FileNotFoundError(path)
        if path.suffix.lower() == ".dta":
            preview_dta(path)
        elif path.suffix.lower() == ".parquet":
            preview_parquet(path)
        else:
            preview_binary(path)
    except Exception as error:
        print(f"DATA PREVIEW ERROR: {type(error).__name__}: {error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
