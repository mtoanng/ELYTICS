"""tab_helpers -- Shared utilities for Standard Reports and Custom Reports tabs.

Centralises constants, resolution logic, data caching, figure helpers
and slicer utilities so both tab modules stay DRY.

Export / download helpers live in ``export_helpers``.

Classes
-------
ServerDataCache
    Per-tab server-side DataFrame cache with resolution look-up and
    fallback logic.

Functions
---------
Resolution helpers : ``resolution_label``, ``initial_resolution``,
    ``pick_resolution``, ``build_res_options``
Slicer helpers     : ``approx_equal``, ``elapsed_span``,
    ``apply_padded_window``, ``apply_time_filter``
Figure helpers     : ``downgrade_to_svg``, ``empty_figure``,
    ``apply_axis_overrides``, ``finalise_figure``
Data loading       : ``load_series_data``
"""


from __future__ import annotations

import plotly.graph_objs as go
from dash import no_update

from ..backend.series_data_manager import SeriesDataManager

# ---------------------------------------------------------------------------
# Constants â€“ three-level resolution thresholds (coarse / medium / fine)
# ---------------------------------------------------------------------------
FINE_THRESHOLD_SECONDS = 10 * 3600      # < 10 h visible â†’ fine (raw)
MEDIUM_THRESHOLD_SECONDS = 100 * 3600   # 10â€“100 h visible â†’ medium (1-min)
# > 100 h visible â†’ coarse (15-min)


# ===================================================================== #
#  Server-side data cache                                                #
# ===================================================================== #

class ServerDataCache:

    """Per-tab, server-side cache for DataFrames.

    Each tab creates its own instance so caches are independent.
    Keys are ``"<resolution>:<parent>"`` strings.
    """

    def __init__(self) -> None:
        """Initialise an empty cache."""
        self._data: dict = {}

    # -- basic accessors ------------------------------------------------

    @staticmethod
    def _key(parent: str, resolution: str = "raw") -> str:
        """Build a cache key from *parent* series name and *resolution*."""
        return f"{resolution}:{parent}"

    def get(self, parent: str, resolution: str = "raw"):
        """Return the cached DataFrame for *parent*/*resolution*, or ``None``."""
        return self._data.get(self._key(parent, resolution))

    def put(self, parent: str, resolution: str, df) -> None:
        """Store *df* under the *parent*/*resolution* key."""
        self._data[self._key(parent, resolution)] = df

    def drop_series(self, parent: str) -> None:
        """Remove every cache entry whose key ends with ``:<parent>``."""
        for k in [k for k in self._data if k.endswith(f":{parent}")]:
            del self._data[k]

    # -- higher-level helpers -------------------------------------------

    def slicer_span_seconds(self, parent: str, time_min, time_max):
        """Compute the visible time span from slicer inputs (seconds).

        Falls back to the full raw-data span when no slicer is active.
        """
        if time_min is not None and time_max is not None:
            return (float(time_max) - float(time_min)) * 3600
        raw_df = self.get(parent, "raw")
        if raw_df is not None and not raw_df.empty:
            return elapsed_span(raw_df)
        return None

    def fallback_data(self, parent: str, desired: str, agg_levels):
        """Find an alternative resolution when *desired* has no data.

        Walk: desired â†’ finer levels â†’ raw, then coarser levels.
        Returns ``(df, resolution)``.
        """
        chain = ["raw"]
        if agg_levels:
            for lvl in reversed(agg_levels):        # finest first
                chain.append(f"agg{lvl['interval']}")
        try:
            idx = chain.index(desired)
        except ValueError:
            idx = 0
        for offset in range(len(chain)):
            for candidate_idx in (idx - offset, idx + offset):
                if 0 <= candidate_idx < len(chain):
                    key = self._key(parent, chain[candidate_idx])
                    df = self._data.get(key)
                    if df is not None and not df.empty:
                        return df, chain[candidate_idx]
        return None, desired


# ===================================================================== #
#  Resolution helpers                                                    #
# ===================================================================== #

_RESOLUTION_LABELS = {"raw": "fine (raw 1 s)"}


def resolution_label(resolution: str) -> str:
    """Return a human-readable label such as ``'coarse (15 min)'``."""
    if resolution in _RESOLUTION_LABELS:
        return _RESOLUTION_LABELS[resolution]
    interval = resolution.replace("agg", "")
    try:
        mins = int(interval)
    except ValueError:
        return resolution
    if mins >= 15:
        return f"coarse ({mins} min)"
    return f"medium ({mins} min)"


