import re

from dash import (
    callback,
    ctx,
    dcc,
    Input,
    Output,
    State,
    no_update,
    register_page,
)
from dash.exceptions import PreventUpdate
import dash_mantine_components as dmc
from dash_iconify import DashIconify
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config.signals import (
    get_signal_title,
    get_signal_unit,
)
from services.backend_service import get_metadata, get_tabular, get_timeseries

register_page(
    __name__,
    path="/sherlock/data-exploration/timeseries-overview",
    title="HOLMES - Sherlock - Timeseries Overview",
)

REQUEST_TIME_COLUMN = "time"
PLOT_TIME_COLUMN = "bucket_start"
TARGET_POINTS = 1200
EMPTY_FIGURE_HEIGHT = 320
PAPER_BG_TRANSPARENT = "rgba(0,0,0,0)"
PLOT_BG_LIGHT = "rgba(0,0,0,0)"
PLOT_BG_DARK = "#1f1f1f"

_GRAPH_STYLE_READY = {
    "width": "100%",
    "minHeight": f"{EMPTY_FIGURE_HEIGHT}px",
}

_GRAPH_STYLE_LOADING = {
    "width": "100%",
    "minHeight": f"{EMPTY_FIGURE_HEIGHT}px",
    "pointerEvents": "none",
}

_GRAPH_WRAPPER_STYLE_READY = {
    "width": "100%",
    "minHeight": f"{EMPTY_FIGURE_HEIGHT}px",
    "overflow": "visible",
}

_GRAPH_WRAPPER_STYLE_LOADING = {
    "width": "100%",
    "minHeight": f"{EMPTY_FIGURE_HEIGHT}px",
    "overflow": "visible",
}

DEFAULT_SIGNALS = [
    "j",
    "u",
    "p_an_in",
    "p_an_out",
    "mf_h2",
    "t_an_in",
    "t_an_out",
]

EXTRA_SIGNALS = [
    "cond_an_in",
    "cond_an_out",
    "cond_cat_in",
    "cond_cat_out",
    "c_h2ino2",
    "c_amb_h2",
    "c_o2inh2",
    "i_set",
    "mf_o2",
    "p_an_out_set",
    "p_cat_in",
    "p_cat_out",
    "p_cat_out_set",
    "t_amb",
    "t_an_in_set",
    "t_cat_in",
    "t_cat_out",
    "vf_an_in",
    "vf_an_in_set",
    "vf_an_out",
    "vf_cat_in",
    "vf_cat_in_set",
    "i",
    "u_cell_avg",
]

DEFAULT_SENSOR_NAMES = [
    get_signal_title(signal_name) for signal_name in DEFAULT_SIGNALS
]

USAGE_BLOCKQUOTE_TEXT = [
    "Choose an order to load the default timeseries view. Add testrig, sample, or cell filters to narrow the result.",
    "Use Additional Signals to extend the plot and switch between average, minimum, and maximum values in the header.",
    "Zoom or pan the chart to reload the selected time window.",
    "Default signals: " + ", ".join(DEFAULT_SENSOR_NAMES) + ".",
]

def _empty_figure(
    theme: str,
    message: str = "Select filters to view timeseries data",
    height: int = EMPTY_FIGURE_HEIGHT,
) -> go.Figure:
    is_dark = theme == "dark"
    plot_bg = PLOT_BG_DARK if is_dark else PLOT_BG_LIGHT
    fig = go.Figure()
    fig.update_layout(
        template="plotly_dark" if is_dark else "plotly",
        autosize=True,
        height=height,
        paper_bgcolor=PAPER_BG_TRANSPARENT,
        plot_bgcolor=plot_bg,
        margin=dict(t=40, l=80, r=30, b=60),
        annotations=[
            dict(
                text=message,
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(size=14),
            )
        ],
    )
    return fig


def _to_options(values: list) -> list[dict]:
    return [{"label": str(v), "value": v} for v in values]

def _to_signal_options(values: list[str]) -> list[dict]:
    return [{"label": get_signal_title(v), "value": v} for v in values]


def _normalize_cell_value(value) -> str | None:
    if value in (None, ""):
        return None
    text = str(value)
    return re.sub(r"\.0$", "", text)


def _resolve_testrig_column(df: pd.DataFrame) -> str | None:
    if "testrig_id" in df.columns:
        return "testrig_id"
    if "testrig_label" in df.columns:
        return "testrig_label"
    return None


def _apply_metadata_filters(
    df: pd.DataFrame,
    order_id=None,
    testrig_id=None,
    sample_name=None,
    number_of_cells=None,
    exclude: str | None = None,
) -> pd.DataFrame:
    filtered = df

    if exclude != "order_id" and order_id not in (None, "") and "order_id" in filtered.columns:
        filtered = filtered[filtered["order_id"] == order_id]

    testrig_column = _resolve_testrig_column(filtered)
    if exclude != "testrig_id" and testrig_id not in (None, "") and testrig_column:
        filtered = filtered[filtered[testrig_column] == testrig_id]

    if (
        exclude != "sample_name"
        and sample_name not in (None, "")
        and "sample_name" in filtered.columns
    ):
        filtered = filtered[filtered["sample_name"] == sample_name]

    if exclude != "number_of_cells" and number_of_cells not in (None, "") and "number_of_cells" in filtered.columns:
        normalized_cells = (
            filtered["number_of_cells"].dropna().astype(str).str.replace(r"\.0$", "", regex=True)
        )
        selected_cell = _normalize_cell_value(number_of_cells)
        filtered = filtered.loc[normalized_cells == selected_cell]

    return filtered


def _metadata_time_bounds(df: pd.DataFrame) -> tuple[str | None, str | None]:
    if df.empty:
        return None, None

    start_candidates = ["start_time", "start_timestamp", "start_ts", "start"]
    end_candidates = ["end_time", "end_timestamp", "end_ts", "end"]

    start_col = next((col for col in start_candidates if col in df.columns), None)
    end_col = next((col for col in end_candidates if col in df.columns), None)
    if not start_col or not end_col:
        return None, None

    start_series = pd.to_datetime(df[start_col], errors="coerce", utc=True).dropna()
    end_series = pd.to_datetime(df[end_col], errors="coerce", utc=True).dropna()
    if start_series.empty or end_series.empty:
        return None, None

    return (
        start_series.min().strftime("%Y-%m-%dT%H:%M:%SZ"),
        end_series.max().strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def _read_viewport(relayout_data: dict | None) -> tuple[str | None, str | None]:
    if not isinstance(relayout_data, dict):
        return None, None

    # Capture viewport updates from any subplot axis (xaxis, xaxis2, ...).
    for key, value in relayout_data.items():
        if re.match(r"^xaxis\d*\.range$", key) and isinstance(value, list):
            if len(value) == 2:
                return value[0], value[1]

    axes = {
        match.group(1)
        for key in relayout_data.keys()
        if (match := re.match(r"^(xaxis\d*)\.range\[[01]\]$", key))
    }
    for axis in sorted(axes):
        left = relayout_data.get(f"{axis}.range[0]")
        right = relayout_data.get(f"{axis}.range[1]")
        if left is not None and right is not None:
            return left, right

    if any(
        relayout_data.get(key) is True
        for key in relayout_data.keys()
        if re.match(r"^xaxis\d*\.autorange$", key)
    ):
        return None, None

    return None, None


_PLOT_COLORS = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
]

EVENT_TYPES = {"loadchange", "ivcurve", "testtype"}
EVENT_COLORS = {
    "loadchange": "rgba(66, 133, 244, 0.16)",
    "ivcurve": "rgba(244, 180, 0, 0.16)",
    "testtype": "rgba(15, 157, 88, 0.16)",
}

