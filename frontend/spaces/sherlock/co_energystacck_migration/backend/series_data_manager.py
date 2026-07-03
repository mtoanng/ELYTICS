"""series_data_manager -- Central backend for series lifecycle management.

This module is the **single source of truth** for series definitions and the
orchestrator of the entire medallion data pipeline::

    Bronze (raw .xlsx in data/bronze/)
      -> Silver (enriched .csv in data/silver/)
        -> Cache (feather in cache/)

Key responsibilities of the ``SeriesDataManager`` class:

* **Series CRUD** -- create / save / delete series definitions stored in
    ``config/series.json``.  Structure schema is driven by
    ``config/series_structure.json``.
* **File management** -- ``import_file_to_bronze()``,
  ``overwrite_file_in_bronze()``.
* **Materialization** -- ``materialize_silver_layer()`` runs the full pipeline:
  load -> map -> clean -> enrich -> write silver CSV.  Also auto-purges stale
  aggregations.
* **Aggregation** -- ``aggregate_and_store_series()`` creates time-binned
  aggregations registered under the parent's ``aggregations`` list.
  ``delete_aggregation()`` / ``delete_all_aggregations()`` clean up.
* **Mapping CRUD** -- ``define_mapping()``, ``save_mapping()``,
  ``delete_mapping()`` manage per-series column mappings in
  ``data/bronze/{name}_mapping.json``.
* **Loading** -- ``load_silver_data()`` reads silver CSVs (with feather
  caching) into ``loaded_series``.
* **Validation** -- ``validate_for_materialization()`` pre-flight checks.

Module-level utilities:

* ``parse_time_slicer(text)`` -- converts ``"0, 10"`` (hours) to
  ``(0, 36000)`` (seconds).  Used by GUI time-slicer inputs.
* ``classify_columns(df)`` -- splits DataFrame columns into x-axis / y-axis
  candidates.  Used by GUI axis selectors.
"""

import os
import json
import csv
import logging
import re
import shutil
import time
import pandas as pd
from . import paths
from .data_loading import (
    load_mapping,
    load_schema_columns,
    apply_mapping,
    load_and_concat_files_and_worksheets,
)
from .data_enrichment import DataEnrichment, load_units_from_schema
from .data_visualization import get_base_parameter_names

logger = logging.getLogger(__name__)

DEFAULT_SERIES_DEF_PATH = paths.SERIES_DEF_PATH


def parse_time_slicer(text):
    """Parse a time-slicer string into (min_seconds, max_seconds).

    Accepts formats like ``"0, 10"``, ``"[0, 10]"``, or ``"0,10"`` where
    values are in **hours**.  Returns a ``(min_s, max_s)`` tuple in seconds,
    or ``None`` if *text* is empty.

    Raises:
        ValueError: on malformed input or min >= max.
    """
    if not text or not text.strip():
        return None
    cleaned = text.replace("[", "").replace("]", "").strip()
    parts = [p.strip() for p in cleaned.split(",")]
    if len(parts) != 2:
        raise ValueError("Expected two comma-separated numbers (min, max).")
    min_h, max_h = float(parts[0]), float(parts[1])
    if min_h >= max_h:
        raise ValueError("Minimum must be less than maximum.")
    return (min_h * 3600, max_h * 3600)


def classify_columns(df):
    """Classify DataFrame columns into x-axis and y-axis candidates.

    Returns:
        tuple: (x_axis_bases, y_axis_bases) â€” both sorted lists of base
        parameter names (aggregation suffixes stripped).  ``"Elapsed time"``
        is **not** included in either list (callers prepend it to x-axis
        themselves).
    """
    if df is None or df.empty:
        return [], []
    x_cols = []
    y_cols = []
    for col in df.columns:
        if col == "Elapsed time":
            continue
        if not (
            pd.api.types.is_float_dtype(df[col])
            or pd.api.types.is_numeric_dtype(df[col])
        ):
            continue
        low = col.lower()
        if "date" in low or "unnamed" in low:
            continue
        if "time" in low:
            continue
        x_cols.append(col)
        y_cols.append(col)
    return get_base_parameter_names(x_cols), get_base_parameter_names(y_cols)


