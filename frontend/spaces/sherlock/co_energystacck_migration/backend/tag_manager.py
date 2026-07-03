"""tag_manager -- Generic, data-driven tag engine.

Tag definitions and per-series category ranges live in ``config/tags.json``.
Tags are applied **in-memory** to DataFrames at load time â€” they are
never written into the silver/feather pipeline.

Schema overview
===============
``config/tags.json`` has two sections:

``_tag_definitions`` (list)
    Each entry defines one tag type with a unique *id*, a human *label*,
    a *source* column in the data, a *unit_divisor* (for unit conversion
    before range comparison), the ordered list of *categories*, and a
    *default_category* label for unmatched rows.

    Categories are evaluated in list order â€” **first match wins**.

Per-series sections (e.g. ``"PoCII"``)
    Keyed by ``str(tag_id)``, each value maps category labels to a list
    of ``[lo, hi]`` ranges (in the units *after* dividing by
    ``unit_divisor``).
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import pandas as pd

from . import paths

log = logging.getLogger(__name__)

DEFAULT_TAGS_PATH = paths.TAGS_PATH

# ---------------------------------------------------------------------------
# The series-name tag is always added (not part of _tag_definitions)
# ---------------------------------------------------------------------------
TAG_SERIES = "_tag_series"


def tag_column(tag_id: int) -> str:
    """Return the DataFrame column name for a given tag ID."""
    return f"_tag_{tag_id}"


class TagManager:
    """Load, apply, and persist per-series tags from a JSON file."""

    def __init__(self, tags_path: str = DEFAULT_TAGS_PATH) -> None:
        self._path = tags_path
        self._definitions: list[dict[str, Any]] = []
        self._series: dict[str, dict[str, Any]] = {}
        self.reload()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def reload(self) -> None:
        """(Re-)read tags from disk."""
        if os.path.isfile(self._path):
            with open(self._path, encoding="utf-8") as fh:
                raw = json.load(fh)
            self._definitions = raw.get("_tag_definitions", [])
            self._series = {k: v for k, v in raw.items() if k != "_tag_definitions"}
            log.info("Loaded tags for %d series from %s", len(self._series), self._path)
        else:
            self._definitions = []
            self._series = {}
            log.warning("Tags file not found: %s â€“ starting empty", self._path)

    def save(self) -> None:
        """Write current state back to disk."""
        data: dict[str, Any] = {"_tag_definitions": self._definitions}
        data.update(self._series)
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        log.info("Saved tags to %s", self._path)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_tag_definitions(self) -> list[dict[str, Any]]:
        """Return the list of tag definitions (copies)."""
        return [dict(d) for d in self._definitions]

    def get_tag_definition(self, tag_id: int) -> dict[str, Any] | None:
        """Return a single definition by *tag_id*, or ``None``."""
        for d in self._definitions:
            if d["id"] == tag_id:
                return dict(d)
        return None

    def get_tag_labels(self) -> list[dict[str, str]]:
        """Return ``[{label, value}]`` for UI dropdowns (filters, legend,
        facets).  *value* is the DataFrame column name ``_tag_{id}``.
        Always includes ``TAG_SERIES`` as the first entry.
        """
        items: list[dict[str, str]] = [
            {"label": "PoC name", "value": TAG_SERIES},
        ]
        for d in self._definitions:
            items.append(
                {
                    "label": d["label"],
                    "value": tag_column(d["id"]),
                }
            )
        return items

    def get_series_config(self, series_name: str) -> dict[str, Any]:
        """Return the per-series ranges dict for *series_name*."""
        return self._series.get(self._parent_name(series_name), {})

    def get_all_series(self) -> list[str]:
        """Return sorted list of series names that have tag data."""
        return sorted(self._series.keys())

    # ------------------------------------------------------------------
    # Mutators
    # ------------------------------------------------------------------

    def set_series_ranges(
        self, series_name: str, tag_id: int, ranges: dict[str, list[list[float]]]
    ) -> None:
        """Set/replace category ranges for one tag on one series."""
        parent = self._parent_name(series_name)
        if parent not in self._series:
            self._series[parent] = {}
        self._series[parent][str(tag_id)] = ranges

    def add_tag_definition(
        self,
        label: str,
        source: str,
        unit_divisor: float = 1,
        default_category: str = "uncategorized",
        categories: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a new tag definition and return it."""
        next_id = max((d["id"] for d in self._definitions), default=0) + 1
        defn: dict[str, Any] = {
            "id": next_id,
            "label": label,
            "source": source,
            "unit_divisor": unit_divisor,
            "default_category": default_category,
            "categories": categories or [],
        }
        self._definitions.append(defn)
        return defn

    def remove_tag_definition(self, tag_id: int) -> bool:
        """Remove a tag definition and all per-series ranges for it."""
        before = len(self._definitions)
        self._definitions = [d for d in self._definitions if d["id"] != tag_id]
        tid = str(tag_id)
        for cfg in self._series.values():
            cfg.pop(tid, None)
        return len(self._definitions) < before

    # ------------------------------------------------------------------
    # Tagging engine
    # ------------------------------------------------------------------

    def apply_tags(self, df: pd.DataFrame, series_name: str) -> pd.DataFrame:
        """Return a copy of *df* with tag columns appended.

        The original DataFrame is **not** mutated.
        """
        parent = self._parent_name(series_name)
        series_cfg = self._series.get(parent, {})
        df = df.copy()

        # Always add the series-name column
        df[TAG_SERIES] = parent

        # Apply each tag definition
        for defn in self._definitions:
            col = tag_column(defn["id"])
            df[col] = self._classify(df, defn, series_cfg)

        return df

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parent_name(series_name: str) -> str:
        """Strip aggregation suffix to get the parent series name."""
        m = re.match(r"^(.+?)_agg\d+min$", series_name)
        return m.group(1) if m else series_name

    @staticmethod
    def _classify(df: pd.DataFrame, defn: dict, series_cfg: dict) -> pd.Series:
        """Generic classifier for one tag definition.

        Resolves the source column (tries ``{source}_mean`` first for
        aggregated data), divides by ``unit_divisor``, then checks each
        category's ranges in list order.  First match wins.
        """
        source = defn["source"]
        divisor = defn.get("unit_divisor", 1)
        default = defn.get("default_category", "uncategorized")
        categories = defn.get("categories", [])
        tag_id = str(defn["id"])

        # Resolve source column (prefer _mean variant for aggregated data)
        src_col = None
        for candidate in (f"{source}_mean", source):
            if candidate in df.columns:
                src_col = candidate
                break
        if src_col is None:
            return pd.Series(default, index=df.index)

        values = df[src_col] / divisor if divisor != 1 else df[src_col]

        # Per-series ranges for this tag
        ranges = series_cfg.get(tag_id, {})

        result = pd.Series(default, index=df.index)
        assigned = pd.Series(False, index=df.index)

        # First match wins: iterate in list order (highest priority first)
        for cat in categories:
            cat_ranges = ranges.get(cat, [])
            if not cat_ranges:
                continue
            cat_mask = pd.Series(False, index=df.index)
            for lo, hi in cat_ranges:
                cat_mask |= (values >= lo) & (values <= hi)
            new_matches = cat_mask & ~assigned
            result[new_matches] = cat
            assigned |= new_matches

        return result

