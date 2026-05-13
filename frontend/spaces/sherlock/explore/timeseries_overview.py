import re

from dash import (
    callback,
    ctx,
    clientside_callback,
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

from services.backend_service import get_metadata, get_timeseries

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

SIGNAL_META = {
    "jStck": ("Current Density", "A/cm^2"),
    "uStck": ("Stack Voltage", "V"),
    "pAndeIn": ("Anode Pressure In", "bar"),
    "pAndeOut": ("Anode Pressure Out", "bar"),
    "mfH2Out": ("H2 Mass Flow Out", "kg/s"),
    "tAndeIn": ("Anode Temp In", "degC"),
    "tAndeOut": ("Anode Temp Out", "degC"),
}

EXTRA_SIGNALS = [
    "cndAndeIn",
    "cndAndeOut",
    "cndCtdeIn",
    "cndCtdeOut",
    "concH2O2",
    "concH2StckAmb",
    "concO2H2",
    "iStckSp",
    "mfO2Out",
    "pAndeOutSp",
    "pCtdeIn",
    "pCtdeOut",
    "pCtdeOutSp",
    "tAmb",
    "tAndeInSp",
    "tCtdeIn",
    "tCtdeOut",
    "vfAndeIn",
    "vfAndeInSp",
    "vfAndeOut",
    "vfCtdeIn",
    "vfCtdeInSp",
    "iStck",
    "uCell",
]

SENSOR_TITLES = {
    "iStck": "Stack Current (iStck)",
    "iStckSp": "Stack Current Setpoint (iStckSp)",
    "jStck": "Current Density (jStck)",
    "uStck": "Stack Voltage (uStck)",
    "uCell": "Cell Voltage (uCell)",
    "pAndeIn": "Anode Inlet Pressure (pAndeIn)",
    "pAndeOut": "Anode Outlet Pressure (pAndeOut)",
    "pAndeOutSp": "Anode Outlet Pressure Setpoint (pAndeOutSp)",
    "pCtdeIn": "Cathode Inlet Pressure (pCtdeIn)",
    "pCtdeOut": "Cathode Outlet Pressure (pCtdeOut)",
    "pCtdeOutSp": "Cathode Outlet Pressure Setpoint (pCtdeOutSp)",
    "tAmb": "Ambient Temperature (tAmb)",
    "tAndeIn": "Anode Inlet Temperature (tAndeIn)",
    "tAndeInSp": "Anode Inlet Temperature Setpoint (tAndeInSp)",
    "tAndeOut": "Anode Outlet Temperature (tAndeOut)",
    "tCtdeIn": "Cathode Inlet Temperature (tCtdeIn)",
    "tCtdeOut": "Cathode Outlet Temperature (tCtdeOut)",
    "vfAndeIn": "Anode Inlet Volume Flow (vfAndeIn)",
    "vfAndeInSp": "Anode Inlet Volume Flow Setpoint (vfAndeInSp)",
    "vfAndeOut": "Anode Outlet Volume Flow (vfAndeOut)",
    "vfCtdeIn": "Cathode Inlet Volume Flow (vfCtdeIn)",
    "vfCtdeInSp": "Cathode Inlet Volume Flow Setpoint (vfCtdeInSp)",
    "mfH2Out": "Hydrogen Outlet Mass Flow (mfH2Out)",
    "mfO2Out": "Oxygen Outlet Mass Flow (mfO2Out)",
    "cndAndeIn": "Anode Inlet Conductivity (cndAndeIn)",
    "cndAndeOut": "Anode Outlet Conductivity (cndAndeOut)",
    "cndCtdeIn": "Cathode Inlet Conductivity (cndCtdeIn)",
    "cndCtdeOut": "Cathode Outlet Conductivity (cndCtdeOut)",
    "concH2O2": "Hydrogen Peroxide Concentration (concH2O2)",
    "concH2StckAmb": "Hydrogen Stack Ambient Concentration (concH2StckAmb)",
    "concO2H2": "Oxygen in Hydrogen Concentration (concO2H2)",
}

SENSOR_UNITS = {
    "iStck": "A",
    "iStckSp": "A",
    "jStck": "A/cm^2",
    "uStck": "V",
    "uCell": "V",
    "pAndeIn": "bar",
    "pAndeOut": "bar",
    "pAndeOutSp": "bar",
    "pCtdeIn": "bar",
    "pCtdeOut": "bar",
    "pCtdeOutSp": "bar",
    "tAmb": "degC",
    "tAndeIn": "degC",
    "tAndeInSp": "degC",
    "tAndeOut": "degC",
    "tCtdeIn": "degC",
    "tCtdeOut": "degC",
    "vfAndeIn": "L/min",
    "vfAndeInSp": "L/min",
    "vfAndeOut": "L/min",
    "vfCtdeIn": "L/min",
    "vfCtdeInSp": "L/min",
    "mfH2Out": "kg/s",
    "mfO2Out": "kg/s",
    "cndAndeIn": "uS/cm",
    "cndAndeOut": "uS/cm",
    "cndCtdeIn": "uS/cm",
    "cndCtdeOut": "uS/cm",
    "concH2O2": "%",
    "concH2StckAmb": "%",
    "concO2H2": "%",
}

DEFAULT_SENSOR_NAMES = [
    f"{label} ({key})" for key, (label, _unit) in SIGNAL_META.items()
]

USAGE_BLOCKQUOTE_TEXT = [
    "Choose an order to load the default timeseries view. Add testrig, sample, or cell filters to narrow the result.",
    "Use Additional Signals to extend the plot and switch between average, minimum, and maximum values in the header.",
    "Zoom or pan the chart to reload the selected time window.",
    "Default signals: " + ", ".join(DEFAULT_SENSOR_NAMES) + ".",
]

NORMALIZED_DESCRIPTION = (
    "Selected signals are min-max normalized to a 0-1 range and overlaid on a shared axis."
)


def _empty_figure(
    theme: str, message: str = "Select filters to view timeseries data"
) -> go.Figure:
    is_dark = theme == "dark"
    plot_bg = PLOT_BG_DARK if is_dark else PLOT_BG_LIGHT
    fig = go.Figure()
    fig.update_layout(
        template="plotly_dark" if is_dark else "plotly",
        autosize=True,
        height=EMPTY_FIGURE_HEIGHT,
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


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    clean = hex_color.lstrip("#")
    if len(clean) != 6:
        return f"rgba(31,119,180,{alpha})"
    red = int(clean[0:2], 16)
    green = int(clean[2:4], 16)
    blue = int(clean[4:6], 16)
    return f"rgba({red},{green},{blue},{alpha})"


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
            (SENSOR_TITLES.get(signal, signal), SENSOR_UNITS.get(signal, ""), [signal])
            for signal in signals
        ]

    grouped: dict[str, list[str]] = {}
    for signal in signals:
        unit = SENSOR_UNITS.get(signal, "value")
        grouped.setdefault(unit, []).append(signal)

    return [(f"{unit} signals", unit, grouped[unit]) for unit in grouped]


def _signal_selector_options(signals: list[str]) -> list[dict[str, str]]:
    return [
        {"label": SENSOR_TITLES.get(signal, signal), "value": signal}
        for signal in signals
    ]


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


def _build_signal_selector_data(
    df: pd.DataFrame,
    signals: list[str],
    metric: str,
) -> list[dict]:
    available = [
        {"label": SENSOR_TITLES.get(signal, signal), "value": signal}
        for signal in signals
        if _signal_has_data(df, signal, metric)
    ]
    missing = [
        {
            "label": SENSOR_TITLES.get(signal, signal),
            "value": signal,
            "disabled": True,
        }
        for signal in signals
        if not _signal_has_data(df, signal, metric)
    ]

    selector_data: list[dict] = [*available]
    if missing:
        selector_data.append({"group": "Missing data", "items": missing})
    return selector_data


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

    color_index = 0
    subplot_legends: dict[int, list[tuple[str, str]]] = {}
    for row_index, (_title, unit, group_signals) in enumerate(groups, start=1):
        subplot_legends[row_index] = []
        for signal in group_signals:
            color = _PLOT_COLORS[color_index % len(_PLOT_COLORS)]
            color_index += 1
            signal_title = SENSOR_TITLES.get(signal, signal)
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
        fig.add_trace(
            go.Scatter(
                x=x_with_gaps,
                y=_insert_gap_markers(normalized.tolist(), gap_positions),
                mode="lines",
                name=SENSOR_TITLES.get(signal, signal),
                line=dict(width=1.8, color=color),
                showlegend=True,
            )
        )

    if not fig.data:
        return _empty_figure(theme, "No plottable data for selected signals")

    fig.update_layout(
        template=template,
        paper_bgcolor=PAPER_BG_TRANSPARENT,
        plot_bgcolor=plot_bg,
        height=360,
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
    return fig


def _resolve_time_column(df: pd.DataFrame) -> str | None:
    for candidate in ("bucket_start", "time", "ts"):
        if candidate in df.columns:
            return candidate
    return None


def _humanize_timestamp(value: str | None) -> str:
    if value in (None, ""):
        return "-"
    ts = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(ts):
        return str(value)
    return ts.strftime("%Y-%m-%d %H:%M:%S UTC")


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
                    dcc.Store(
                        id="timeseries-viewport-store",
                        data={"start": None, "end": None},
                    ),
                    dcc.Store(id="timeseries-init-trigger", data=True),
                    dcc.Store(id="timeseries-data-store"),
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
                                    ),
                                    dmc.InputWrapper(
                                        dcc.Dropdown(
                                            id="timeseries-extra-signals",
                                            options=_to_options(EXTRA_SIGNALS),
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
                                    ),
                                    dmc.Stack(
                                        gap=6,
                                        justify="flex-end",
                                        children=[
                                            dmc.Text("Download", fw=600, size="sm"),
                                            dmc.Button(
                                                "Download CSV (disabled)",
                                                id="timeseries-download-btn",
                                                disabled=True,
                                                variant="light",
                                            ),
                                        ],
                                    ),
                                ],
                            )
                        ],
                    ),
                    dmc.Paper(
                        withBorder=True,
                        p="md",
                        radius="md",
                        style={"overflow": "hidden"},
                        children=[
                            dmc.MultiSelect(
                                id="timeseries-signal-selector",
                                label="Visible Signals",
                                description="Hide or show signals in stacked and isolated views.",
                                data=[],
                                value=None,
                                searchable=True,
                                clearable=False,
                                nothingFoundMessage="No signals available",
                            ),
                            dmc.Divider(size="xs", my="sm"),
                            dmc.Group(
                                justify="space-between",
                                children=[
                                    dmc.Text(
                                        id="timeseries-status-text",
                                        c="dimmed",
                                        size="sm",
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
                                            dmc.Text(
                                                "Value", size="sm", c="dimmed", fw=600
                                            ),
                                            dmc.SegmentedControl(
                                                id="timeseries-metric-selector",
                                                data=[
                                                    {"label": "All", "value": "all"},
                                                    {"label": "Avg", "value": "avg"},
                                                    {"label": "Min", "value": "min"},
                                                    {"label": "Max", "value": "max"},
                                                ],
                                                value="all",
                                                size="xs",
                                                radius="md",
                                                style={"minWidth": "220px"},
                                            ),
                                            dmc.Text(
                                                "Layout", size="sm", c="dimmed", fw=600
                                            ),
                                            dmc.SegmentedControl(
                                                id="timeseries-plot-mode-selector",
                                                data=[
                                                    {
                                                        "label": "Isolated",
                                                        "value": "isolated",
                                                    },
                                                    {
                                                        "label": "Stacked",
                                                        "value": "stacked",
                                                    },
                                                ],
                                                value="isolated",
                                                size="xs",
                                                radius="md",
                                                style={"minWidth": "190px"},
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            dmc.Space(h="sm"),
                            dcc.Graph(
                                id="timeseries-normalized-graph",
                                figure=_empty_figure(
                                    "light", "Loading metadata..."
                                ),
                                config={
                                    "responsive": True,
                                    "displaylogo": False,
                                },
                                style={
                                    "width": "100%",
                                    "minHeight": "360px",
                                },
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
    Output("timeseries-order-id-filter", "options"),
    Output("timeseries-order-id-filter", "value"),
    Input("timeseries-metadata-store", "data"),
)
def populate_order_filter(metadata_rows):
    if not metadata_rows:
        return [], None

    df = pd.DataFrame(metadata_rows)

    order_values = (
        sorted(df["order_id"].dropna().unique().tolist(), reverse=True)
        if "order_id" in df.columns
        else []
    )

    return (
        _to_options(order_values),
        None,
    )


@callback(
    Output("timeseries-filter-state-store", "data"),
    Output("timeseries-testrig-id-filter", "options"),
    Output("timeseries-testrig-id-filter", "value"),
    Output("timeseries-sample-name-filter", "options"),
    Output("timeseries-sample-name-filter", "value"),
    Output("timeseries-number-of-cells-filter", "options"),
    Output("timeseries-number-of-cells-filter", "value"),
    Input("timeseries-metadata-store", "data"),
    Input("timeseries-order-id-filter", "value"),
    State("timeseries-filter-state-store", "data"),
    State("timeseries-testrig-id-filter", "value"),
    State("timeseries-sample-name-filter", "value"),
    State("timeseries-number-of-cells-filter", "value"),
)
def sync_stateful_filters(
    metadata_rows,
    order_id,
    filter_state,
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
        )

    df = pd.DataFrame(metadata_rows)
    filtered_df = df
    if order_id not in (None, "") and "order_id" in df.columns:
        filtered_df = df[df["order_id"] == order_id]

    testrig_column = None
    if "testrig_id" in filtered_df.columns:
        testrig_column = "testrig_id"
    elif "testrig_label" in filtered_df.columns:
        testrig_column = "testrig_label"

    testrig_values = (
        sorted(filtered_df[testrig_column].dropna().unique().tolist())
        if testrig_column
        else []
    )
    sample_values = (
        sorted(filtered_df["sample_name"].dropna().unique().tolist())
        if "sample_name" in filtered_df.columns
        else []
    )

    if "number_of_cells" in filtered_df.columns:
        cell_series = (
            filtered_df["number_of_cells"]
            .dropna()
            .astype(str)
            .str.replace(r"\.0$", "", regex=True)
        )
        cell_values = sorted(
            cell_series.unique().tolist(), key=lambda x: (not str(x).isdigit(), str(x))
        )
    else:
        cell_values = []

    filter_state = filter_state or {}
    preferred_testrig = current_testrig_id or filter_state.get("testrig_id")
    preferred_sample = current_sample_name or filter_state.get("sample_name")
    preferred_cells = current_number_of_cells or filter_state.get("number_of_cells")

    selected_testrig = (
        preferred_testrig if preferred_testrig in testrig_values else None
    )

    selected_sample = preferred_sample if preferred_sample in sample_values else None

    selected_cells = preferred_cells if preferred_cells in cell_values else None

    next_state = {
        "order_id": order_id,
        "testrig_id": selected_testrig,
        "sample_name": selected_sample,
        "number_of_cells": selected_cells,
    }

    return (
        next_state,
        _to_options(testrig_values),
        selected_testrig,
        _to_options(sample_values),
        selected_sample,
        _to_options(cell_values),
        selected_cells,
    )


@callback(
    Output("timeseries-viewport-store", "data"),
    Input("timeseries-graph", "relayoutData"),
    Input("timeseries-normalized-graph", "relayoutData"),
    State("timeseries-viewport-store", "data"),
    prevent_initial_call=True,
)
def update_viewport_store(main_relayout_data, normalized_relayout_data, current):
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
    current = current or {"start": None, "end": None}
    if start == current.get("start") and end == current.get("end"):
        raise PreventUpdate
    return {"start": start, "end": end}


@callback(
    Output("timeseries-data-store", "data"),
    Input("timeseries-order-id-filter", "value"),
    Input("timeseries-testrig-id-filter", "value"),
    Input("timeseries-sample-name-filter", "value"),
    Input("timeseries-number-of-cells-filter", "value"),
    Input("timeseries-extra-signals", "value"),
    Input("timeseries-viewport-store", "data"),
    running=[
        (Output("timeseries-metric-selector", "disabled"), True, False),
        (Output("timeseries-plot-mode-selector", "disabled"), True, False),
        (Output("timeseries-signal-selector", "disabled"), True, False),
        (Output("timeseries-graph", "style"), _GRAPH_STYLE_LOADING, _GRAPH_STYLE_READY),
        (Output("timeseries-plot-loading-overlay", "visible"), True, False),
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
):
    has_required_filter = any(f not in (None, "") for f in [order_id, testrig_id, sample_name])
    if not has_required_filter:
        return {
            "error": "Please select either Order ID, Testrig ID, or Sample Name to view data",
            "status": "Awaiting filter selection",
            "badge": "No request yet",
            "signals": [],
            "records": [],
            "viewport": viewport or {"start": None, "end": None},
        }

    signals = list(SIGNAL_META.keys()) + (extra_signals or [])

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
            "status": "Failed to load timeseries",
            "badge": "Request error",
            "signals": signals,
            "records": [],
            "viewport": viewport,
        }

    time_col = _resolve_time_column(df)
    if not time_col:
        return {
            "error": "No supported time column was returned",
            "status": "No time axis available",
            "badge": "Request error",
            "signals": signals,
            "records": [],
            "viewport": viewport,
        }

    plot_df = df.rename(columns={time_col: PLOT_TIME_COLUMN}).copy()
    plot_df[PLOT_TIME_COLUMN] = pd.to_datetime(
        plot_df[PLOT_TIME_COLUMN], errors="coerce", utc=True
    ).dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    meta = df.attrs.get("meta", {}) if hasattr(df, "attrs") else {}
    bucket_seconds = meta.get("bucket_seconds")
    bucket_label = meta.get("bucket_label")
    bucket_display = _humanize_bucket(bucket_seconds, bucket_label)
    effective_start = meta.get("effective_start") or start_value
    effective_end = meta.get("effective_end") or end_value
    readable_start = _humanize_timestamp(effective_start)
    readable_end = _humanize_timestamp(effective_end)

    status_text = NORMALIZED_DESCRIPTION
    badge = f" Bucket: {bucket_display}" if bucket_display else ""

    return {
        "error": None,
        "status": status_text,
        "badge": badge,
        "signals": signals,
        "bucket_seconds": bucket_seconds,
        "records": plot_df.to_dict("records"),
        "viewport": viewport,
    }

@callback(
    Output("timeseries-signal-selector", "data"),
    Output("timeseries-signal-selector", "value"),
    Input("timeseries-data-store", "data"),
    Input("timeseries-metric-selector", "value"),
    State("timeseries-signal-selector", "value"),
)
def sync_signal_selector(data, metric, current_selection):
    data = data or {}
    signals = data.get("signals") or []
    metric = metric or "all"
    records = data.get("records") or []
    plot_df = pd.DataFrame(records)
    options = _build_signal_selector_data(plot_df, signals, metric)
    selectable_signals = [
        signal for signal in signals if _signal_has_data(plot_df, signal, metric)
    ]

    if not signals:
        return [], []

    if not current_selection:
        return options, selectable_signals

    selected = [signal for signal in current_selection if signal in selectable_signals]
    if not selected:
        return options, selectable_signals
    return options, selected


@callback(
    Output("timeseries-graph", "figure"),
    Output("timeseries-normalized-graph", "figure"),
    Output("timeseries-status-text", "children"),
    Output("timeseries-meta-badge", "children"),
    Input("timeseries-data-store", "data"),
    Input("timeseries-signal-selector", "value"),
    Input("timeseries-metric-selector", "value"),
    Input("timeseries-plot-mode-selector", "value"),
    Input("theme-store", "data"),
    running=[
        (Output("timeseries-render-loading-overlay", "visible"), True, False),
    ],
    prevent_initial_call=False,
)
def render_timeseries(data, selected_signals, metric, plot_mode, theme):
    theme = theme or "light"
    metric = metric or "all"
    plot_mode = plot_mode or "isolated"
    data = data or {}

    error_message = data.get("error")
    if error_message:
        fig = _empty_figure(theme, error_message)
        return fig, fig, data.get("status", "No data"), data.get("badge", "Request error")

    records = data.get("records") or []
    signals = data.get("signals") or []
    bucket_seconds = data.get("bucket_seconds")
    viewport = data.get("viewport") or {"start": None, "end": None}

    if selected_signals is None:
        active_signals = signals
    else:
        active_signals = [signal for signal in selected_signals if signal in signals]

    if not active_signals:
        fig = _empty_figure(theme, "No signals selected")
        return fig, fig, data.get("status", "No data"), data.get("badge", "")

    plot_df = pd.DataFrame(records)
    resolved_signals = [
        signal for signal in active_signals if _signal_has_data(plot_df, signal, metric)
    ]

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

    normalized_fig = _build_normalized_figure(
        plot_df,
        resolved_signals,
        theme,
        metric=metric,
        viewport_start=viewport.get("start"),
        viewport_end=viewport.get("end"),
        bucket_seconds=bucket_seconds,
    )

    return fig, normalized_fig, data.get("status", "No data"), data.get("badge", "")