class SeriesDataManager:
    def __init__(
        self,
        series_def_path: str = DEFAULT_SERIES_DEF_PATH,
        cache_dir: str | None = None,
    ):
        """Initialise the manager.

        Args:
            series_def_path: Path to the ``config/series.json`` file that
                stores all series definitions. Defaults to
                ``paths.SERIES_DEF_PATH``.
            cache_dir: Directory for feather-format DataFrame caches.
                Defaults to ``paths.CACHE_DIR``.
        """
        self.series_def_path = series_def_path
        self.cache_dir = cache_dir if cache_dir is not None else paths.CACHE_DIR
        self.loaded_series = {}  # {series_name: DataFrame}
        # ``_series_defs`` + ``_series_defs_mtime`` back the public
        # ``series_defs`` property below. We initialise via the private
        # attributes so the property's mtime check does not run before the
        # first load has completed.
        self._series_defs_mtime: float | None = None
        self._series_defs: dict = self._load_series_defs()
        self._update_series_defs_mtime()
        self.structure = self._load_structure()
        self.stack_definitions = self._load_stack_definitions()
        self.units = load_units_from_schema()

    # ------------------------------------------------------------------ #
    # series_defs: multi-worker-safe view backed by config/series.json   #
    # ------------------------------------------------------------------ #
    # The Dash app is deployed under gunicorn with multiple worker
    # processes (App Service / Dockerfile both default to >1). Each worker
    # holds its own ``SeriesDataManager`` instance, so a write done by one
    # worker is invisible to the others unless they re-read the file.
    # This property turns every access into an mtime check against
    # ``config/series.json`` and reloads when the file has advanced since
    # we last looked. The stat() is sub-millisecond on a local SSD or the
    # Azure App Service file share, well below the latency of the
    # upload/parse paths that dominate this tab.
    @property
    def series_defs(self) -> dict:
        """Always-fresh series-definitions dict (reloads if the JSON changed)."""
        self._refresh_if_stale()
        return self._series_defs

    @series_defs.setter
    def series_defs(self, value: dict) -> None:
        self._series_defs = value

    def _refresh_if_stale(self) -> None:
        """Reload ``_series_defs`` from disk if the JSON file has advanced."""
        if not os.path.isfile(self.series_def_path):
            return
        try:
            mtime = os.path.getmtime(self.series_def_path)
        except OSError:
            return
        if self._series_defs_mtime is None or mtime > self._series_defs_mtime:
            self._series_defs = self._load_series_defs()
            self._series_defs_mtime = mtime

    def _update_series_defs_mtime(self) -> None:
        """Snapshot the current mtime of ``config/series.json`` (if it exists)."""
        try:
            self._series_defs_mtime = os.path.getmtime(self.series_def_path)
        except OSError:
            self._series_defs_mtime = None

    def _load_series_defs(self):
        """Read and return the series definitions dict from the JSON file on disk.

        Includes a back-compat shim for legacy ``config/series.json`` files
        authored on Windows: any ``"path"`` or ``"mapping"`` value that
        contains a backslash is rewritten in-memory to use forward slashes,
        and the cleaned dict is then written back to disk once. The
        rewritten value works on every OS Python supports; on Linux the
        original backslashes are literal filename characters and break
        ``os.path.exists`` (the user-reported "Detection error: [Errno 2]
        No such file or directory" symptom on App Service).
        """
        if not os.path.isfile(self.series_def_path):
            logger.warning(
                "Series definitions file not found: %s â€“ starting empty",
                self.series_def_path,
            )
            return {}
        with open(self.series_def_path, "r", encoding="utf-8") as f:
            defs = json.load(f)
        rewrote = self._migrate_path_separators(defs)
        if rewrote:
            logger.info(
                "Normalised %d legacy Windows path(s) in series.json", rewrote
            )
            self._save_defs_dict_to_disk(defs)
        return defs

    @staticmethod
    def _migrate_path_separators(defs: dict) -> int:
        """Rewrite every backslash-bearing path value in *defs* in-place.

        Returns the number of values rewritten.
        """
        count = 0
        if not isinstance(defs, dict):
            return 0
        for sdef in defs.values():
            if not isinstance(sdef, dict):
                continue
            for entry in sdef.get("files", []) or []:
                if not isinstance(entry, dict):
                    continue
                p = entry.get("path")
                if isinstance(p, str) and "\\" in p:
                    entry["path"] = p.replace("\\", "/")
                    count += 1
            mapping = sdef.get("mapping")
            if isinstance(mapping, str) and "\\" in mapping:
                sdef["mapping"] = mapping.replace("\\", "/")
                count += 1
        return count

    def _save_defs_dict_to_disk(self, defs: dict) -> None:
        """Write *defs* to ``self.series_def_path`` atomically.

        Used by both the live save path and the one-time migration save in
        ``_load_series_defs``; the latter cannot call
        ``_save_series_defs_to_disk`` because ``_series_defs`` is not yet
        bound to ``self``.
        """
        os.makedirs(os.path.dirname(self.series_def_path) or ".", exist_ok=True)
        tmp = self.series_def_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(defs, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.series_def_path)

    def _resolve_config_sibling(self, filename: str) -> str | None:
        """Find a config JSON next to ``series_def_path`` or in the deploy dir.

        Preference order:

        1. ``<dirname(series_def_path)>/filename`` â€” the writable config dir
           in production; falls through if missing so user-supplied test
           paths (where ``series_def_path`` lives in ``tmp_path``) keep
           working as before.
        2. ``READONLY_CONFIG_DIR/filename`` â€” the read-only deploy package
           copy, which always ships with the app.
        """
        sibling = os.path.join(
            os.path.dirname(self.series_def_path) or ".", filename
        )
        if os.path.isfile(sibling):
            return sibling
        readonly = os.path.join(paths.READONLY_CONFIG_DIR, filename)
        if os.path.isfile(readonly):
            return readonly
        return None

    def _load_structure(self):
        """Load the series structure definition from config/series_structure.json."""
        path = self._resolve_config_sibling("series_structure.json")
        if path:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _load_stack_definitions(self):
        """Load stack type definitions from config/stack_definitions.json."""
        path = self._resolve_config_sibling("stack_definitions.json")
        if path:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    @staticmethod
    def _parse_agg_name(name):
        """Decompose an aggregated series name into (parent, interval_minutes).

        Returns (parent, interval) if *name* matches the pattern
        ``{parent}_agg{N}min``, otherwise (name, None).
        """
        m = re.match(r"^(.+)_agg(\d+)min$", name)
        if m:
            return m.group(1), int(m.group(2))
        return name, None

    def get_all_selectable_series(self):
        """Return a list of all series names that can be selected for loading.

        This includes raw (parent) series **and** synthesised aggregated names
        derived from each parent's ``aggregations`` list.  Only names whose
        silver CSV actually exists on disk are included.
        """
        # ``self.series_defs`` is a property: each access runs an mtime check
        # against config/series.json and reloads if a sibling worker wrote
        # newer data, so an explicit ``_load_series_defs`` call is no longer
        # required here.
        result = []
        for name, sdef in self.series_defs.items():
            # Parent series
            if os.path.exists(self._get_silver_path(name)):
                result.append(name)
            # Synthesised aggregated variants
            for interval in sdef.get("aggregations", []):
                agg_name = f"{name}_agg{interval}min"
                if os.path.exists(self._get_silver_path(agg_name)):
                    result.append(agg_name)
        return result

    def get_active_area(self, series_name):
        """Resolve active area (cm2) for a series from its stack_type.

        For aggregated series the stack_type is resolved through the parent.
        """
        parent, _ = self._parse_agg_name(series_name)
        series_def = self.series_defs.get(parent, {})
        stack_type = series_def.get("stack_type", "")
        stack_def = self.stack_definitions.get(stack_type, {})
        return stack_def.get("active_area_cm2", 88.0)

    def import_file_to_bronze(self, source_path):
        """Copy an external file into ``BRONZE_DIR`` and return the stored path.

        If the file is already inside ``BRONZE_DIR`` no copy is made.
        If a file with the same name already exists in bronze, the method
        returns ``(stored_path, 'exists')`` so the caller can decide
        whether to overwrite.

        Args:
            source_path: Absolute or relative path to the source file.
                Backslashes are accepted and normalised.

        Returns:
            tuple: (stored_path, status)
                stored_path: Forward-slash path suitable for putting back
                    into ``series.json`` (relative to PROJECT_ROOT when
                    BRONZE_DIR is under PROJECT_ROOT, absolute otherwise).
                status: 'copied', 'already_in_bronze', or 'exists'.
        """
        bronze_dir = paths.BRONZE_DIR
        os.makedirs(bronze_dir, exist_ok=True)
        abs_source = os.path.abspath(paths.normalize_separators(source_path))
        abs_bronze = os.path.abspath(bronze_dir)
        # Check if the file is already inside the bronze folder
        if abs_source == abs_bronze or abs_source.startswith(abs_bronze + os.sep):
            return paths.to_storage_path(abs_source), "already_in_bronze"
        filename = os.path.basename(abs_source)
        dest_path = os.path.join(bronze_dir, filename)
        if os.path.exists(dest_path):
            # Same name already in bronze â€” let caller decide
            return paths.to_storage_path(dest_path), "exists"
        shutil.copy2(abs_source, dest_path)
        stored = paths.to_storage_path(dest_path)
        logger.info("Imported '%s' to bronze: %s", filename, stored)
        return stored, "copied"

    def overwrite_file_in_bronze(self, source_path):
        """Force-copy a file into ``BRONZE_DIR``, overwriting any existing file."""
        bronze_dir = paths.BRONZE_DIR
        os.makedirs(bronze_dir, exist_ok=True)
        abs_source = os.path.abspath(paths.normalize_separators(source_path))
        filename = os.path.basename(abs_source)
        dest_path = os.path.join(bronze_dir, filename)
        shutil.copy2(abs_source, dest_path)
        stored = paths.to_storage_path(dest_path)
        logger.info("Overwritten '%s' in bronze: %s", filename, stored)
        return stored

    def _get_silver_path(self, series_name):
        """Return the expected path of the silver CSV for *series_name*."""
        return os.path.join(paths.SILVER_DIR, f"{series_name}.csv")

    def _get_silver_cache_path(self, series_name):
        """Return the expected path of the feather cache for *series_name*."""
        return os.path.join(self.cache_dir, f"{series_name}_silver.feather")

    def _get_mapping_file_for_series(self, series_name):
        """
        Returns the mapping file path for a given series, if it exists.
        Searches in ``BRONZE_DIR`` for ``{series_name}_mapping.json``.
        """
        bronze_dir = paths.BRONZE_DIR
        # Try common mapping file patterns
        candidates = [
            os.path.join(bronze_dir, f"{series_name}_mapping.json"),
            os.path.join(bronze_dir, f"{series_name.lower()}_mapping.json"),
        ]
        for fname in candidates:
            if os.path.exists(fname):
                return fname
        # Fallback: look for any matching mapping in bronze dir
        if os.path.isdir(bronze_dir):
            for f in os.listdir(bronze_dir):
                if f.endswith("_mapping.json") and series_name.lower() in f.lower():
                    return os.path.join(bronze_dir, f)
        return None

    def get_all_series_definitions(self):
        """Reload and return the full series definitions dict from disk."""
        return self._load_series_defs()

    def load_silver_data(self, series_name, force_reload=False):
        """
        Load enriched (silver) data for a series from CSV or cache.
        If force_reload is True, reload from CSV and update cache.
        """
        cache_path = self._get_silver_cache_path(series_name)
        silver_path = self._get_silver_path(series_name)
        if not force_reload and os.path.exists(cache_path):
            df = pd.read_feather(cache_path)
            return df
        if os.path.exists(silver_path):
            df = pd.read_csv(silver_path)
            os.makedirs(self.cache_dir, exist_ok=True)
            df.reset_index(drop=True).to_feather(cache_path)
            return df
        logger.debug("Silver data for series '%s' not found.", series_name)
        return pd.DataFrame()

    def materialize_silver_layer(self, series_name):
        """
        Loads and enriches data for the given series using its mapping, then saves as CSV in the silver layer.
        Bronze: xlsx files in ``paths.BRONZE_DIR``.
        Silver: enriched CSV in ``paths.SILVER_DIR``/{series_name}.csv.
        """
        t_start = time.perf_counter()
        # Invalidate cache so stale feather files are never loaded afterwards
        cache_path = self._get_silver_cache_path(series_name)
        if os.path.exists(cache_path):
            os.remove(cache_path)
            logger.debug("Cache removed: %s", cache_path)
        silver_dir = paths.SILVER_DIR
        os.makedirs(silver_dir, exist_ok=True)
        series_def = self.series_defs.get(series_name)
        if not series_def:
            logger.warning("No series definition found for '%s'.", series_name)
            return False
        mapping_file = paths.resolve_under_project_root(series_def.get("mapping"))
        if not mapping_file or not os.path.exists(mapping_file):
            mapping_file = self._get_mapping_file_for_series(series_name)
        if not mapping_file or not os.path.exists(mapping_file):
            logger.warning(
                "No mapping file found for series '%s'. Skipping silver materialization.",
                series_name,
            )
            return False
        mapping = load_mapping(mapping_file)
        t_load = time.perf_counter()
        df, unresolved_offsets = load_and_concat_files_and_worksheets(
            series_def, mapping
        )
        t_loaded = time.perf_counter()
        if unresolved_offsets:
            logger.warning(
                "%d unresolved time offset(s) during materialization of '%s'.",
                len(unresolved_offsets),
                series_name,
            )
            for uo in unresolved_offsets:
                logger.warning(
                    "  - File: %s, Worksheet: %s, first_time=%s, prev_max=%s",
                    uo["file"],
                    uo["worksheet"],
                    uo["first_time"],
                    uo["prev_max_time"],
                )
        if df is None or df.empty:
            logger.warning("No data loaded for series '%s'.", series_name)
            return False
        rows = len(df)
        logger.info(
            "Materialize '%s': load_files %.1fs (%d rows).",
            series_name,
            t_loaded - t_load,
            rows,
        )
        df_mapped = apply_mapping(df, mapping)
        t_mapped = time.perf_counter()
        logger.info(
            "Materialize '%s': apply_mapping %.1fs.",
            series_name,
            t_mapped - t_loaded,
        )

        active_area = self.get_active_area(series_name)
        enricher = DataEnrichment(active_area=active_area)
        df_clean = DataEnrichment.clean_data(df_mapped)
        t_clean = time.perf_counter()
        logger.info(
            "Materialize '%s': clean_data %.1fs.",
            series_name,
            t_clean - t_mapped,
        )
        df_enriched = enricher.enrich(df_clean, mapping, units=self.units)
        t_enriched = time.perf_counter()
        logger.info(
            "Materialize '%s': enrich %.1fs (%d cols).",
            series_name,
            t_enriched - t_clean,
            len(df_enriched.columns),
        )
        silver_path = self._get_silver_path(series_name)
        df_enriched.to_csv(silver_path, index=False)
        t_written = time.perf_counter()
        logger.info(
            "Materialize '%s': write_csv %.1fs -> %s",
            series_name,
            t_written - t_enriched,
            silver_path,
        )
        logger.info(
            "Silver layer materialized for series '%s' in %.1fs total (%d rows).",
            series_name,
            t_written - t_start,
            rows,
        )
        # Auto-delete all aggregations â€” they are derived from the old silver data
        removed = self.delete_all_aggregations(series_name)
        if removed:
            logger.info(
                "Purged %d stale aggregation(s) for '%s'.", removed, series_name
            )
        return True

    def unload_series(self, series_name):
        """Remove a series DataFrame from memory."""
        if series_name in self.loaded_series:
            del self.loaded_series[series_name]

    def get_loaded_series(self):
        """Return a list of currently loaded series names."""
        return list(self.loaded_series.keys())

    def aggregate_and_store_series(self, series_name, interval_minutes=15):
        """Aggregate silver data and register the interval under the parent series.

        The aggregated CSV is stored conventionally as
        ``data/silver/{series_name}_agg{N}min.csv``.  Instead of creating a
        standalone series-definition clone, the *interval_minutes* value is
        added to the parent's ``aggregations`` list (if not already present).
        """
        new_series_name = f"{series_name}_agg{interval_minutes}min"
        # Invalidate cache
        agg_cache_path = self._get_silver_cache_path(new_series_name)
        if os.path.exists(agg_cache_path):
            os.remove(agg_cache_path)
            logger.debug("Cache removed: %s", agg_cache_path)
        # Load silver data (force reload to pick up any recent re-materialization)
        df = self.load_silver_data(series_name, force_reload=True)
        if df is None or df.empty:
            logger.warning("No silver data found for series '%s'.", series_name)
            return False
        # Aggregate
        agg_df = DataEnrichment.aggregate_timeseries(
            df, interval_minutes=interval_minutes
        )
        # Store aggregated CSV in silver layer
        silver_dir = paths.SILVER_DIR
        os.makedirs(silver_dir, exist_ok=True)
        agg_path = self._get_silver_path(new_series_name)
        agg_df.to_csv(agg_path, index=False)
        # Update parent's aggregations list (no standalone entry)
        parent_def = self.series_defs.get(series_name)
        if not parent_def:
            logger.warning("Parent series definition not found for '%s'.", series_name)
            return False
        agg_list = parent_def.setdefault("aggregations", [])
        if interval_minutes not in agg_list:
            agg_list.append(interval_minutes)
            agg_list.sort()
        try:
            self._save_series_defs_to_disk()
        except Exception as e:
            logger.error("Failed to update series definitions: %s", e)
            return False
        logger.info("Aggregated series '%s' stored at %s.", new_series_name, agg_path)
        return True

    def delete_aggregation(self, series_name, interval_minutes):
        """Remove a single aggregation interval from a parent series.

        Deletes the corresponding silver CSV and cache feather file, removes
        the interval from the parent's ``aggregations`` list, and persists.

        Returns:
            True if the interval was found and removed, False otherwise.
        """
        series_def = self.series_defs.get(series_name)
        if not series_def:
            return False
        agg_list = series_def.get("aggregations", [])
        if interval_minutes not in agg_list:
            return False
        agg_name = f"{series_name}_agg{interval_minutes}min"
        # Remove silver CSV and cache
        for path in [
            self._get_silver_path(agg_name),
            self._get_silver_cache_path(agg_name),
        ]:
            if os.path.exists(path):
                os.remove(path)
                logger.debug("Deleted: %s", path)
        # Also unload from memory if loaded
        self.unload_series(agg_name)
        # Update parent's list
        agg_list.remove(interval_minutes)
        self._save_series_defs_to_disk()
        return True

    def delete_all_aggregations(self, series_name):
        """Remove all aggregation intervals and their files for a parent series.

        Returns:
            int: number of aggregation intervals removed.
        """
        series_def = self.series_defs.get(series_name)
        if not series_def:
            return 0
        agg_list = list(series_def.get("aggregations", []))  # copy
        count = 0
        for interval in agg_list:
            agg_name = f"{series_name}_agg{interval}min"
            for path in [
                self._get_silver_path(agg_name),
                self._get_silver_cache_path(agg_name),
            ]:
                if os.path.exists(path):
                    os.remove(path)
                    logger.debug("Deleted: %s", path)
            self.unload_series(agg_name)
            count += 1
        series_def["aggregations"] = []
        self._save_series_defs_to_disk()
        return count

    # --- Series CRUD ---

    def _save_series_defs_to_disk(self):
        """Persist the current series_defs dict to the JSON file atomically.

        Uses ``_series_defs`` directly to avoid a recursive refresh through
        the property getter, then snapshots the new on-disk mtime so this
        instance does not immediately re-read what it just wrote.

        The write is done through a sibling ``.tmp`` file plus ``os.replace``
        so a crash mid-write never leaves the on-disk JSON in a corrupted /
        partially-written state visible to other workers.
        """
        self._save_defs_dict_to_disk(self._series_defs)
        self._update_series_defs_mtime()

    def create_series(self, series_name):
        """
        Create a new empty series entry.

        Args:
            series_name: Name for the new series.

        Returns:
            True if created, False if name already exists or is empty.
        """
        if not series_name or series_name in self.series_defs:
            return False
        self.series_defs[series_name] = {}
        self._save_series_defs_to_disk()
        return True

    def save_series(self, series_name, fields=None, options=None, files=None):
        """
        Update and persist a series definition.

        Args:
            series_name: The series key to update.
            fields: dict of top-level field values (excluding 'files' and 'options').
            options: dict of option field values.
            files: list of file dicts (with worksheets, header_row, etc.).
                   If None, existing files are kept unchanged.

        Returns:
            True on success, False if series not found.
        """
        if series_name not in self.series_defs:
            return False
        series = self.series_defs[series_name]
        # Update top-level fields
        if fields:
            for field, value in fields.items():
                if field not in ("files", "options"):
                    series[field] = value
        # Update options
        if options is not None:
            series["options"] = options
        # Update files if provided
        if files is not None:
            series["files"] = files
        self.series_defs[series_name] = series
        self._save_series_defs_to_disk()
        return True

    def get_associated_files(self, series_name):
        """Return a list of associated file paths that exist on disk.

        For parent series, this also includes silver/cache files for every
        registered aggregation interval.
        """
        parent, interval = self._parse_agg_name(series_name)
        if interval is not None:
            # Aggregated variant â€” only silver + cache
            silver_file = self._get_silver_path(series_name)
            cache_file = self._get_silver_cache_path(series_name)
            return [f for f in [silver_file, cache_file] if os.path.exists(f)]
        # Parent series
        mapping_file = os.path.join(
            paths.BRONZE_DIR, f"{series_name}_mapping.json"
        )
        silver_file = self._get_silver_path(series_name)
        cache_file = self._get_silver_cache_path(series_name)
        files_to_check = [mapping_file, silver_file, cache_file]
        for iv in self.series_defs.get(series_name, {}).get("aggregations", []):
            agg_name = f"{series_name}_agg{iv}min"
            files_to_check.append(self._get_silver_path(agg_name))
            files_to_check.append(self._get_silver_cache_path(agg_name))
        return [f for f in files_to_check if os.path.exists(f)]

    def delete_series(self, series_name, delete_associated_files=False):
        """Delete a series (or an aggregated variant) and optionally remove files.

        If *series_name* is an aggregated name (e.g. ``PoCII_agg15min``), only
        that aggregation interval is removed from the parent's ``aggregations``
        list and the corresponding silver/cache files are cleaned up.

        If *series_name* is a parent series, all its aggregated silver/cache
        files are also included in the associated-files list.

        Returns:
            dict with keys: deleted, associated_files, deleted_files, errors.
        """
        result = {
            "deleted": False,
            "associated_files": [],
            "deleted_files": [],
            "errors": [],
        }

        parent, interval = self._parse_agg_name(series_name)

        # --- Deleting a specific aggregation interval ---
        if interval is not None:
            parent_def = self.series_defs.get(parent)
            if not parent_def:
                return result
            # Collect silver/cache for the agg name
            silver_file = self._get_silver_path(series_name)
            cache_file = self._get_silver_cache_path(series_name)
            result["associated_files"] = [
                f for f in [silver_file, cache_file] if os.path.exists(f)
            ]
            if delete_associated_files:
                for f in result["associated_files"]:
                    try:
                        os.remove(f)
                        result["deleted_files"].append(f)
                    except Exception as e:
                        result["errors"].append((f, str(e)))
            # Remove interval from parent's list
            agg_list = parent_def.get("aggregations", [])
            if interval in agg_list:
                agg_list.remove(interval)
            self._save_series_defs_to_disk()
            result["deleted"] = True
            return result

        # --- Deleting a parent series ---
        if series_name not in self.series_defs:
            return result

        # Identify associated files (parent + all its aggregations)
        mapping_file = os.path.join(
            paths.BRONZE_DIR, f"{series_name}_mapping.json"
        )
        silver_file = self._get_silver_path(series_name)
        cache_file = self._get_silver_cache_path(series_name)
        files_to_check = [mapping_file, silver_file, cache_file]
        # Include aggregated silver/cache files
        for iv in self.series_defs[series_name].get("aggregations", []):
            agg_name = f"{series_name}_agg{iv}min"
            files_to_check.append(self._get_silver_path(agg_name))
            files_to_check.append(self._get_silver_cache_path(agg_name))
        result["associated_files"] = [f for f in files_to_check if os.path.exists(f)]

        if delete_associated_files:
            for f in result["associated_files"]:
                try:
                    os.remove(f)
                    result["deleted_files"].append(f)
                except Exception as e:
                    result["errors"].append((f, str(e)))

        # Remove from series_defs and persist
        del self.series_defs[series_name]
        self._save_series_defs_to_disk()
        result["deleted"] = True
        return result

    def get_series_field_names(self):
        """
        Return the list of top-level field names and option field names from the structure.

        Returns:
            tuple: (top_level_fields, option_fields)
                top_level_fields: list of str (excluding 'files' and 'options')
                option_fields: list of str
        """
        top_level = [f for f in self.structure if f not in ("files", "options")]
        options = list(self.structure.get("options", {}).keys())
        return top_level, options

    # --- Mapping CRUD ---

    def define_mapping(self, series_name):
        """
        Generate a mapping between schema columns (from schema.csv) and file columns
        from the first worksheet of the given series, using aliases for fuzzy matching.

        If a saved mapping file exists on disk it is loaded and returned directly.

        Args:
            series_name: Name of the series (used to locate mapping file and look up
                         the series definition from self.series_defs).

        Returns:
            tuple: (mapping, schema_names, file_columns)
                mapping:      list of dicts [{"schema_column": ..., "file_column": ...}, ...]
                schema_names: list of schema column names (None when loaded from file)
                file_columns: list of raw file column names (None when loaded from file)
        """
        mapping_path = os.path.join(
            paths.BRONZE_DIR, f"{series_name}_mapping.json"
        )
        # For aggregated series, try to load the mapping for the base/original series
        if not os.path.exists(mapping_path) and "_agg" in series_name:
            base_series = series_name.split("_agg")[0]
            base_mapping_path = os.path.join(
                paths.BRONZE_DIR, f"{base_series}_mapping.json"
            )
            if os.path.exists(base_mapping_path):
                mapping_path = base_mapping_path
        if os.path.exists(mapping_path):
            with open(mapping_path, "r", encoding="utf-8") as f:
                mapping = json.load(f)
                return mapping, None, None

        series_def = self.series_defs.get(series_name)
        if not series_def:
            raise ValueError(
                f"No saved mapping found and no series definition for '{series_name}'."
            )

        file_path = paths.resolve_under_project_root(series_def["files"][0]["path"])
        if (
            "worksheets" in series_def["files"][0]
            and series_def["files"][0]["worksheets"]
        ):
            worksheet = series_def["files"][0]["worksheets"][0]
            header_row = worksheet["header_row"]
            first_data_row = worksheet["first_data_row"]
        else:
            worksheet = None

        # Load the file header (Excel/CSV)
        if file_path.lower().endswith(".xlsx"):
            df = pd.read_excel(
                file_path,
                sheet_name=worksheet["name"],
                header=header_row,
                nrows=first_data_row + 2,
            )
            file_columns = list(df.columns)
            example_row = (
                df.iloc[first_data_row + 1].to_dict()
                if first_data_row < len(df)
                else None
            )
        else:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                for i, row in enumerate(reader):
                    if i == header_row - 1:
                        file_columns = row
                        break

        # Load schema columns from .csv file
        schema_columns = load_schema_columns(paths.SCHEMA_PATH)

        # Build mapping: for each schema column, try to match a file column using aliases
        mapping = []
        for schema_row in schema_columns:
            schema_name = schema_row.get("name", "").strip()
            aliases = schema_row.get("aliases", "")
            origin = schema_row.get("origin", "").strip()
            alias_list = [a.strip() for a in aliases.split(",") if a.strip()]
            matched_col = ""
            example_val = ""
            for col in file_columns:
                col_norm = str(col).strip().lower()
                for alias in alias_list:
                    if col_norm == alias.lower():
                        matched_col = col
                        example_val = example_row.get(col, "")
                        break
                if matched_col:
                    example_val = example_row.get(col, "")
                    break
            mapping.append(
                {
                    "schema_column": schema_name,
                    "file_column": matched_col,
                    "example": example_val,
                    "origin": origin,
                }
            )
        schema_names = [row.get("name", "") for row in schema_columns]
        return mapping, schema_names, file_columns

    def save_mapping(self, series_name, mapping):
        """
        Save a mapping list to ``BRONZE_DIR/{series_name}_mapping.json``
        and update the series definition with the mapping file path.

        Args:
            series_name: The series key.
            mapping: list of mapping dicts.

        Returns:
            str: The output file path.
        """
        bronze_dir = paths.BRONZE_DIR
        os.makedirs(bronze_dir, exist_ok=True)
        out_path = os.path.join(bronze_dir, f"{series_name}_mapping.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
        # Keep series_def in sync so materialize_silver_layer can find the mapping
        if series_name in self.series_defs:
            self.series_defs[series_name]["mapping"] = paths.to_storage_path(
                out_path
            )
            self._save_series_defs_to_disk()
        return out_path

    def delete_mapping(self, series_name):
        """
        Delete the mapping file for a series.

        Args:
            series_name: The series key.

        Returns:
            tuple: (success: bool, error_msg: str or None)
        """
        mapping_path = os.path.join(
            paths.BRONZE_DIR, f"{series_name}_mapping.json"
        )
        if not os.path.exists(mapping_path):
            return True, None  # Nothing to delete
        try:
            os.remove(mapping_path)
            return True, None
        except Exception as e:
            return False, str(e)

    # --- Materialization validation ---

    def validate_for_materialization(self, series_name):
        """
        Check prerequisites for silver layer materialization.

        Args:
            series_name: The series to validate.

        Returns:
            list of error/warning strings. Empty list means validation passed.
        """
        issues = []
        series_def = self.series_defs.get(series_name)
        if not series_def:
            issues.append(f"{series_name}: No series definition.")
            return issues
        files_and_worksheets = series_def.get("files", [])
        if not files_and_worksheets:
            issues.append(f"{series_name}: No files/worksheets defined.")
            return issues
        # Check header rows
        for file_entry in files_and_worksheets:
            worksheets = file_entry.get("worksheets", [])
            for ws in worksheets:
                if "header_row" not in ws or "first_data_row" not in ws:
                    issues.append(
                        f"{series_name}: Header/data rows not specified for all worksheets."
                    )
                    break
            if issues:
                break
        # Check mapping file
        mapping_file = self._get_mapping_file_for_series(series_name)
        if not mapping_file:
            issues.append(f"{series_name}: mapping.json not found in bronze.")
        # Check raw files exist
        bronze_dir = paths.BRONZE_DIR
        missing_files = []
        for fw in files_and_worksheets:
            file_path = paths.normalize_separators(fw.get("path"))
            if not file_path:
                missing_files.append("(unspecified file)")
                continue
            bronze_path = os.path.join(bronze_dir, os.path.basename(file_path))
            if os.path.exists(bronze_path):
                continue
            # Fallback: maybe the stored path is already absolute / valid
            resolved = paths.resolve_under_project_root(file_path)
            if not (resolved and os.path.exists(resolved)):
                missing_files.append(os.path.basename(file_path))
        if missing_files:
            issues.append(
                f"{series_name}: Missing files in bronze: {', '.join(missing_files)}"
            )
        return issues