def initial_resolution(agg_levels) -> str:
    """Return the coarsest available aggregation, or ``'raw'``."""
    if agg_levels:
        return f"agg{agg_levels[0]['interval']}"
    return "raw"


def pick_resolution(span_seconds, agg_levels) -> str:
    """Choose the best resolution for *span_seconds* of visible data.

    Three-level scheme:

    * span < 10 h   â†’ fine  (raw 1-s data)
    * span < 100 h  â†’ medium (1-min agg, if available)
    * span >= 100 h â†’ coarse (15-min agg, if available)

    Falls back gracefully when a level is unavailable.
    """
    if span_seconds is None:
        return initial_resolution(agg_levels)
    if not agg_levels:
        return "raw"

    available = {lvl["interval"]: f"agg{lvl['interval']}" for lvl in agg_levels}

    if span_seconds < FINE_THRESHOLD_SECONDS:
        return "raw"
    if span_seconds < MEDIUM_THRESHOLD_SECONDS:
        return available.get(1, "raw")
    # >= MEDIUM_THRESHOLD â†’ coarse
    if 15 in available:
        return available[15]
    if 1 in available:
        return available[1]
    return "raw"


def build_res_options(agg_levels_meta) -> list[dict]:
    """Build the ``options`` list for the resolution-override dropdown."""
    opts: list[dict] = [
        {"label": "auto", "value": "auto"},
        {"label": "raw", "value": "raw"},
    ]
    for a in sorted(agg_levels_meta, key=lambda m: m["interval"]):
        opts.append(
            {"label": f"{a['interval']} min", "value": f"agg{a['interval']}"},
        )
    return opts


# ===================================================================== #
#  Slicer / data-span helpers                                            #
# ===================================================================== #

def approx_equal(new_val, old_val, tol: float = 0.005) -> bool:
    """Return *True* if two slicer values are close enough to skip an update."""
    if new_val is no_update:
        return True
    if new_val is None and old_val is None:
        return True
    if new_val is None or old_val is None:
        return False
    try:
        return abs(float(new_val) - float(old_val)) < tol
    except (TypeError, ValueError):
        return False


def elapsed_span(df):
    """Return the elapsed-time span in seconds, or ``None``."""
    if "Elapsed time" not in df.columns or df.empty:
        return None
    return df["Elapsed time"].max() - df["Elapsed time"].min()


def apply_padded_window(df, time_min, time_max, factor: float = 2.0):
    """Return a slice of *df* covering a padded window around the slicer.

    The window is *factor* Ã— the slicer span, centred on the slicer
    midpoint (50 % padding on each side when ``factor=2``).

    Parameters
    ----------
    df : DataFrame
        Must contain an ``Elapsed time`` column in **seconds**.
    time_min, time_max : float | None
        Slicer bounds in **hours**.
    factor : float
        Multiplier for the slicer span (default 2Ã—).
    """
    if "Elapsed time" not in df.columns:
        return df
    if time_min is None and time_max is None:
        return df

    et = df["Elapsed time"]
    data_min_h = et.min() / 3600.0
    data_max_h = et.max() / 3600.0

    tmin = float(time_min) if time_min is not None else data_min_h
    tmax = float(time_max) if time_max is not None else data_max_h

    span = tmax - tmin
    if span <= 0:
        span = 1.0

    padding = span * (factor - 1.0) / 2.0
    win_min = max(tmin - padding, data_min_h)
    win_max = min(tmax + padding, data_max_h)

    mask = (et >= win_min * 3600.0) & (et <= win_max * 3600.0)
    return df[mask]


def apply_time_filter(df, time_min, time_max):
    """Hard-filter rows by Elapsed time (hours).  Used for non-time X."""
    if "Elapsed time" not in df.columns:
        return df
    if time_min is None and time_max is None:
        return df
    et = df["Elapsed time"]
    if time_min is not None:
        df = df[et >= float(time_min) * 3600.0]
        et = df["Elapsed time"]
    if time_max is not None:
        df = df[et <= float(time_max) * 3600.0]
    return df


# ===================================================================== #
#  Figure helpers                                                        #
# ===================================================================== #

def downgrade_to_svg(fig):
    """Replace ``Scattergl`` traces with SVG ``Scatter``.

    The SVG-based rangeslider miniature cannot render WebGL traces.
    Returns a **new** figure.
    """
    new_fig = go.Figure(layout=fig.layout)
    for trace in fig.data:
        if isinstance(trace, go.Scattergl):
            props = trace.to_plotly_json()
            props.pop("type", None)
            new_fig.add_trace(go.Scatter(**props))
        else:
            new_fig.add_trace(trace)
    return new_fig


