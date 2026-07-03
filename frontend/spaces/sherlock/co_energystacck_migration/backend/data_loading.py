"""data_loading -- File I/O, mapping application, and data export.

This module handles all low-level interactions with raw data files:

* **Schema** -- ``load_schema_columns()`` reads the master column catalogue
  from ``data/schema.csv``.
* **Mapping** -- ``load_mapping()`` / ``apply_mapping()`` load and apply
  per-series column-rename mappings (JSON), including Date+Time -> Timestamp
  auto-combination.
* **Ingestion** -- ``load_and_concat_files_and_worksheets()`` reads one or more
  Excel worksheets for a series, stitches their time columns for continuity,
  and returns a single concatenated DataFrame.
* **Header detection** -- ``detect_header_and_data_row()`` auto-detects (or
  provides a preview for manual selection of) header and first-data rows.
* **Export** -- ``download_selected_data()`` writes filtered/selected columns
  to CSV, XLSX, or JSON.

No enrichment or business logic lives here; that is handled by
``data_enrichment`` and ``series_data_manager``.
"""

import logging
import pandas as pd
import os
import json
import csv
import time

from . import paths
from .data_visualization import AGG_SUFFIXES

logger = logging.getLogger(__name__)

# openpyxl options used when we only need a quick preview / sheet listing.
# ``read_only`` streams the XLSX (instead of loading every cell into memory)
# and ``data_only`` skips formula evaluation.  Together they typically make
# the parse 5-10x faster on multi-MB workbooks, which dominates the latency
# of the Series Management "Add file" flow.
_OPENPYXL_FAST_KW = {"read_only": True, "data_only": True}


def _normalize_path(p):
    """Return *p* with any Windows backslash separators converted to '/'.

    The pre-seeded ``config/series.json`` stores some paths using Windows
    separators (e.g. ``"data\\bronze\\foo.xlsx"``).  Python's open()/os.path
    accept forward slashes on every platform, so normalising here lets the
    same JSON work on both Windows and Linux App Service.

    This is a thin wrapper around :func:`src.backend.paths.normalize_separators`
    that exists for backwards-compatibility â€” older modules imported the
    private name directly.  Prefer ``paths.normalize_separators`` and
    ``paths.resolve_under_project_root`` in new code.
    """
    if not p or not isinstance(p, str):
        return p
    return p.replace("\\", "/")


def _read_csv_with_bom_fix(path):
    """Read a CSV file via ``csv.DictReader``, stripping any UTF-8 BOM from
    field names and row keys.

    Returns:
        list[dict]: One dict per row with clean keys.
    """
    rows = []
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames:
            reader.fieldnames = [fn.lstrip("\ufeff") for fn in reader.fieldnames]
        for row in reader:
            rows.append({k.lstrip("\ufeff"): v for k, v in row.items()})
    return rows


def load_schema_columns(schema_path):
    """
    Load schema columns from a CSV file and return a list of column names.
    """
    return _read_csv_with_bom_fix(schema_path)