MAX_EVENT_OVERLAY_SHAPES = 500
EVENT_MAX_RANGE_DAYS = 14
NORMALIZED_FIGURE_HEIGHT = 460


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    clean = hex_color.lstrip("#")
    if len(clean) != 6:
        return f"rgba(31,119,180,{alpha})"
    red = int(clean[0:2], 16)
    green = int(clean[2:4], 16)
    blue = int(clean[4:6], 16)
    return f"rgba({red},{green},{blue},{alpha})"


def _extract_order_ids_for_events(
    metadata_filtered: pd.DataFrame,
    selected_order_id,
    filtered_order_options: list[dict] | None = None,
) -> list[str]:
    if selected_order_id not in (None, ""):
        return [str(selected_order_id)]

    option_values = [
        str(opt.get("value"))
        for opt in (filtered_order_options or [])
        if isinstance(opt, dict) and opt.get("value") not in (None, "")
    ]
    if option_values:
        return sorted(set(option_values))

    if metadata_filtered.empty or "order_id" not in metadata_filtered.columns:
        return []
    return sorted(metadata_filtered["order_id"].dropna().astype(str).unique().tolist())


def _fetch_events_for_order_ids(order_ids: list[str]) -> list[dict]:
    if not order_ids:
        return []

    # Keep events non-blocking for the page callback.
    max_order_ids = 50
    unique_order_ids = sorted(set(order_ids))[:max_order_ids]

    try:
        merged = get_tabular(
            "sherlock",
            "event",
            filters={"order_id": unique_order_ids},
        )
    except Exception:
        return []

    if merged.empty:
        return []
    if not {"event_type", "start", "end"}.issubset(merged.columns):
        return []

    merged = merged.copy()
    merged["event_type"] = merged["event_type"].astype(str).str.strip().str.lower()
    merged = merged[merged["event_type"].isin(EVENT_TYPES)]
    if merged.empty:
        return []

    if "order_id" not in merged.columns:
        merged["order_id"] = None

    merged["start"] = pd.to_datetime(merged["start"], errors="coerce", utc=True)
    merged["end"] = pd.to_datetime(merged["end"], errors="coerce", utc=True)
    merged = merged.dropna(subset=["start", "end"])
    merged = merged[merged["end"] > merged["start"]]
    if merged.empty:
        return []

    merged["start"] = merged["start"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    merged["end"] = merged["end"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    merged = (
        merged[["order_id", "event_type", "start", "end"]]
        .drop_duplicates(subset=["order_id", "event_type", "start", "end"])
        .sort_values(["start", "event_type", "order_id"])
    )
    return merged.to_dict("records")


def _apply_event_overlays(
    fig: go.Figure,
    event_rows: list[dict],
    all_rows: bool = True,
    row_count: int = 1,
    target_row: int | None = None,
    y_mids: dict[int, float] | None = None,
) -> None:
    if not event_rows:
        return

    # Drawing each event on every subplot row can create thousands of shapes and
    # make Plotly rendering very slow. Fall back to a single-row overlay when
    # the shape count would exceed a safe threshold.
    effective_row_count = max(1, int(row_count)) if all_rows else 1
    if len(event_rows) * effective_row_count > MAX_EVENT_OVERLAY_SHAPES:
        all_rows = False
        effective_row_count = 1

    seen: set[tuple[str, str, str]] = set()
    for event in event_rows:
        event_type = str(event.get("event_type", "")).strip().lower()
        if event_type not in EVENT_TYPES:
            continue

        start_ts = pd.to_datetime(event.get("start"), errors="coerce", utc=True)
        end_ts = pd.to_datetime(event.get("end"), errors="coerce", utc=True)
        if pd.isna(start_ts) or pd.isna(end_ts) or end_ts <= start_ts:
            continue

        start_naive = start_ts.tz_localize(None)
        end_naive = end_ts.tz_localize(None)

        dedupe_key = (event_type, str(start_naive), str(end_naive))
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        vrect_kwargs = dict(
            x0=start_naive,
            x1=end_naive,
            fillcolor=EVENT_COLORS[event_type],
            opacity=1,
            layer="below",
            line_width=0,
        )
        if all_rows:
            rows = range(1, effective_row_count + 1)
        elif target_row is not None:
            rows = [target_row]
        else:
            rows = [None]
        for row_idx in rows:
            try:
                if row_idx is not None:
                    fig.add_vrect(row=row_idx, col=1, **vrect_kwargs)
                else:
                    fig.add_vrect(**vrect_kwargs)
            except Exception:
                pass


def _build_event_lookup(event_rows: list[dict]):
    """Return a function (timestamp) -> event label string or empty string."""
    intervals: list[tuple[pd.Timestamp, pd.Timestamp, str]] = []
    for event in event_rows:
        event_type = str(event.get("event_type", "")).strip().lower()
        if event_type not in EVENT_TYPES:
            continue
        start_ts = pd.to_datetime(event.get("start"), errors="coerce", utc=True)
        end_ts = pd.to_datetime(event.get("end"), errors="coerce", utc=True)
        if pd.isna(start_ts) or pd.isna(end_ts) or end_ts <= start_ts:
            continue
        intervals.append((start_ts.tz_localize(None), end_ts.tz_localize(None), event_type.title()))

    def lookup(ts) -> str:
        if pd.isna(ts):
            return ""
        t = pd.Timestamp(ts)
        if t.tzinfo is not None:
            t = t.tz_localize(None)
        for s, e, label in intervals:
            if s <= t < e:
                return label
        return ""

    return lookup


def _build_event_labels_for_timestamps(
    timestamps: list,
    event_rows: list[dict] | None,
) -> list[str]:
    if not timestamps:
        return []
    lookup = _build_event_lookup(event_rows or [])
    return [lookup(ts) for ts in timestamps]


def _should_render_events(
    viewport_start: str | None,
    viewport_end: str | None,
    time_values: pd.Series,
) -> bool:
    start_ts = pd.to_datetime(viewport_start, errors="coerce", utc=True)
    end_ts = pd.to_datetime(viewport_end, errors="coerce", utc=True)

    if pd.isna(start_ts) or pd.isna(end_ts):
        parsed = pd.to_datetime(time_values, errors="coerce", utc=True).dropna()
        if parsed.empty:
            return False
        start_ts = parsed.min()
        end_ts = parsed.max()

    if pd.isna(start_ts) or pd.isna(end_ts) or end_ts <= start_ts:
        return False

    return (end_ts - start_ts).total_seconds() <= EVENT_MAX_RANGE_DAYS * 24 * 60 * 60

def _resolve_metric_column(df: pd.DataFrame, signal: str, metric: str) -> str | None:
    preferred = f"{signal}_{metric}"
    if preferred in df.columns:
        return preferred
    if metric == "avg" and signal in df.columns:
        return signal
    return None


def _series_has_data(df: pd.DataFrame, column: str | None) -> bool:
    if not column or column not in df.columns:
        return False
    return bool(df[column].notna().any())


def _signal_has_data(df: pd.DataFrame, signal: str, metric: str) -> bool:
    if metric == "all":
        has_avg = _series_has_data(df, _resolve_metric_column(df, signal, "avg"))
        has_min = _series_has_data(df, _resolve_metric_column(df, signal, "min"))
        has_max = _series_has_data(df, _resolve_metric_column(df, signal, "max"))
        return has_avg or (has_min and has_max)
    return _series_has_data(df, _resolve_metric_column(df, signal, metric))


def _build_plot_groups(
    signals: list[str], plot_mode: str
) -> list[tuple[str, str, list[str]]]:
    if plot_mode != "stacked":
        return [
            (get_signal_title(signal), get_signal_unit(signal), [signal])
            for signal in signals
        ]

    grouped: dict[str, list[str]] = {}
    for signal in signals:
        unit = get_signal_unit(signal) or "value"
        grouped.setdefault(unit, []).append(signal)

    return [(f"{unit} signals", unit, grouped[unit]) for unit in grouped]


def _compute_gap_positions(
    time_values: pd.Series,
    max_gap_seconds: int | None,
) -> set[int]:
    if not max_gap_seconds or max_gap_seconds <= 0:
        return set()

    timestamps = pd.to_datetime(time_values, errors="coerce")
    positions: set[int] = set()
    for idx in range(1, len(timestamps)):
        prev_ts = timestamps.iloc[idx - 1]
        curr_ts = timestamps.iloc[idx]
        if pd.isna(prev_ts) or pd.isna(curr_ts):
            continue
        if (curr_ts - prev_ts).total_seconds() > max_gap_seconds:
            positions.add(idx)
    return positions


def _insert_gap_markers(values: list, gap_positions: set[int]) -> list:
    if not gap_positions:
        return values

    output: list = []
    for idx, value in enumerate(values):
        if idx in gap_positions:
            output.append(None)
        output.append(value)
    return output
def _contiguous_band_segments(
    df: pd.DataFrame,
    min_col: str,
    max_col: str,
    gap_positions: set[int],
) -> list[tuple[int, int]]:
    segments: list[tuple[int, int]] = []
    start_idx: int | None = None

    for idx in range(len(df)):
        if idx in gap_positions and start_idx is not None:
            segments.append((start_idx, idx))
            start_idx = None

        min_value = df[min_col].iloc[idx]
        max_value = df[max_col].iloc[idx]
        time_value = df[PLOT_TIME_COLUMN].iloc[idx]
        has_values = not (
            pd.isna(min_value) or pd.isna(max_value) or pd.isna(time_value)
        )

        if not has_values:
            if start_idx is not None:
                segments.append((start_idx, idx))
                start_idx = None
            continue

        if start_idx is None:
            start_idx = idx

    if start_idx is not None:
        segments.append((start_idx, len(df)))

    return segments


def _format_subplot_legend(entries: list[tuple[str, str]]) -> str:
    if not entries:
        return ""
    preview = entries[:3]
    parts = [
        f"<span style='color:{color};font-size:11px'>{name}</span>"
        for name, color in preview
    ]
    extra_count = len(entries) - len(preview)
    if extra_count > 0:
        parts.append(f"<span style='font-size:11px'>+{extra_count} more</span>")
    return " | ".join(parts)


def _build_figure(
    df: pd.DataFrame,
    signals: list[str],
    theme: str,
    metric: str = "avg",
    plot_mode: str = "isolated",
    viewport_start: str | None = None,
    viewport_end: str | None = None,
    bucket_seconds: int | None = None,
    event_rows: list[dict] | None = None,
) -> go.Figure:
    if df.empty:
        return _empty_figure(theme, "No data for selected filters")

    if PLOT_TIME_COLUMN not in df.columns:
        return _empty_figure(theme, "The response does not contain a time column")

    is_dark = theme == "dark"
    template = "plotly_dark" if is_dark else "plotly"
    plot_bg = PLOT_BG_DARK if is_dark else PLOT_BG_LIGHT

    df = df.copy()
    df[PLOT_TIME_COLUMN] = pd.to_datetime(df[PLOT_TIME_COLUMN], errors="coerce")
    df = df.dropna(subset=[PLOT_TIME_COLUMN]).sort_values(PLOT_TIME_COLUMN)
    if df.empty:
        return _empty_figure(theme, "No data for selected filters")

    safe_signals = [
        signal for signal in signals if _signal_has_data(df, signal, metric)
    ]
    if not safe_signals:
        return _empty_figure(theme, "No plottable data for selected signals")

    groups = _build_plot_groups(safe_signals, plot_mode)
    if not groups:
        return _empty_figure(theme, "No plottable data for selected signals")

    n_groups = len(groups)
    is_stacked = plot_mode == "stacked"
    vertical_spacing = 0.09 if is_stacked else 0.055
    total_height = max(360, 280 * n_groups + (40 * n_groups if is_stacked else 0))

    fig = make_subplots(
        rows=n_groups,
        cols=1,
        shared_xaxes=False,
        vertical_spacing=vertical_spacing,
        subplot_titles=[title for title, _unit, _signals in groups],
    )

    gap_positions = _compute_gap_positions(
        df[PLOT_TIME_COLUMN],
        2 * bucket_seconds if bucket_seconds else None,
    )
    x_with_gaps = _insert_gap_markers(df[PLOT_TIME_COLUMN].tolist(), gap_positions)
    # Individual plots intentionally exclude event overlays and event hover labels.

    color_index = 0
    subplot_legends: dict[int, list[tuple[str, str]]] = {}
    for row_index, (_title, unit, group_signals) in enumerate(groups, start=1):
        subplot_legends[row_index] = []
        for signal in group_signals:
            color = _PLOT_COLORS[color_index % len(_PLOT_COLORS)]
            color_index += 1
            signal_title = get_signal_title(signal)
            signal_added = False

            if metric == "all":
                min_col = _resolve_metric_column(df, signal, "min")
                max_col = _resolve_metric_column(df, signal, "max")
                avg_col = _resolve_metric_column(df, signal, "avg")

                has_min = _series_has_data(df, min_col)
                has_max = _series_has_data(df, max_col)
                has_avg = _series_has_data(df, avg_col)

                if has_min and has_max and min_col and max_col:
                    segments = _contiguous_band_segments(
                        df, min_col, max_col, gap_positions
                    )
                    for seg_start, seg_end in segments:
                        seg_x = df[PLOT_TIME_COLUMN].iloc[seg_start:seg_end].tolist()
                        seg_min = df[min_col].iloc[seg_start:seg_end].tolist()
                        seg_max = df[max_col].iloc[seg_start:seg_end].tolist()
                        if len(seg_x) < 2:
                            continue

                        fig.add_trace(
                            go.Scatter(
                                x=seg_x,
                                y=seg_min,
                                mode="lines",
                                line=dict(width=0, color=color),
                                showlegend=False,
                                hoverinfo="skip",
                                connectgaps=False,
                                name=f"{signal_title} min",
                            ),
                            row=row_index,
                            col=1,
                        )
                        signal_added = True
                        fig.add_trace(
                            go.Scatter(
                                x=seg_x,
                                y=seg_max,
                                mode="lines",
                                line=dict(width=0, color=color),
                                fill="tonexty",
                                fillcolor=_hex_to_rgba(color, 0.18),
                                showlegend=False,
                                hoverinfo="skip",
                                connectgaps=False,
                                name=f"{signal_title} max",
                            ),
                            row=row_index,
                            col=1,
                        )
                        signal_added = True

                if has_avg:
                    avg_with_gaps = _insert_gap_markers(
                        df[avg_col].tolist(), gap_positions
                    )
                    fig.add_trace(
                        go.Scatter(
                            x=x_with_gaps,
                            y=avg_with_gaps,
                            mode="lines",
                            name=signal_title,
                            line=dict(width=2.0, color=color),
                            showlegend=False,
                            hovertemplate="%{x}<br>%{y:.4g}<extra>" + signal_title + "</extra>",
                        ),
                        row=row_index,
                        col=1,
                    )
                    signal_added = True
                if signal_added:
                    subplot_legends[row_index].append((signal_title, color))
                continue

            value_col = _resolve_metric_column(df, signal, metric)
            if not _series_has_data(df, value_col):
                continue

            fig.add_trace(
                go.Scatter(
                    x=x_with_gaps,
                    y=_insert_gap_markers(df[value_col].tolist(), gap_positions),
                    mode="lines",
                    name=signal_title,
                    line=dict(width=1.8, color=color),
                    showlegend=False,
                    hovertemplate="%{x}<br>%{y:.4g}<extra>" + signal_title + "</extra>",
                ),
                row=row_index,
                col=1,
            )
            subplot_legends[row_index].append((signal_title, color))

        fig.update_yaxes(
            title_text=unit,
            row=row_index,
            col=1,
            gridcolor="rgba(255,255,255,0.15)" if is_dark else "rgba(0,0,0,0.08)",
        )

    for row_index in range(1, n_groups + 1):
        x_axis_kwargs = {
            "title_text": "",
            "row": row_index,
            "col": 1,
            "gridcolor": "rgba(255,255,255,0.15)" if is_dark else "rgba(0,0,0,0.08)",
        }
        if viewport_start and viewport_end:
            x_axis_kwargs["range"] = [viewport_start, viewport_end]
        fig.update_xaxes(**x_axis_kwargs)

    layout_updates: dict = dict(
        template=template,
        paper_bgcolor=PAPER_BG_TRANSPARENT,
        plot_bgcolor=plot_bg,
        height=total_height,
        margin=dict(t=64, l=80, r=30, b=80),
        showlegend=False,
    )

    fig.update_layout(**layout_updates)

    for row_index in range(1, n_groups + 1):
        row_suffix = "" if row_index == 1 else str(row_index)
        yaxis_name = f"yaxis{row_suffix}"
        y_domain = getattr(fig.layout, yaxis_name).domain
        legend_text = _format_subplot_legend(subplot_legends.get(row_index, []))
        if not legend_text:
            continue
        fig.add_annotation(
            x=0.995,
            y=y_domain[1] - 0.01,
            xref="paper",
            yref="paper",
            text=legend_text,
            showarrow=False,
            xanchor="right",
            yanchor="top",
            align="right",
            borderwidth=0,
            bgcolor="rgba(0,0,0,0)",
        )

    return fig


def _build_normalized_figure(
    df: pd.DataFrame,
    signals: list[str],
    theme: str,
    metric: str = "avg",
    viewport_start: str | None = None,
    viewport_end: str | None = None,
    bucket_seconds: int | None = None,
    event_rows: list[dict] | None = None,
) -> go.Figure:
    if df.empty:
        return _empty_figure(theme, "No data for selected filters")

    if PLOT_TIME_COLUMN not in df.columns:
        return _empty_figure(theme, "The response does not contain a time column")

    resolved_metric = "avg" if metric == "all" else metric
    is_dark = theme == "dark"
    template = "plotly_dark" if is_dark else "plotly"
    plot_bg = PLOT_BG_DARK if is_dark else PLOT_BG_LIGHT

    plot_df = df.copy()
    plot_df[PLOT_TIME_COLUMN] = pd.to_datetime(plot_df[PLOT_TIME_COLUMN], errors="coerce")
    plot_df = plot_df.dropna(subset=[PLOT_TIME_COLUMN]).sort_values(PLOT_TIME_COLUMN)
    if plot_df.empty:
        return _empty_figure(theme, "No data for selected filters")

    safe_signals: list[tuple[str, str]] = []
    for signal in signals:
        value_col = _resolve_metric_column(plot_df, signal, resolved_metric)
        if _series_has_data(plot_df, value_col):
            safe_signals.append((signal, value_col))

    if not safe_signals:
        return _empty_figure(theme, "No plottable data for selected signals")

    gap_positions = _compute_gap_positions(
        plot_df[PLOT_TIME_COLUMN],
        2 * bucket_seconds if bucket_seconds else None,
    )
    x_with_gaps = _insert_gap_markers(plot_df[PLOT_TIME_COLUMN].tolist(), gap_positions)
    include_events = _should_render_events(
        viewport_start,
        viewport_end,
        plot_df[PLOT_TIME_COLUMN],
    )
    event_labels_with_gaps = (
        _build_event_labels_for_timestamps(x_with_gaps, event_rows)
        if include_events
        else None
    )

    fig = go.Figure()
    for idx, (signal, value_col) in enumerate(safe_signals):
        series = pd.to_numeric(plot_df[value_col], errors="coerce")
        min_value = series.min(skipna=True)
        max_value = series.max(skipna=True)
        if pd.isna(min_value) or pd.isna(max_value):
            continue
        if max_value == min_value:
            normalized = series.apply(lambda value: 0.5 if pd.notna(value) else None)
        else:
            normalized = (series - min_value) / (max_value - min_value)

        color = _PLOT_COLORS[idx % len(_PLOT_COLORS)]
        norm_with_gaps = _insert_gap_markers(normalized.tolist(), gap_positions)
        fig.add_trace(
            go.Scatter(
                x=x_with_gaps,
                y=norm_with_gaps,
                mode="lines",
                name=get_signal_title(signal),
                line=dict(width=1.8, color=color),
                showlegend=True,
                customdata=event_labels_with_gaps,
                hovertemplate=(
                    "%{x}<br>%{y:.4f}<br>"
                    "%{customdata}<extra>" + get_signal_title(signal) + "</extra>"
                ),
            )
        )

    if not fig.data:
        return _empty_figure(theme, "No plottable data for selected signals")

    fig.update_layout(
        template=template,
        paper_bgcolor=PAPER_BG_TRANSPARENT,
        plot_bgcolor=plot_bg,
        height=NORMALIZED_FIGURE_HEIGHT,
        margin=dict(t=40, l=80, r=30, b=60),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        yaxis=dict(range=[-0.02, 1.02]),
    )
    fig.update_yaxes(
        title_text="Normalized value",
        gridcolor="rgba(255,255,255,0.15)" if is_dark else "rgba(0,0,0,0.08)",
    )
    x_axis_kwargs = {
        "title_text": "",
        "gridcolor": "rgba(255,255,255,0.15)" if is_dark else "rgba(0,0,0,0.08)",
    }
    if viewport_start and viewport_end:
        x_axis_kwargs["range"] = [viewport_start, viewport_end]
    fig.update_xaxes(**x_axis_kwargs)
    if include_events:
        _apply_event_overlays(fig, event_rows or [], all_rows=False)
    return fig


def _resolve_time_column(df: pd.DataFrame) -> str | None:
    for candidate in ("bucket_start", "time", "ts"):
        if candidate in df.columns:
            return candidate
    return None


def _normalize_datetime_value(value: str | None) -> str | None:
    if value in (None, ""):
        return None
    ts = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(ts):
        return None
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def _humanize_bucket(
    bucket_seconds: int | None, bucket_label: str | None = None
) -> str | None:
    if bucket_label:
        return bucket_label
    if bucket_seconds is None:
        return None
    if bucket_seconds <= 0:
        return f"{bucket_seconds}s"
    days, rem = divmod(bucket_seconds, 24 * 60 * 60)
    hours, rem = divmod(rem, 60 * 60)
    minutes, seconds = divmod(rem, 60)
    if days and not (hours or minutes or seconds):
        return f"{days}d"
    if hours and not (minutes or seconds):
        return f"{hours}h"
    if minutes and not seconds:
        return f"{minutes}m"
    if minutes or seconds:
        parts: list[str] = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        if seconds:
            parts.append(f"{seconds}s")
        return " ".join(parts)
    return f"{bucket_seconds}s"


def timeseries_overview_layout():
    return dmc.Container(
        size="xl",
        py="md",
        children=[
            dmc.Stack(
                gap="md",
                children=[
                    dmc.Stack(
                        gap=2,
                        children=[
                            dmc.Group(
                                gap="xs",
                                align="center",
                                children=[
                                    dmc.Title("Timeseries Overview", order=2),
                                    dmc.ActionIcon(
                                        DashIconify(
                                            icon="material-symbols:info-outline",
                                            width=20,
                                        ),
                                        id="timeseries-usage-toggle",
                                        variant="subtle",
                                        color="blue",
                                        size="md",
                                        radius="xl",
                                    ),
                                ],
                            ),
                            dmc.Text(
                                "Review key stack signals for a selected order and refine the view with filters, extra signals, and time-range zooming.",
                                c="dimmed",
                            ),
                            dmc.Collapse(
                                dmc.Blockquote(
                                    dmc.List(
                                        withPadding=False,
                                        children=[
                                            dmc.ListItem(item)
                                            for item in USAGE_BLOCKQUOTE_TEXT
                                        ],
                                    ),
                                    color="blue",
                                ),
                                opened=False,
                                id="timeseries-usage-collapse",
                            ),
                        ],
                    ),
                    dcc.Store(id="timeseries-usage-open", data=False),
                    dcc.Store(id="timeseries-metadata-store"),
                    dcc.Store(id="timeseries-events-store", data={"order_ids": [], "rows": []}),
                    dcc.Store(
                        id="timeseries-viewport-store",
                        data={"start": None, "end": None},
                    ),
                    dcc.Store(id="timeseries-init-trigger", data=True),
                    dcc.Store(id="timeseries-data-store"),
                    dcc.Download(id="timeseries-download"),
                    dcc.Store(
                        id="timeseries-filter-state-store",
                        data={
                            "order_id": None,
                            "testrig_id": None,
                            "sample_name": None,
                            "number_of_cells": None,
                        },
                    ),
                    dmc.Paper(
                        withBorder=True,
                        p="md",
                        radius="md",
                        children=[
                            dmc.Stack(
                                gap="md",
                                children=[
                                    dmc.SimpleGrid(
                                        cols={"base": 1, "sm": 2, "lg": 3},
                                        spacing="md",
                                        verticalSpacing="md",
                                        children=[
                                            dmc.InputWrapper(
                                                dcc.Dropdown(
                                                    id="timeseries-order-id-filter",
                                                    options=[],
                                                    value=None,
                                                    clearable=False,
                                                    searchable=True,
                                                    placeholder="Select order ID",
                                                    style={"width": "100%"},
                                                ),
                                                label="Order ID",
                                                htmlFor="timeseries-order-id-filter",
                                                className="dmc",
                                                styles={"label": {"marginBottom": "6px"}},
                                            ),
                                            dmc.InputWrapper(
                                                dcc.Dropdown(
                                                    id="timeseries-testrig-id-filter",
                                                    options=[],
                                                    value=None,
                                                    clearable=True,
                                                    searchable=True,
                                                    placeholder="Select testrig ID",
                                                    style={"width": "100%"},
                                                ),
                                                label="Testrig ID",
                                                htmlFor="timeseries-testrig-id-filter",
                                                className="dmc",
                                                styles={"label": {"marginBottom": "6px"}},
                                            ),
                                            dmc.InputWrapper(
                                                dcc.Dropdown(
                                                    id="timeseries-sample-name-filter",
                                                    options=[],
                                                    value=None,
                                                    clearable=True,
                                                    searchable=True,
                                                    placeholder="Select sample name",
                                                    style={"width": "100%"},
                                                ),
                                                label="Sample Name",
                                                htmlFor="timeseries-sample-name-filter",
                                                className="dmc",
                                                styles={"label": {"marginBottom": "6px"}},
                                            ),
                                        ],
                                    ),
                                    dmc.Group(
                                        gap="md",
                                        align="flex-end",
                                        wrap="wrap",
                                        children=[
                                            dmc.Box(
                                                style={"flex": "1 1 320px"},
                                                children=[
                                                    dmc.InputWrapper(
                                                        dcc.Dropdown(
                                                            id="timeseries-number-of-cells-filter",
                                                            options=[],
                                                            value=None,
                                                            clearable=True,
                                                            searchable=True,
                                                            placeholder="Select number of cells",
                                                            style={"width": "100%"},
                                                        ),
                                                        label="Number of Cells",
                                                        htmlFor="timeseries-number-of-cells-filter",
                                                        className="dmc",
                                                        styles={"label": {"marginBottom": "6px"}},
                                                    )
                                                ],
                                            ),
                                            dmc.Box(
                                                style={"flex": "1 1 320px"},
                                                children=[
                                                    dmc.InputWrapper(
                                                        dcc.Dropdown(
                                                            id="timeseries-extra-signals",
                                                            options=_to_signal_options(EXTRA_SIGNALS),
                                                            value=[],
                                                            multi=True,
                                                            clearable=True,
                                                            searchable=True,
                                                            placeholder="Select additional signals",
                                                            style={"width": "100%"},
                                                        ),
                                                        label="Additional Signals",
                                                        htmlFor="timeseries-extra-signals",
                                                        className="dmc",
                                                        styles={"label": {"marginBottom": "6px"}},
                                                    )
                                                ],
                                            ),
                                            dmc.Button(
                                                "Clear",
                                                id="timeseries-clear-filters-btn",
                                                variant="light",
                                                size="xs",
                                                style={"alignSelf": "flex-end", "marginBottom": "2px"},
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                    dmc.Paper(
                        withBorder=True,
                        p="md",
                        radius="md",
                        style={"overflow": "hidden"},
                        children=[
                            dmc.Box(id="timeseries-missing-signals-box"),
                            dmc.Divider(
                                id="timeseries-missing-signals-divider",
                                size="xs",
                                my="sm",
                                style={"display": "none"},
                            ),
                            dmc.Group(
                                justify="space-between",
                                align="flex-end",
                                children=[
                                    dmc.Group(
                                        gap="sm",
                                        wrap="wrap",
                                        children=[
                                            dmc.Group(
                                                gap=6,
                                                align="center",
                                                children=[
                                                    dmc.Text("Start", size="sm", c="dimmed", fw=600),
                                                    dmc.DateTimePicker(
                                                        id="timeseries-start-datetime",
                                                        placeholder="Select start",
                                                        clearable=True,
                                                        size="xs",
                                                        style={"minWidth": "220px"},
                                                    ),
                                                ],
                                            ),
                                            dmc.Group(
                                                gap=6,
                                                align="center",
                                                children=[
                                                    dmc.Text("End", size="sm", c="dimmed", fw=600),
                                                    dmc.DateTimePicker(
                                                        id="timeseries-end-datetime",
                                                        placeholder="Select end",
                                                        clearable=True,
                                                        size="xs",
                                                        style={"minWidth": "220px"},
                                                    ),
                                                ],
                                            ),
                                        ],
                                    ),
                                    dmc.Group(
                                        gap="sm",
                                        align="center",
                                        children=[
                                            dmc.Badge(
                                                id="timeseries-meta-badge",
                                                variant="light",
                                                color="blue",
                                            ),
                                            dmc.Button(
                                                "Download CSV",
                                                id="timeseries-download-btn",
                                                variant="light",
                                                size="xs",
                                                disabled=True,
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            dmc.Space(h="sm"),
                            dmc.Box(
                                id="timeseries-normalized-plot-container",
                                pos="relative",
                                style={
                                    "width": "100%",
                                    "minHeight": f"{NORMALIZED_FIGURE_HEIGHT}px",
                                },
                                children=[
                                    dmc.LoadingOverlay(
                                        id="timeseries-normalized-plot-loading-overlay",
                                        visible=True,
                                        zIndex=10,
                                        loaderProps={
                                            "color": "blue",
                                            "size": "lg",
                                            "variant": "dots",
                                        },
                                        overlayProps={
                                            "radius": "sm",
                                            "blur": 2,
                                            "backgroundOpacity": 0.92,
                                        },
                                    ),
                                    dmc.LoadingOverlay(
                                        id="timeseries-normalized-render-loading-overlay",
                                        visible=False,
                                        zIndex=11,
                                        loaderProps={
                                            "color": "blue",
                                            "size": "lg",
                                            "variant": "dots",
                                        },
                                        overlayProps={
                                            "radius": "sm",
                                            "blur": 2,
                                            "backgroundOpacity": 0.92,
                                        },
                                    ),
                                    dcc.Graph(
                                        id="timeseries-normalized-graph",
                                        figure=_empty_figure(
                                            "light",
                                            "Loading metadata...",
                                            height=NORMALIZED_FIGURE_HEIGHT,
                                        ),
                                        config={
                                            "responsive": True,
                                            "displaylogo": False,
                                        },
                                        style={
                                            "width": "100%",
                                            "minHeight": f"{NORMALIZED_FIGURE_HEIGHT}px",
                                        },
                                    ),
                                ],
                            ),
                            dmc.Divider(size="xs", my="sm"),
                            dmc.Box(
                                id="timeseries-plot-container",
                                pos="relative",
                                style={
                                    "width": "100%",
                                    "minHeight": f"{EMPTY_FIGURE_HEIGHT}px",
                                },
                                children=[
                                    dmc.LoadingOverlay(
                                        id="timeseries-plot-loading-overlay",
                                        visible=True,
                                        zIndex=10,
                                        loaderProps={
                                            "color": "blue",
                                            "size": "lg",
                                            "variant": "dots",
                                        },
                                        overlayProps={
                                            "radius": "sm",
                                            "blur": 2,
                                            "backgroundOpacity": 0.92,
                                        },
                                    ),
                                    dmc.LoadingOverlay(
                                        id="timeseries-render-loading-overlay",
                                        visible=False,
                                        zIndex=11,
                                        loaderProps={
                                            "color": "blue",
                                            "size": "lg",
                                            "variant": "dots",
                                        },
                                        overlayProps={
                                            "radius": "sm",
                                            "blur": 2,
                                            "backgroundOpacity": 0.92,
                                        },
                                    ),
                                    dmc.Box(
                                        id="timeseries-graph-wrapper",
                                        style=_GRAPH_WRAPPER_STYLE_LOADING,
                                        children=[
                                            dcc.Graph(
                                                id="timeseries-graph",
                                                figure=_empty_figure(
                                                    "light", "Loading metadata..."
                                                ),
                                                config={
                                                    "responsive": True,
                                                    "displaylogo": False,
                                                },
                                                style=_GRAPH_STYLE_READY,
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            )
        ],
    )


layout = timeseries_overview_layout


@callback(
    Output("timeseries-usage-open", "data"),
    Input("timeseries-usage-toggle", "n_clicks"),
    State("timeseries-usage-open", "data"),
    prevent_initial_call=True,
)
def toggle_usage_blockquote(n_clicks, is_open):
    if n_clicks is None:
        return no_update
    return not bool(is_open)


@callback(
    Output("timeseries-usage-collapse", "opened"),
    Input("timeseries-usage-open", "data"),
)
def sync_usage_blockquote(is_open):
    return bool(is_open)


@callback(
    Output("timeseries-metadata-store", "data"),
    Input("timeseries-init-trigger", "data"),
)
def load_timeseries_metadata(_):
    rows = get_metadata("sherlock", "timeseries_exp")
    return rows or []


@callback(
    Output("timeseries-filter-state-store", "data"),
    Output("timeseries-order-id-filter", "options"),
    Output("timeseries-order-id-filter", "value"),
    Output("timeseries-testrig-id-filter", "options"),
    Output("timeseries-testrig-id-filter", "value"),
    Output("timeseries-sample-name-filter", "options"),
    Output("timeseries-sample-name-filter", "value"),
    Output("timeseries-number-of-cells-filter", "options"),
    Output("timeseries-number-of-cells-filter", "value"),
    Input("timeseries-metadata-store", "data"),
    Input("timeseries-order-id-filter", "value"),
    Input("timeseries-testrig-id-filter", "value"),
    Input("timeseries-sample-name-filter", "value"),
    Input("timeseries-number-of-cells-filter", "value"),
)
def sync_stateful_filters(
    metadata_rows,
    order_id,
    current_testrig_id,
    current_sample_name,
    current_number_of_cells,
):
    if not metadata_rows:
        return (
            {
                "order_id": order_id,
                "testrig_id": None,
                "sample_name": None,
                "number_of_cells": None,
            },
            [],
            None,
            [],
            None,
            [],
            None,
            [],
            None,
        )

    df = pd.DataFrame(metadata_rows)

    order_df = _apply_metadata_filters(
        df,
        order_id=order_id,
        testrig_id=current_testrig_id,
        sample_name=current_sample_name,
        number_of_cells=current_number_of_cells,
        exclude="order_id",
    )
    order_values = (
        sorted(order_df["order_id"].dropna().unique().tolist(), reverse=True)
        if "order_id" in order_df.columns
        else []
    )
    selected_order = order_id if order_id in order_values else None

    testrig_df = _apply_metadata_filters(
        df,
        order_id=selected_order,
        testrig_id=current_testrig_id,
        sample_name=current_sample_name,
        number_of_cells=current_number_of_cells,
        exclude="testrig_id",
    )
    testrig_column = _resolve_testrig_column(testrig_df)
    testrig_values = (
        sorted(testrig_df[testrig_column].dropna().unique().tolist())
        if testrig_column
        else []
    )
    selected_testrig = (
        current_testrig_id if current_testrig_id in testrig_values else None
    )

    sample_df = _apply_metadata_filters(
        df,
        order_id=selected_order,
        testrig_id=selected_testrig,
        sample_name=current_sample_name,
        number_of_cells=current_number_of_cells,
        exclude="sample_name",
    )
    sample_values = (
        sorted(sample_df["sample_name"].dropna().unique().tolist())
        if "sample_name" in sample_df.columns
        else []
    )
    selected_sample = (
        current_sample_name if current_sample_name in sample_values else None
    )

    cells_df = _apply_metadata_filters(
        df,
        order_id=selected_order,
        testrig_id=selected_testrig,
        sample_name=selected_sample,
        number_of_cells=current_number_of_cells,
        exclude="number_of_cells",
    )
    if "number_of_cells" in cells_df.columns:
        cell_series = (
            cells_df["number_of_cells"]
            .dropna()
            .astype(str)
            .str.replace(r"\.0$", "", regex=True)
        )
        cell_values = sorted(
            cell_series.unique().tolist(), key=lambda x: (not str(x).isdigit(), str(x))
        )
    else:
        cell_values = []

    selected_cells = _normalize_cell_value(current_number_of_cells)
    selected_cells = selected_cells if selected_cells in cell_values else None

    next_state = {
        "order_id": selected_order,
        "testrig_id": selected_testrig,
        "sample_name": selected_sample,
        "number_of_cells": selected_cells,
    }

    return (
        next_state,
        _to_options(order_values),
        selected_order,
        _to_options(testrig_values),
        selected_testrig,
        _to_options(sample_values),
        selected_sample,
        _to_options(cell_values),
        selected_cells,
    )


@callback(
    Output("timeseries-viewport-store", "data"),
    Output("timeseries-start-datetime", "value"),
    Output("timeseries-end-datetime", "value"),
    Input("timeseries-graph", "relayoutData"),
    Input("timeseries-normalized-graph", "relayoutData"),
    State("timeseries-viewport-store", "data"),
    prevent_initial_call=True,
)
def update_viewport_store(
    main_relayout_data,
    normalized_relayout_data,
    current,
):
    relayout_data = None
    trigger_id = ctx.triggered_id

    if trigger_id == "timeseries-normalized-graph" and isinstance(
        normalized_relayout_data, dict
    ):
        relayout_data = normalized_relayout_data
    elif trigger_id == "timeseries-graph" and isinstance(main_relayout_data, dict):
        relayout_data = main_relayout_data
    else:
        for candidate in (main_relayout_data, normalized_relayout_data):
            if isinstance(candidate, dict):
                relayout_data = candidate
                break
    if not isinstance(relayout_data, dict):
        raise PreventUpdate
    if not any(
        re.search(r"^xaxis\d*\.range", key) or re.search(r"^xaxis\d*\.autorange$", key)
        for key in relayout_data
    ):
        raise PreventUpdate

    start, end = _read_viewport(relayout_data)
    start = _normalize_datetime_value(start)
    end = _normalize_datetime_value(end)
    current = current or {"start": None, "end": None}
    if start == current.get("start") and end == current.get("end"):
        raise PreventUpdate
    return {"start": start, "end": end}, start, end


@callback(
    Output("timeseries-viewport-store", "data", allow_duplicate=True),
    Input("timeseries-start-datetime", "value"),
    Input("timeseries-end-datetime", "value"),
    State("timeseries-viewport-store", "data"),
    prevent_initial_call=True,
)
def update_viewport_from_datetime(start_datetime, end_datetime, current):
    start = _normalize_datetime_value(start_datetime)
    end = _normalize_datetime_value(end_datetime)
    current = current or {"start": None, "end": None}
    if start == current.get("start") and end == current.get("end"):
        raise PreventUpdate
    return {"start": start, "end": end}


@callback(
    Output("timeseries-order-id-filter", "value", allow_duplicate=True),
    Output("timeseries-testrig-id-filter", "value", allow_duplicate=True),
    Output("timeseries-sample-name-filter", "value", allow_duplicate=True),
    Output("timeseries-number-of-cells-filter", "value", allow_duplicate=True),
    Output("timeseries-extra-signals", "value", allow_duplicate=True),
    Output("timeseries-viewport-store", "data", allow_duplicate=True),
    Output("timeseries-start-datetime", "value", allow_duplicate=True),
    Output("timeseries-end-datetime", "value", allow_duplicate=True),
    Input("timeseries-clear-filters-btn", "n_clicks"),
    prevent_initial_call=True,
)
def clear_timeseries_filters(n_clicks):
    if not n_clicks:
        raise PreventUpdate
    return None, None, None, None, [], {"start": None, "end": None}, None, None


@callback(
    Output("timeseries-events-store", "data"),
    Input("timeseries-order-id-filter", "value"),
    Input("timeseries-testrig-id-filter", "value"),
    Input("timeseries-sample-name-filter", "value"),
    Input("timeseries-number-of-cells-filter", "value"),
    Input("timeseries-metadata-store", "data"),
    Input("timeseries-order-id-filter", "options"),
    State("timeseries-events-store", "data"),
    prevent_initial_call=False,
)
def load_timeseries_events(
    order_id,
    testrig_id,
    sample_name,
    number_of_cells,
    metadata_rows,
    order_options,
    events_store,
):
    has_required_filter = any(
        f not in (None, "") for f in [order_id, testrig_id, sample_name]
    )
    if not has_required_filter:
        cached = events_store or {}
        if not (cached.get("rows") or cached.get("order_ids")):
            return no_update
        return {"order_ids": [], "rows": []}

    metadata_df = pd.DataFrame(metadata_rows or [])
    metadata_filtered = _apply_metadata_filters(
        metadata_df,
        order_id=order_id,
        testrig_id=testrig_id,
        sample_name=sample_name,
        number_of_cells=number_of_cells,
    )
    event_order_ids = _extract_order_ids_for_events(
        metadata_filtered,
        order_id,
        order_options,
    )
    cached = events_store or {}
    cached_ids = cached.get("order_ids") or []
    if event_order_ids == cached_ids:
        return no_update

    event_rows = _fetch_events_for_order_ids(event_order_ids)
    return {
        "order_ids": event_order_ids,
        "rows": event_rows,
    }


@callback(
    Output("timeseries-data-store", "data"),
    Input("timeseries-order-id-filter", "value"),
    Input("timeseries-testrig-id-filter", "value"),
    Input("timeseries-sample-name-filter", "value"),
    Input("timeseries-number-of-cells-filter", "value"),
    Input("timeseries-extra-signals", "value"),
    Input("timeseries-viewport-store", "data"),
    Input("timeseries-metadata-store", "data"),
    Input("timeseries-events-store", "data"),
    running=[
        (Output("timeseries-graph", "style"), _GRAPH_STYLE_LOADING, _GRAPH_STYLE_READY),
        (Output("timeseries-plot-loading-overlay", "visible"), True, False),
        (Output("timeseries-normalized-plot-loading-overlay", "visible"), True, False),
        (
            Output("timeseries-graph-wrapper", "style"),
            _GRAPH_WRAPPER_STYLE_LOADING,
            _GRAPH_WRAPPER_STYLE_READY,
        ),
    ],
    prevent_initial_call=False,
)
def load_timeseries_data(
    order_id,
    testrig_id,
    sample_name,
    number_of_cells,
    extra_signals,
    viewport,
    metadata_rows,
    events_store,
):
    has_required_filter = any(f not in (None, "") for f in [order_id, testrig_id, sample_name])
    if not has_required_filter:
        return {
            "error": "Please select either Order ID, Testrig ID, or Sample Name to view data",
            "badge": "No request yet",
            "signals": [],
            "events": [],
            "records": [],
            "data_min": None,
            "data_max": None,
            "viewport": viewport or {"start": None, "end": None},
        }

    requested_signals = DEFAULT_SIGNALS + (extra_signals or [])
    signals = list(dict.fromkeys(requested_signals))

    viewport = viewport or {"start": None, "end": None}
    start_value = viewport.get("start")
    end_value = viewport.get("end")

    filters = {}
    if order_id not in (None, ""):
        filters["order_id"] = order_id
    if testrig_id not in (None, ""):
        filters["testrig_id"] = testrig_id
    if sample_name not in (None, ""):
        filters["sample_name"] = sample_name
    if number_of_cells not in (None, ""):
        filters["number_of_cells"] = number_of_cells

    metadata_df = pd.DataFrame(metadata_rows or [])
    metadata_filtered = _apply_metadata_filters(
        metadata_df,
        order_id=order_id,
        testrig_id=testrig_id,
        sample_name=sample_name,
        number_of_cells=number_of_cells,
    )
    metadata_start, metadata_end = _metadata_time_bounds(metadata_filtered)
    event_rows = (events_store or {}).get("rows") or []
    if start_value in (None, "") and metadata_start:
        start_value = metadata_start
    if end_value in (None, "") and metadata_end:
        end_value = metadata_end

    try:
        df = get_timeseries(
            space="sherlock",
            route_name="timeseries_exp",
            start=start_value,
            end=end_value,
            columns=signals,
            time_column=REQUEST_TIME_COLUMN,
            target_points=TARGET_POINTS,
            filters=filters,
        )
    except Exception as exc:
        return {
            "error": f"Request failed: {exc}",
            "badge": "Request error",
            "signals": signals,
            "events": event_rows,
            "records": [],
            "data_min": None,
            "data_max": None,
            "viewport": viewport,
        }

    time_col = _resolve_time_column(df)
    if not time_col:
        return {
            "error": "No supported time column was returned",
            "badge": "Request error",
            "signals": signals,
            "events": event_rows,
            "records": [],
            "data_min": None,
            "data_max": None,
            "viewport": viewport,
        }

    plot_df = df.rename(columns={time_col: PLOT_TIME_COLUMN}).copy()
    plot_df[PLOT_TIME_COLUMN] = pd.to_datetime(
        plot_df[PLOT_TIME_COLUMN], errors="coerce", utc=True
    )
    valid_times = plot_df[PLOT_TIME_COLUMN].dropna()
    data_min = (
        valid_times.min().strftime("%Y-%m-%dT%H:%M:%SZ")
        if not valid_times.empty
        else None
    )
    data_max = (
        valid_times.max().strftime("%Y-%m-%dT%H:%M:%SZ")
        if not valid_times.empty
        else None
    )
    plot_df[PLOT_TIME_COLUMN] = plot_df[PLOT_TIME_COLUMN].dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    meta = df.attrs.get("meta", {}) if hasattr(df, "attrs") else {}
    bucket_seconds = meta.get("bucket_seconds")
    bucket_label = meta.get("bucket_label")
    bucket_display = _humanize_bucket(bucket_seconds, bucket_label)
    badge = f" Bucket: {bucket_display}" if bucket_display else ""

    return {
        "error": None,
        "badge": badge,
        "signals": signals,
        "events": event_rows,
        "bucket_seconds": bucket_seconds,
        "records": plot_df.to_dict("records"),
        "data_min": data_min,
        "data_max": data_max,
        "viewport": viewport,
    }


@callback(
    Output("timeseries-start-datetime", "minDate"),
    Output("timeseries-start-datetime", "maxDate"),
    Output("timeseries-end-datetime", "minDate"),
    Output("timeseries-end-datetime", "maxDate"),
    Output("timeseries-start-datetime", "value", allow_duplicate=True),
    Output("timeseries-end-datetime", "value", allow_duplicate=True),
    Input("timeseries-data-store", "data"),
    prevent_initial_call=True,
)
def sync_datetime_bounds(data):
    data = data or {}
    data_min = _normalize_datetime_value(data.get("data_min"))
    data_max = _normalize_datetime_value(data.get("data_max"))
    if not data_min or not data_max:
        return None, None, None, None, None, None

    viewport = data.get("viewport") or {}
    start_value = _normalize_datetime_value(viewport.get("start")) or data_min
    end_value = _normalize_datetime_value(viewport.get("end")) or data_max

    min_ts = pd.to_datetime(data_min, errors="coerce", utc=True)
    max_ts = pd.to_datetime(data_max, errors="coerce", utc=True)
    start_ts = pd.to_datetime(start_value, errors="coerce", utc=True)
    end_ts = pd.to_datetime(end_value, errors="coerce", utc=True)

    if pd.notna(min_ts) and pd.notna(max_ts):
        if pd.isna(start_ts) or start_ts < min_ts:
            start_value = data_min
            start_ts = min_ts
        if pd.isna(end_ts) or end_ts > max_ts:
            end_value = data_max
            end_ts = max_ts
        if pd.notna(start_ts) and pd.notna(end_ts) and start_ts > end_ts:
            start_value, end_value = data_min, data_max

    return data_min, data_max, data_min, data_max, start_value, end_value


@callback(
    Output("timeseries-download", "data"),
    Input("timeseries-download-btn", "n_clicks"),
    State("timeseries-data-store", "data"),
    prevent_initial_call=True,
)
def download_timeseries_csv(n_clicks, data):
    if not n_clicks:
        raise PreventUpdate

    data = data or {}
    records = data.get("records") or []
    if not records:
        raise PreventUpdate

    df = pd.DataFrame(records)
    return dcc.send_data_frame(df.to_csv, "timeseries_overview.csv", index=False)


@callback(
    Output("timeseries-graph", "figure"),
    Output("timeseries-meta-badge", "children"),
    Output("timeseries-missing-signals-box", "children"),
    Output("timeseries-missing-signals-divider", "style"),
    Output("timeseries-download-btn", "disabled"),
    Input("timeseries-data-store", "data"),
    Input("theme-store", "data"),
    running=[
        (Output("timeseries-render-loading-overlay", "visible"), True, False),
    ],
    prevent_initial_call=False,
)
def render_main_timeseries(data, theme):
    theme = theme or "light"
    metric = "all"
    plot_mode = "isolated"
    data = data or {}
    hidden_divider_style = {"display": "none"}

    error_message = data.get("error")
    if error_message:
        fig = _empty_figure(theme, error_message)
        return fig, data.get("badge", "Request error"), None, hidden_divider_style, True

    records = data.get("records") or []
    signals = data.get("signals") or []
    bucket_seconds = data.get("bucket_seconds")
    viewport = data.get("viewport") or {"start": None, "end": None}

    if not signals:
        fig = _empty_figure(theme, "No signals selected")
        return fig, data.get("badge", ""), None, hidden_divider_style, True

    plot_df = pd.DataFrame(records)
    resolved_signals = [
        signal for signal in signals if _signal_has_data(plot_df, signal, metric)
    ]
    missing_signals = [
        signal for signal in signals if signal not in resolved_signals
    ]

    missing_message = None
    divider_style = hidden_divider_style
    if missing_signals:
        missing_message = dmc.Text(
            f"Missing signals in selected range: {', '.join(missing_signals)}",
            size="sm",
            c="dimmed",
        )
        divider_style = {}

    try:
        fig = _build_figure(
            plot_df,
            resolved_signals,
            theme,
            metric=metric,
            plot_mode=plot_mode,
            viewport_start=viewport.get("start"),
            viewport_end=viewport.get("end"),
            bucket_seconds=bucket_seconds,
        )
    except Exception as e:
        fig = _empty_figure(theme, f"Error building figure: {str(e)}")

    has_records = bool(records)
    return (
        fig,
        data.get("badge", ""),
        missing_message,
        divider_style,
        not has_records,
    )


@callback(
    Output("timeseries-normalized-graph", "figure"),
    Input("timeseries-data-store", "data"),
    Input("theme-store", "data"),
    running=[
        (Output("timeseries-normalized-render-loading-overlay", "visible"), True, False),
    ],
    prevent_initial_call=False,
)
def render_normalized_timeseries(data, theme):
    theme = theme or "light"
    metric = "all"
    data = data or {}

    error_message = data.get("error")
    if error_message:
        fig = _empty_figure(theme, error_message, height=NORMALIZED_FIGURE_HEIGHT)
        return fig

    records = data.get("records") or []
    event_rows = data.get("events") or []
    signals = data.get("signals") or []
    bucket_seconds = data.get("bucket_seconds")
    viewport = data.get("viewport") or {"start": None, "end": None}

    if not signals:
        fig = _empty_figure(theme, "No signals selected", height=NORMALIZED_FIGURE_HEIGHT)
        return fig

    plot_df = pd.DataFrame(records)
    resolved_signals = [
        signal for signal in signals if _signal_has_data(plot_df, signal, metric)
    ]

    try:
        normalized_fig = _build_normalized_figure(
            plot_df,
            resolved_signals,
            theme,
            metric=metric,
            viewport_start=viewport.get("start"),
            viewport_end=viewport.get("end"),
            bucket_seconds=bucket_seconds,
            event_rows=event_rows,
        )
    except Exception as e:
        normalized_fig = _empty_figure(
            theme,
            f"Error building normalized figure: {str(e)}",
            height=NORMALIZED_FIGURE_HEIGHT,
        )
    return normalized_fig