def empty_figure(message: str = "No data"):
    """Return a blank figure with a centered annotation."""
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        showarrow=False,
        font=dict(size=16, color="grey"),
    )
    fig.update_layout(
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        margin=dict(l=60, r=40, t=40, b=10),
    )
    return fig


def apply_axis_overrides(fig, y1_min, y1_max, y2_min, y2_max):
    """Override Y-axis ranges from manual slicer inputs."""
    if y1_min is not None or y1_max is not None:
        y1_range = [
            float(y1_min) if y1_min is not None else None,
            float(y1_max) if y1_max is not None else None,
        ]
        fig.update_layout(yaxis=dict(range=y1_range, autorange=False))
    if y2_min is not None or y2_max is not None:
        y2_range = [
            float(y2_min) if y2_min is not None else None,
            float(y2_max) if y2_max is not None else None,
        ]
        fig.update_layout(yaxis2=dict(range=y2_range, autorange=False))


def finalise_figure(fig, keep_webgl=False):
    """Apply standard Dash optimisations to a raw ``plot_report`` figure.

    * Downgrade Scattergl â†’ SVG Scatter (rangeslider compatibility) - unless keep_webgl=True
    * Enable range slider (only for time-series with downgraded SVG traces).
    * Tighten margins and position legend.
    
    Args:
        fig: Plotly Figure object
        keep_webgl: If True, keep Scattergl traces as-is (for scatter plots, no rangeslider)
    """
    if not keep_webgl:
        # For time-series: downgrade to SVG for rangeslider compatibility
        fig = downgrade_to_svg(fig)
        fig.update_xaxes(rangeslider=dict(visible=True, thickness=0.04))
    # For scatter plots with WebGL: no rangeslider needed
    
    fig.update_layout(
        margin=dict(l=60, r=40, t=40, b=10),
        legend=dict(
            orientation="v",
            yanchor="top", y=1,
            xanchor="left", x=1.02,
            font=dict(size=10),
        ),
    )
    return fig


# ===================================================================== #
#  Data loading (shared series-load pipeline)                            #
# ===================================================================== #

def load_series_data(
    cache: ServerDataCache,
    data_manager: SeriesDataManager,
    series_name: str,
    prev_series: str | None,
):
    """Load raw + aggregated data for *series_name* into *cache*.

    Handles unloading the previous series from both the cache and the
    ``data_manager``.

    Returns
    -------
    tuple : (parent, agg_levels_meta, n_rows_raw, res_options, status)
    """
    # Unload previous series
    if prev_series and prev_series != series_name:
        parent_prev, _ = SeriesDataManager._parse_agg_name(prev_series)
        cache.drop_series(parent_prev)
        for key in list(data_manager.loaded_series.keys()):
            p, _ = SeriesDataManager._parse_agg_name(key)
            if p == parent_prev:
                data_manager.unload_series(key)

    parent, _ = SeriesDataManager._parse_agg_name(series_name)
    series_def = data_manager.series_defs.get(parent, {})
    agg_intervals = sorted(series_def.get("aggregations", []), reverse=True)

    # Load raw data
    raw_df = data_manager.load_silver_data(parent)
    if raw_df is not None and not raw_df.empty:
        cache.put(parent, "raw", raw_df)
    n_rows_raw = len(raw_df) if raw_df is not None else 0

    # Load aggregation levels
    agg_levels_meta: list[dict] = []
    for interval in agg_intervals:
        agg_name = f"{parent}_agg{interval}min"
        agg_df = data_manager.load_silver_data(agg_name)
        if agg_df is not None and not agg_df.empty:
            cache.put(parent, f"agg{interval}", agg_df)
            agg_levels_meta.append({"interval": interval, "name": agg_name})

    # Status string
    status = f"Loaded '{series_name}'"
    if agg_levels_meta:
        intervals_str = ", ".join(
            f"{a['interval']} min" for a in agg_levels_meta
        )
        status += f" - Aggregations: {intervals_str}"
    status += f" - Raw: {n_rows_raw:,} rows"

    res_options = build_res_options(agg_levels_meta)

    return parent, agg_levels_meta, n_rows_raw, res_options, status


def build_window_status(series_name: str, served_resolution: str, row_count: int, query_start_s: float | None = None, query_end_s: float | None = None) -> str:
    resolution_text = resolution_label(served_resolution)
    status = f"Loaded '{series_name}' - Resolution: {resolution_text} - {row_count:,} rows"
    if query_start_s is not None and query_end_s is not None:
        status += f" - Window: {query_start_s / 3600:.2f}h-{query_end_s / 3600:.2f}h"
    return status