def load_mapping(mapping_path):
    """Load the per-file mapping JSON if it exists, else return None."""
    if os.path.exists(mapping_path):
        with open(mapping_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _combine_date_time(date_series, time_series):
    """Combine ``Date`` + ``Time`` Series into a single ``Timestamp`` Series.

    The previous implementation cast both columns to strings, concatenated row
    by row, and re-parsed the result via ``pd.to_datetime``. That path is
    O(N) in Python over the row count and routinely takes 30-90s on 800k-row
    files on a small App Service plan, which caused gunicorn worker timeouts
    during materialize.

    This helper picks a vectorized path based on the input dtypes and only
    falls back to the legacy string-concat path when both vectorized branches
    yield all-NaT (which preserves the previous behavior on unusual inputs).
    """
    # Date -> datetime64 at day resolution
    if pd.api.types.is_datetime64_any_dtype(date_series):
        date_part = date_series.dt.normalize()
    else:
        date_part = pd.to_datetime(date_series, errors="coerce").dt.normalize()
    # Time -> timedelta (time-of-day)
    if pd.api.types.is_datetime64_any_dtype(time_series):
        # Excel times are usually returned as datetime64 anchored at the epoch
        # (e.g. 1899-12-30); subtracting the floor recovers the offset.
        time_part = time_series - time_series.dt.normalize()
    else:
        # ``pd.to_timedelta`` accepts "HH:MM:SS" strings and datetime.time
        # objects, so the object-dtype case lands here.
        time_part = pd.to_timedelta(time_series.astype(str), errors="coerce")
    combined = date_part + time_part
    # Defensive fallback: if the fast path collapsed to all-NaT, rerun via
    # the legacy string-concat path so existing weird datasets still load.
    if len(combined) > 0 and combined.isna().all():
        return pd.to_datetime(
            date_series.astype(str) + " " + time_series.astype(str),
            errors="coerce",
        )
    return combined


def apply_mapping(df, mapping):
    """Apply the mapping steps to the DataFrame only (no enrichment).
    mapping: list of dicts with 'schema_column' and 'file_column' keys.
    Renames columns by matching file_column name to DataFrame columns.
    Auto-detects Date + Time columns for datetime combining.
    """
    # Build rename map: file_column -> schema_column (skip empty file_column)
    rename_map = {}
    for entry in mapping:
        file_col = entry.get("file_column", "")
        schema_col = entry.get("schema_column", "").strip()
        if file_col and schema_col and file_col in df.columns:
            rename_map[file_col] = schema_col
    df = df.rename(columns=rename_map)
    # Auto-detect Date + Time columns and combine into Timestamp
    date_col = None
    time_col = None
    for col in df.columns:
        if col == "Date":
            date_col = col
        elif col == "Time":
            time_col = col
    if date_col and time_col:
        t_combine = time.perf_counter()
        df["Timestamp"] = _combine_date_time(df[date_col], df[time_col])
        logger.info(
            "apply_mapping: combined Date+Time -> Timestamp in %.2fs (%d rows)",
            time.perf_counter() - t_combine,
            len(df),
        )
    return df


def load_and_concat_files_and_worksheets(series_def, mapping, offset_callback=None):
    """
    Load and concatenate all files/worksheets for a series.

    Args:
        series_def: Series definition dict.
        mapping: List of mapping dicts.
        offset_callback: Optional callable(file_path, ws_name, first_time, prev_max_time, time_col) -> float or None.
                         Called when a time offset ambiguity cannot be auto-resolved.
                         If not provided, ambiguous offsets are skipped (no offset applied).

    Returns:
        tuple: (DataFrame, list of unresolved_offsets)
            unresolved_offsets: list of dicts with keys 'file', 'worksheet', 'first_time', 'prev_max_time', 'time_col'
            These are cases where auto-resolution failed and no offset_callback was provided.
    """
    files = series_def.get("files", [])
    logger.info("Number of files in series: %d", len(files))
    dfs = []
    unresolved_offsets = []
    time_col = None
    # Find mapped file_column name for 'Test time' from new mapping format (list of dicts)
    if mapping and isinstance(mapping, list):
        for entry in mapping:
            if entry.get("schema_column", "").lower() == "elapsed time":
                file_col = entry.get("file_column", "").strip()
                if file_col:
                    time_col = file_col
                break
    # Fallback: try to find 'Elapsed time' in columns
    if not time_col:
        time_col = "Elapsed time"

    prev_max_time = None
    for file_idx, file_entry in enumerate(files):
        if not isinstance(file_entry, dict):
            raise ValueError(
                f"File entry must be a dict with at least a 'path' key, got: {file_entry}"
            )
        # ``resolve_under_project_root`` normalises any backslashes and
        # joins relative paths onto PROJECT_ROOT so the same series.json
        # entry works on Windows and Linux App Service alike.
        file_path = paths.resolve_under_project_root(file_entry.get("path"))
        if not file_path or not os.path.isfile(file_path):
            logger.warning("File not found: %s", file_path)
            continue
        worksheets = file_entry.get("worksheets", [])
        logger.info(
            "File %d/%d: %s, worksheets: %d",
            file_idx + 1,
            len(files),
            file_path,
            len(worksheets),
        )
        for ws_idx, ws_entry in enumerate(worksheets):
            ws_name = ws_entry.get("name")
            header_row = ws_entry.get("header_row")
            first_data_row = ws_entry.get("first_data_row")
            try:
                skiprows = (
                    list(range(header_row + 1, first_data_row))
                    if (header_row is not None and first_data_row is not None)
                    else None
                )
                df = pd.read_excel(
                    file_path,
                    sheet_name=ws_name,
                    header=header_row if header_row is not None else 1,
                    skiprows=skiprows,
                    engine="openpyxl",
                )
                logger.info(
                    "Worksheet %d/%d: %s, shape: %s, loaded rows: %d",
                    ws_idx + 1,
                    len(worksheets),
                    ws_name,
                    df.shape,
                    len(df),
                )
                # Stitch time column for continuity
                if time_col in df.columns:
                    df[time_col] = pd.to_numeric(df[time_col], errors="coerce")
                    first_time = df[time_col].iloc[0]
                    max_time = df[time_col].max()
                    if prev_max_time is not None:
                        # If first_time is within Â±1 of prev_max_time, append as-is
                        if abs(first_time - prev_max_time) <= 1:
                            pass
                        # If first_time is 0 or 1, offset by prev_max_time
                        elif first_time in [0, 1]:
                            df[time_col] = df[time_col] + prev_max_time
                        else:
                            # Ambiguous time offset â€” delegate to callback or record as unresolved
                            if offset_callback is not None:
                                offset = offset_callback(
                                    file_path,
                                    ws_name,
                                    first_time,
                                    prev_max_time,
                                    time_col,
                                )
                                if offset is not None:
                                    df[time_col] = df[time_col] + offset
                            else:
                                unresolved_offsets.append(
                                    {
                                        "file": file_path,
                                        "worksheet": ws_name,
                                        "first_time": first_time,
                                        "prev_max_time": prev_max_time,
                                        "time_col": time_col,
                                    }
                                )
                    prev_max_time = df[time_col].max()
                else:
                    logger.warning(
                        "'%s' column not found in worksheet %s.", time_col, ws_name
                    )
                dfs.append(df)
            except Exception as e:
                logger.error(
                    "Failed to load %s [%s] (header_row=%s, first_data_row=%s): %s",
                    file_path,
                    ws_name,
                    header_row,
                    first_data_row,
                    e,
                )
    if dfs:
        logger.info("Concatenating %d DataFrames.", len(dfs))
        return pd.concat(dfs, ignore_index=True), unresolved_offsets
    else:
        logger.warning("No DataFrames loaded.")
        return pd.DataFrame(), unresolved_offsets


# Robust header and data row detection using schema
def detect_header_and_data_row(
    filepath,
    worksheet=None,
    preview_rows=10,
    preview_cols=5,
    float_threshold=0.8,
    match_threshold=0.6,
):
    """
    Attempt to auto-detect the header row and first data row in a file.

    Returns:
        tuple: (header_row_idx, first_data_row_idx, preview_df)
            - If auto-detection succeeds: (int, int, None)
            - If auto-detection fails: (None, None, DataFrame) where preview_df
              contains the first preview_rows of the file for manual selection by the UI.
    """
    # Get all possible column names/aliases from schema (read-only,
    # always lives in the deploy package â€” see ``paths`` module).
    schema_columns = load_schema_columns(paths.SCHEMA_PATH)

    schema_names = set()
    for col in schema_columns:
        name = col.get("name", "").strip()
        if name:
            schema_names.add(name.lower())
        aliases = col.get("aliases", "")
        if aliases:
            for alias in aliases.split(","):
                schema_names.add(alias.strip().lower())

    # Read preview rows.  ``engine_kwargs`` forwards ``read_only=True`` +
    # ``data_only=True`` to openpyxl which streams the file instead of
    # materialising every cell in memory â€“ critical for the 30-80 MB
    # measurement workbooks uploaded via the Series Management tab.
    t0 = time.perf_counter()
    if filepath.lower().endswith(".xlsx"):
        if worksheet is None:
            with pd.ExcelFile(
                filepath, engine="openpyxl", engine_kwargs=_OPENPYXL_FAST_KW
            ) as xls:
                first_sheet = xls.sheet_names[0]
            df = pd.read_excel(
                filepath,
                sheet_name=first_sheet,
                header=None,
                nrows=preview_rows,
                engine="openpyxl",
                engine_kwargs=_OPENPYXL_FAST_KW,
            )
        else:
            df = pd.read_excel(
                filepath,
                sheet_name=worksheet,
                header=None,
                nrows=preview_rows,
                engine="openpyxl",
                engine_kwargs=_OPENPYXL_FAST_KW,
            )
    else:
        df = pd.read_csv(filepath, header=None, nrows=preview_rows)
    logger.info(
        "detect_header_and_data_row: read preview (%d rows) from '%s' ws=%r in %.2fs",
        len(df),
        os.path.basename(filepath),
        worksheet,
        time.perf_counter() - t0,
    )

    # Header row detection: row with most matches to schema names/aliases
    best_match = 0
    header_row = None
    best_row_len = 0
    for i, row in df.iterrows():
        match_count = 0
        row_len = len(row)
        for cell in row:
            if pd.isnull(cell):
                continue
            cell_str = str(cell).strip().lower()
            for name in schema_names:
                if name in cell_str or cell_str in name:
                    match_count += 1
                    break
        threshold = int(row_len * match_threshold)
        if match_count > best_match:
            best_match = match_count
            header_row = i
            best_row_len = row_len
    # Accept if at least match_threshold of columns in the row matched
    if header_row is not None and best_match >= int(best_row_len * match_threshold):
        pass
    else:
        header_row = None

    # Data row detection: after header, first row with >= float_threshold floats (excluding first 2 cols)
    first_data_row = None
    if header_row is not None:
        for i in range(header_row + 1, len(df)):
            row = df.iloc[i]
            float_cols = row.drop([0, 1]) if len(row) > 2 else row
            float_vals = pd.to_numeric(float_cols, errors="coerce")
            num_floats = (float_vals.notnull()).sum()
            num_total = len(float_vals)
            float_ratio = num_floats / num_total if num_total else 0
            if num_total > 0 and float_ratio >= float_threshold:
                first_data_row = i
                break

    # If detection failed, return preview so the UI can handle manual selection
    if header_row is None or first_data_row is None or header_row >= first_data_row:
        return None, None, df

    return header_row, first_data_row, None


def download_selected_data(df, columns, time_column, output_path, time_slicer=None):
    """
    Export selected columns from a DataFrame to a file.

    Filters the DataFrame to the requested columns (always including the time column),
    optionally applies a time-range filter, and writes the result to output_path.

    Args:
        df:          Source DataFrame (silver / aggregated data).
        columns:     List of column names to export. The time_column is always
                     included even if not in this list.
        time_column: Name of the time column (used for ordering and optional filtering).
        output_path: Destination file path. Format is inferred from extension
                     (.csv, .xlsx, .json supported).
        time_slicer: Optional (min_time, max_time) tuple. When provided only rows
                     where min_time <= time_column <= max_time are exported.

    Returns:
        str: The absolute path of the written file.

    Raises:
        ValueError: If the time_column is missing from the DataFrame or no data
                    remains after filtering.
    """
    # Ensure the time column is present
    if time_column not in df.columns:
        raise ValueError(f"Time column '{time_column}' not found in the data.")

    # Build final column list: time column first, then the rest (skip missing).
    # For aggregated data the GUI passes base names (e.g. "Stack Voltage")
    # but the DataFrame contains suffixed columns (_min, _max, _mean).
    # Expand base names to their aggregated variants when necessary.
    export_cols = [time_column]
    for col in columns:
        if col == time_column:
            continue
        if col in df.columns:
            export_cols.append(col)
        else:
            # Try aggregated variants
            for suffix in AGG_SUFFIXES:
                agg_col = col + suffix
                if agg_col in df.columns:
                    export_cols.append(agg_col)

    df_out = df[export_cols].copy()

    # Add Test time (hours) column derived from Elapsed time (seconds)
    if "Elapsed time" in df_out.columns:
        idx = df_out.columns.get_loc("Elapsed time")
        df_out.insert(idx + 1, "Test time", df_out["Elapsed time"] / 3600.0)

    # Apply optional time-range filter
    if time_slicer is not None:
        min_time, max_time = time_slicer
        df_out = df_out[
            (df_out[time_column] >= min_time) & (df_out[time_column] <= max_time)
        ]

    if df_out.empty:
        raise ValueError("No data remaining after applying filters.")

    # Ensure output directory exists
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    # Write to file based on extension
    ext = os.path.splitext(output_path)[1].lower()
    if ext == ".xlsx":
        df_out.to_excel(output_path, index=False)
    elif ext == ".json":
        df_out.to_json(output_path, orient="records", indent=2)
    else:
        # Default to CSV
        df_out.to_csv(output_path, index=False)

    return os.path.abspath(output_path)

