"""data_visualization -- Plotly chart generation and HTML export.

Central entry point is ``plot_report()``, which:

1. Converts Elapsed time from seconds to hours for display.
2. Classifies columns as raw or aggregated and selects the right trace
   style (``add_standard_traces`` for raw, ``add_band_traces`` for
   min/max/mean bands).
3. Supports an **overlay** series (with configurable time delay).
4. Auto-generates axis labels from the ``units`` dict (via schema.csv).
5. Returns the Plotly ``Figure`` object for Dash embedding.
6. Optionally writes an interactive HTML file with a floating range-
   control panel and opens it in the system browser (controlled by the
   ``open_in_browser`` flag).

Helper functions for aggregation-suffix handling (``strip_agg_suffix``,
``add_agg_suffix``, ``get_base_parameter_names``, ``get_agg_columns_for_base``)
are used by the reporting tabs.

``save_and_open_report()`` is the standalone presentation helper that
writes HTML, injects the range panel, and opens the browser.  Dash consumers
should ignore it and use the returned ``Figure`` directly.
"""

import os
import webbrowser

import numpy as np
import plotly.graph_objs as go
import plotly.io as pio
from plotly.subplots import make_subplots

# Aggregation suffixes used in the project
AGG_SUFFIXES = ("_mean", "_min", "_max")

# Helper functions for aggregation suffix handling
def strip_agg_suffix(col, suffixes=AGG_SUFFIXES):
    """
    Remove a known aggregation suffix (e.g., '_mean', '_min', '_max') from a column name.

    Args:
        col (str): The column name to process.
        suffixes (tuple): Suffixes to remove (default: AGG_SUFFIXES).

    Returns:
        str: The base column name without the aggregation suffix.
    """
    for suf in suffixes:
        if col.endswith(suf):
            return col[: -len(suf)]
    return col

def add_agg_suffix(base, agg_type):
    """
    Append an aggregation suffix (e.g., 'mean', 'min', 'max') to a base parameter name.

    Args:
        base (str): The base parameter name.
        agg_type (str): The aggregation type (with or without leading underscore).

    Returns:
        str: The full column name with aggregation suffix.
    """
    if not agg_type.startswith('_'):
        agg_type = '_' + agg_type
    return base + agg_type

def get_base_parameter_names(columns, suffixes=AGG_SUFFIXES):
    """
    Extract unique base parameter names from a list of column names by removing known aggregation suffixes.

    Args:
        columns (list): List of column names.
        suffixes (tuple): Suffixes to remove (default: AGG_SUFFIXES).

    Returns:
        list: Sorted list of unique base parameter names.
    """
    base_names = set()
    for col in columns:
        base = strip_agg_suffix(col, suffixes)
        # Exclude common non-parameter columns
        if base.lower() not in ('time', 'elapsed time', 'timestamp', 'index', 'test time', 'test time [h]', 'test time [s]'):
            base_names.add(base)
    return sorted(base_names)

def get_agg_columns_for_base(base, df, suffixes=AGG_SUFFIXES):
    """
    For a given base parameter name, find the corresponding mean, min, and max columns in a DataFrame.

    Args:
        base (str): The base parameter name.
        df (pd.DataFrame): DataFrame to search.
        suffixes (tuple): Suffixes to check (default: AGG_SUFFIXES).

    Returns:
        dict: Mapping of aggregation type ('mean', 'min', 'max') to column name or None if not found.
    """
    result = {}
    for suf in suffixes:
        key = suf[1:] if suf.startswith('_') else suf
        col = base + suf
        result[key] = col if col in df.columns else None
    return result

# Helper to get consistent colors
def get_color(idx):
    """
    Get a color from the Plotly colorway palette by index.

    Args:
        idx (int): Index for color selection.

    Returns:
        str: Color string in Plotly format.
    """
    colors = pio.templates['plotly'].layout.colorway
    return colors[idx % len(colors)]


def insert_nan_gaps(x, *y_arrays, gap_factor=2.0):
    """Insert NaN at positions where consecutive x-values jump by more than
    *gap_factor* Ã— median step.  This breaks line/band traces at time gaps
    so filtered-out windows don't get connected by a misleading line.

    Returns new arrays of the same count as inputs.

    Args:
        x (np.ndarray): Sorted x-axis values.
        *y_arrays: One or more y-axis arrays of the same length as *x*.
        gap_factor (float): Multiplier of the median step that triggers a gap.
    """
    if len(x) < 3:
        return (x, *y_arrays)
    dx = np.diff(x)
    positive = dx[dx > 0]
    if len(positive) == 0:
        return (x, *y_arrays)
    median_step = np.median(positive)
    gap_indices = np.where(dx > gap_factor * median_step)[0] + 1
    if len(gap_indices) == 0:
        return (x, *y_arrays)
    nan_x = np.full(len(gap_indices), np.nan)
    new_x = np.insert(x.astype(float), gap_indices, nan_x)
    result = [new_x]
    for y in y_arrays:
        result.append(np.insert(y.astype(float), gap_indices, np.full(len(gap_indices), np.nan)))
    return tuple(result)


# Low-level function to add standard line or marker traces for primary and secondary y-axes
def add_standard_traces(fig, df, x_col, y1_cols, y2_cols, scatter_mode,
                        color_offset=0, color_map=None, name_prefix="",
                        subplot_row=None, subplot_col=None):
    """
    Add standard (line or marker) traces to a Plotly figure for primary and secondary y-axes.

    Args:
        fig (plotly.graph_objs.Figure): The Plotly figure to add traces to.
        df (pd.DataFrame): DataFrame containing the data.
        x_col (str): Name of the x-axis column.
        y1_cols (list): Columns for the primary y-axis.
        y2_cols (list): Columns for the secondary y-axis.
        scatter_mode (str): Plotly scatter mode ('lines', 'markers', etc.).
        color_offset (int): Offset for color selection (default: 0).
        color_map (dict, optional): Mapping of column base name â†’ fixed
            color string.  When a column is found in this dict, the fixed
            color is used instead of the palette.
        name_prefix (str): Optional prefix for trace names (e.g. series
            name).  When non-empty the legend shows
            ``"prefix Â· col_name"`` instead of just ``col_name``.
        subplot_row (int, optional): Subplot row for faceted figures.
        subplot_col (int, optional): Subplot column for faceted figures.
    """
    color_map = color_map or {}
    _pfx = f"{name_prefix} \u00b7 " if name_prefix else ""
    _is_time_lines = (scatter_mode == 'lines' and x_col == 'Elapsed time')
    if _is_time_lines:
        sdf = df.sort_values(x_col)
    # Primary y-axis traces
    for i, col in enumerate(y1_cols):
        base = strip_agg_suffix(col)
        color = color_map.get(base) or get_color(i + color_offset)
        if _is_time_lines:
            xv = sdf[x_col].values
            yv = sdf[col].values
            xv, yv = insert_nan_gaps(xv, yv)
            fig.add_trace(
                go.Scattergl(x=xv, y=yv, line=dict(color=color), mode=scatter_mode, name=f"{_pfx}{col}", showlegend=True),
                secondary_y=False, row=subplot_row, col=subplot_col
            )
        else:
            fig.add_trace(
                go.Scattergl(x=df[x_col], y=df[col], line=dict(color=color), mode=scatter_mode, name=f"{_pfx}{col}", showlegend=True),
                secondary_y=False, row=subplot_row, col=subplot_col
            )
    # Secondary y-axis traces \u2013 offset by len(y1_cols) so colours differ
    for i, col in enumerate(y2_cols):
        base = strip_agg_suffix(col)
        color = color_map.get(base) or get_color(i + color_offset + len(y1_cols))
        if _is_time_lines:
            xv = sdf[x_col].values
            yv = sdf[col].values
            xv, yv = insert_nan_gaps(xv, yv)
            fig.add_trace(
                go.Scattergl(x=xv, y=yv, line=dict(color=color), mode=scatter_mode, name=f"{_pfx}{col}", showlegend=True),
                secondary_y=True, row=subplot_row, col=subplot_col
            )
        else:
            fig.add_trace(
                go.Scattergl(x=df[x_col], y=df[col], line=dict(color=color), mode=scatter_mode, name=f"{_pfx}{col}", showlegend=True),
                secondary_y=True, row=subplot_row, col=subplot_col
            )

# Low-level function for min-max bands (and mean traces) for time-based aggregated data
def add_band_traces(fig, df, x_col, y1_cols, y2_cols, scatter_mode,
                    color_offset=0, color_map=None, name_prefix="",
                    subplot_row=None, subplot_col=None):
    """
    Add min/max band and mean traces for each variable to a Plotly figure, supporting both y-axes.

    Args:
        fig (plotly.graph_objs.Figure): The Plotly figure to add traces to.
        df (pd.DataFrame): DataFrame containing the data.
        x_col (str): Name of the x-axis column.
        y1_cols (list): Base names for primary y-axis bands.
        y2_cols (list): Base names for secondary y-axis bands.
        scatter_mode (str): Plotly scatter mode.
        color_offset (int): Offset for color selection (default: 0).
        color_map (dict, optional): Mapping of column base name â†’ fixed
            color string.  Overrides the palette when a match is found.
        name_prefix (str): Optional prefix for trace names (e.g. series
            name).  When non-empty the legend shows
            ``"prefix Â· var_name"`` instead of just ``var_name``.
        subplot_row (int, optional): Subplot row for faceted figures.
        subplot_col (int, optional): Subplot column for faceted figures.
    """
    color_map = color_map or {}
    _pfx = f"{name_prefix} \u00b7 " if name_prefix else ""

    fig.add_trace(go.Scatter(
        x=[None], y=[None],
        mode='lines',
        line=dict(color='rgba(0,0,0,0.15)', width=10),
        name='Min_Max Envelope',
        legendgroup='band',
        showlegend=True,
        visible='legendonly',
        hoverinfo='skip'
    ), row=subplot_row, col=subplot_col)

    # Build a combined list: (var, secondary_y, color_index)
    all_vars = [(var, False, i + color_offset) for i, var in enumerate(y1_cols)] + \
               [(var, True, i + color_offset + len(y1_cols)) for i, var in enumerate(y2_cols)]

    for var, secondary_y, color_idx in all_vars:
        color = color_map.get(var) or get_color(color_idx)
        min_col = var + '_min'
        max_col = var + '_max'
        mean_col = var + '_mean'
        if min_col in df.columns and max_col in df.columns:
            sorted_df = df.sort_values(x_col)
            valid = (
                (~sorted_df[min_col].isna()) & (~sorted_df[max_col].isna()) &
                np.isfinite(sorted_df[min_col]) & np.isfinite(sorted_df[max_col])
            )
            x = sorted_df.loc[valid, x_col].values
            y_max = sorted_df.loc[valid, max_col].values
            y_min = sorted_df.loc[valid, min_col].values
            if mean_col in df.columns:
                y_mean = sorted_df.loc[valid, mean_col].values
            else:
                with np.errstate(invalid='ignore'):
                    y_mean = np.where(np.isfinite(y_max) & np.isfinite(y_min), (y_max + y_min) / 2, np.nan)
            if len(x) > 1:
                # Insert NaN gaps to break lines/bands at time jumps
                x, y_min, y_max, y_mean = insert_nan_gaps(
                    x, y_min, y_max, y_mean)

                # Split into contiguous segments at NaN positions and
                # emit one closed polygon per segment.  This prevents
                # the toself fill from wrapping/inverting across gaps.
                nan_mask = np.isnan(x)
                segments = []
                seg_start = 0
                for i in range(len(x)):
                    if nan_mask[i]:
                        if i > seg_start:
                            segments.append(slice(seg_start, i))
                        seg_start = i + 1
                if seg_start < len(x):
                    segments.append(slice(seg_start, len(x)))

                for seg in segments:
                    sx = x[seg]
                    if len(sx) < 2:
                        continue
                    band_x = np.concatenate([sx, sx[::-1]])
                    band_y = np.concatenate([y_max[seg], y_min[seg][::-1]])
                    fig.add_trace(go.Scatter(
                        x=band_x,
                        y=band_y,
                        fill='toself',
                        mode='lines',
                        fillcolor=rgb_to_rgba(color, 0.5),
                        line=dict(width=0),
                        showlegend=False,
                        legendgroup='band',
                        name=f"{_pfx}{var} band",
                        marker=dict(color=color),
                        hoverinfo='skip',
                    ), secondary_y=secondary_y, row=subplot_row, col=subplot_col)

                # Mean trace (single, NaN gaps break the line correctly)
                fig.add_trace(go.Scatter(
                    x=x,
                    y=y_mean,
                    mode='lines',
                    line=dict(color=color, width=2),
                    showlegend=True,
                    legendgroup=f"{_pfx}{var}",
                    name=f"{_pfx}{var}",
                    marker=dict(color=color)
                ), secondary_y=secondary_y, row=subplot_row, col=subplot_col)


# Generic plotting function
def plot_report(
    df,
    x_col=None,
    y1_cols=None,
    y2_cols=None,
    labels=None,
    output_file="report.html",
    scatter_mode='lines',
    overlay_df=None,
    overlay_triggered=False,
    overlay_name=None,
    time_delay=0.0,
    units=None,
    open_in_browser=True,
    color_map=None,
    group_col=None,
):
    """
    Generate an interactive Plotly figure for time series data, supporting overlays and both y-axes.

    When *open_in_browser* is True (the default), the figure is also written to
    an HTML file with an interactive range panel and opened in the system browser.
    When False, only the Plotly Figure object is returned â€” suitable for embedding
    in Dash or other programmatic consumers.

    Args:
        df (pd.DataFrame): Main DataFrame with time-series data.
        x_col (str, optional): X-axis column name (default: 'Elapsed time' or first column).
        y1_cols (list, optional): Columns for primary y-axis.
        y2_cols (list, optional): Columns for secondary y-axis.
        labels (dict, optional): Axis and title labels. Auto-generated from units when missing.
        output_file (str): Output HTML filename (used only when *open_in_browser* is True).
        scatter_mode (str): Plotly scatter mode.
        overlay_df (pd.DataFrame, optional): Overlay DataFrame for comparison.
        overlay_triggered (bool): If True, overlay is active.
        overlay_name (str, optional): Name for overlay legend.
        time_delay (float): Time shift to apply to overlay (in hours).
        units (dict, optional): Mapping of column name to unit string from schema.
        open_in_browser (bool): If True, write HTML and open in browser (default True).
        color_map (dict, optional): Mapping of column base name â†’ fixed color
            string (e.g. ``{"Cell voltage": "#d62728"}``).  When provided,
            matching columns use the specified colour instead of the default
            palette.  Non-matching columns still use the palette.
        group_col (str, optional): Column name used to split the DataFrame
            into groups (e.g. ``"_tag_series"``).  Each group gets its own
            set of traces with a distinct colour offset and prefixed legend
            names.  When *None* (default) no grouping is applied and the
            existing single-series behaviour is preserved.

    Returns:
        plotly.graph_objs.Figure: The constructed Plotly figure.
    """
    if x_col is None:
        x_col = "Elapsed time" if "Elapsed time" in df.columns else df.columns[0]

    # Convert Elapsed time from seconds to hours for visualization
    if x_col == "Elapsed time" and "Elapsed time" in df.columns:
        df = df.copy()
        df["Elapsed time"] = df["Elapsed time"] / 3600.0
        for suffix in ("_min", "_max", "_mean"):
            agg_col = f"Elapsed time{suffix}"
            if agg_col in df.columns:
                df[agg_col] = df[agg_col] / 3600.0
        if overlay_df is not None and "Elapsed time" in overlay_df.columns:
            overlay_df = overlay_df.copy()
            overlay_df["Elapsed time"] = overlay_df["Elapsed time"] / 3600.0
            for suffix in ("_min", "_max", "_mean"):
                agg_col = f"Elapsed time{suffix}"
                if agg_col in overlay_df.columns:
                    overlay_df[agg_col] = overlay_df[agg_col] / 3600.0

    if x_col != "Elapsed time":
        scatter_mode = 'markers'  # Show markers if not time-based x-axis
        x_col = [add_agg_suffix(x_col, 'mean')][0] if add_agg_suffix(x_col, 'mean') in df.columns else x_col        

    # Preprocess y1_cols
    def is_time_col(col):
        """Return True if *col* looks like a time-axis column."""
        col_l = col.lower()
        return (
            "time" in col_l
            or col in {"Elapsed time", "Time", "Test time"}
        )

    agg_keywords = ['min', 'max', 'mean']
    agg_cols = [col for col in df.columns if any(col.lower().endswith(kw) for kw in agg_keywords)]

    if agg_cols and x_col == "Elapsed time":
        base_vars = set(
            col[:-(len(kw)+1)]
            for col in agg_cols
            for kw in agg_keywords
            if col.lower().endswith(kw)
        )
        valid_cols = sorted(var for var in base_vars if not is_time_col(var))
        if y1_cols is not None:
            y1_cols = [base for base in y1_cols if base in valid_cols]
        else:
            y1_cols = valid_cols
        if y2_cols is not None:
            y2_cols = [base for base in y2_cols if base in valid_cols]
        else:
            y2_cols = []
    elif agg_cols and x_col != "Elapsed time":
        valid_cols = [col for col in df.columns if col.lower().endswith('mean') and not is_time_col(col)]
        if y1_cols is not None:
            y1_cols = [add_agg_suffix(base, 'mean') if not base.endswith('_mean') and add_agg_suffix(base, 'mean') in df.columns else base for base in y1_cols if base.endswith('_mean') or add_agg_suffix(base, 'mean') in df.columns]
        else:
            y1_cols = valid_cols
        if y2_cols is not None:
            y2_cols = [add_agg_suffix(base, 'mean') if not base.endswith('_mean') and add_agg_suffix(base, 'mean') in df.columns else base for base in y2_cols if base.endswith('_mean') or add_agg_suffix(base, 'mean') in df.columns]
        else:
            y2_cols = []
    else:
        valid_cols = [
            col for col in df.select_dtypes(include=["float", "float32", "float64", "int", "int32", "int64"]).columns
            if col != x_col and not is_time_col(col)
        ]
        if y1_cols is None:
            y1_cols = valid_cols
        else:
            y1_cols = [col for col in y1_cols if col in valid_cols]
        if y2_cols is None:
            y2_cols = []
        else:
            y2_cols = [col for col in y2_cols if col in valid_cols]

    if labels is None:
        labels = {'title': ''}

    # Auto-generate axis labels from units when not explicitly provided
    def _build_axis_label(cols, units_dict):
        """Build an axis label from column names grouped by unit.
        Single unit  â†’ 'Name1, Name2 [unit]'
        Mixed units  â†’ 'Name1 [unit1], Name2 [unit2]'
        """
        if not cols:
            return ''
        from collections import OrderedDict
        grouped = OrderedDict()  # unit â†’ [base_names]
        for c in cols:
            base = strip_agg_suffix(c)
            unit = units_dict.get(base, '')
            grouped.setdefault(unit, []).append(base)
        if len(grouped) == 1:
            unit, names = next(iter(grouped.items()))
            # deduplicate while preserving order
            seen = set()
            unique = [n for n in names if not (n in seen or seen.add(n))]
            label = ', '.join(unique)
            return f'{label} [{unit}]' if unit else label
        else:
            parts = []
            for unit, names in grouped.items():
                seen = set()
                unique = [n for n in names if not (n in seen or seen.add(n))]
                chunk = ', '.join(unique)
                parts.append(f'{chunk} [{unit}]' if unit else chunk)
            return ', '.join(parts)

    if units:
        if 'x' not in labels:
            if x_col == 'Elapsed time':
                labels['x'] = 'Elapsed time [h]'
            else:
                x_base = strip_agg_suffix(x_col)
                x_unit = units.get(x_base, '')
                labels['x'] = f'{x_base} [{x_unit}]' if x_unit else x_base
        if 'y1' not in labels and y1_cols:
            labels['y1'] = _build_axis_label(y1_cols, units)
        if 'y2' not in labels and y2_cols:
            labels['y2'] = _build_axis_label(y2_cols, units)
    else:
        if 'x' not in labels:
            labels['x'] = x_col

    fig = make_subplots(specs=[[{"secondary_y": bool(y2_cols)}]])

    # Overlay plotting logic
    plot_overlay = False
    if overlay_df is not None and "Elapsed time" in overlay_df.columns and overlay_name:
        plot_overlay = True
        color_offset = len(y1_cols)# + len(y2_cols)  # To ensure overlay colors are distinct
        overlay_x_col = x_col
        overlay_y1_cols = y1_cols
        overlay_y2_cols = y2_cols
        overlay_df_copy = overlay_df.copy()
        if time_delay and overlay_x_col == "Elapsed time":
            overlay_df_copy[overlay_x_col] = overlay_df_copy[overlay_x_col] + time_delay
        # Rename columns for legend distinction
        overlay_y1_cols_renamed = [f"{overlay_name} {col}" for col in overlay_y1_cols]
        overlay_y2_cols_renamed = [f"{overlay_name} {col}" for col in overlay_y2_cols]        

        rename_dict = {}
        for col in list(overlay_y1_cols) + list(overlay_y2_cols):
            for suffix in ["_min", "_max", "_mean"]:
                orig = col + suffix
                if orig in overlay_df_copy.columns:
                    new = f"{overlay_name} {col}{suffix}"
                    rename_dict[orig] = new
            if col in overlay_df_copy.columns:
                new = f"{overlay_name} {col}"
                rename_dict[col] = new
        overlay_df_copy.rename(columns=rename_dict, inplace=True)

    # ---- Trace creation (with optional grouping) ----
    _n_vars = len(y1_cols) + len(y2_cols)

    if group_col and group_col in df.columns:
        groups = sorted(df[group_col].unique())
        offset = 0
        for g in groups:
            sub = df[df[group_col] == g]
            pfx = str(g)
            if bool(agg_cols) and x_col == "Elapsed time":
                add_band_traces(fig, sub, x_col, y1_cols, y2_cols,
                                scatter_mode, color_offset=offset,
                                color_map=color_map, name_prefix=pfx)
            else:
                add_standard_traces(fig, sub, x_col, y1_cols, y2_cols,
                                    scatter_mode, color_offset=offset,
                                    color_map=color_map, name_prefix=pfx)
            offset += _n_vars
    else:
        if bool(agg_cols) and x_col == "Elapsed time":
            add_band_traces(fig, df, x_col, y1_cols, y2_cols, scatter_mode,
                            color_map=color_map)
        else:
            add_standard_traces(fig, df, x_col, y1_cols, y2_cols, scatter_mode,
                                color_map=color_map)

    # Overlay traces (always ungrouped â€“ overlay is a separate series)
    if bool(agg_cols) and x_col == "Elapsed time":
        if plot_overlay:
            add_band_traces(fig, overlay_df_copy, overlay_x_col, overlay_y1_cols_renamed, overlay_y2_cols_renamed, scatter_mode, color_offset)
    else:
        if plot_overlay:
            add_standard_traces(fig, overlay_df_copy, overlay_x_col, overlay_y1_cols_renamed, overlay_y2_cols_renamed, scatter_mode, color_offset) 

    fig.update_xaxes(title_text=labels.get('x', x_col), rangeslider_visible=True, rangeselector=dict(
        buttons=list([
            dict(count=1, label="1h", step="hour", stepmode="backward"),
            dict(count=6, label="6h", step="hour", stepmode="backward"),
            dict(count=12, label="12h", step="hour", stepmode="backward"),
            dict(count=1, label="1d", step="day", stepmode="backward"),
            dict(step="all")
        ])
    ))

    if y1_cols:
        fig.update_yaxes(title_text=labels.get('y1', ''), secondary_y=False)
    if y2_cols:
        fig.update_yaxes(title_text=labels.get('y2', ''), secondary_y=True)
    fig.update_layout(
        title=dict(text=labels.get('title', ''), x=0.5, xanchor='center'),
        legend_title="Series",
        hovermode="x unified",
        dragmode="zoom",
        template="plotly_white"
    )

    if open_in_browser:
        save_and_open_report(fig, output_file, has_secondary_y=bool(y2_cols))

    return fig


def save_report(fig, output_file, has_secondary_y=False, open_browser=False):
    """Write a Plotly figure to an HTML file with the floating range-control
    panel injected.

    Args:
        fig (plotly.graph_objs.Figure): The Plotly figure to export.
        output_file (str): Path to the output HTML file.
        has_secondary_y (bool): If True, inject the extended range panel
            (includes Y2 axis control); otherwise inject the standard panel.
        open_browser (bool): If True, open the result in the default browser.
    """
    fig.write_html(output_file)
    with open(output_file, 'r', encoding='utf-8') as f:
        html = f.read()
    panel_html = get_extended_range_panel() if has_secondary_y else get_range_panel_html()
    html = html.replace('</body>', panel_html + '\n</body>')
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    if open_browser:
        webbrowser.open('file://' + os.path.abspath(output_file))


# Back-compat thin wrappers ------------------------------------------------

def save_html_report(fig, output_file, has_secondary_y=False):
    """Write HTML report without opening a browser (Dash UI entry-point)."""
    save_report(fig, output_file, has_secondary_y=has_secondary_y, open_browser=False)


def save_and_open_report(fig, output_file, has_secondary_y=False):
    """Write HTML report and open it in the default browser."""
    save_report(fig, output_file, has_secondary_y=has_secondary_y, open_browser=True)


def rgb_to_rgba(color, alpha=0.2):
    """Convert Plotly RGB, hex, or common named colors to RGBA."""
    color = str(color).strip()
    if color.startswith('rgb'):
        nums = color[color.find('(')+1:color.find(')')].split(',')
        return f'rgba({nums[0].strip()},{nums[1].strip()},{nums[2].strip()},{alpha})'
    if color.startswith('#'):
        hex_value = color.lstrip('#')
        if len(hex_value) == 3:
            hex_value = ''.join(ch * 2 for ch in hex_value)
        if len(hex_value) == 6:
            try:
                r, g, b = (int(hex_value[i:i + 2], 16) for i in (0, 2, 4))
                return f'rgba({r},{g},{b},{alpha})'
            except ValueError:
                pass

    named_colors = {
        "blue": (0, 0, 255),
        "red": (255, 0, 0),
        "green": (0, 128, 0),
        "orange": (255, 165, 0),
        "purple": (128, 0, 128),
        "gray": (128, 128, 128),
        "grey": (128, 128, 128),
        "black": (0, 0, 0),
        "white": (255, 255, 255),
    }
    r, g, b = named_colors.get(color.lower(), (31, 119, 180))
    return f'rgba({r},{g},{b},{alpha})'

def get_range_panel_html():
    """
    Return HTML/JS for an interactive floating panel to control x/y axis ranges in Plotly reports.

    Returns:
        str: HTML string for embedding in Plotly output.
    """
    return r"""
<style>
#xrange-panel-fixed {
  position: fixed;
  right: 40px;
  bottom: 40px;
  z-index: 10;
  background: #fff;
  border: 1px solid #ccc;
  border-radius: 6px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  padding: 8px 12px 8px 12px;
  min-width: 180px;
  font-size: 13px;
}
#xrange-label, #yrange-label { font-size: 12px; font-weight: bold; margin-bottom: 2px; }
#xrange-info, #yrange-info { font-family: monospace; font-size: 12px; background: #f5f5f5; border: 1px solid #ccc; border-radius: 3px; padding: 2px 6px; margin-bottom: 2px; width: 160px; }
#xrange-input, #yrange-input { width: 160px; font-family: monospace; font-size: 12px; margin-bottom: 2px; }
#xrange-apply, #yrange-apply { font-size: 12px; padding: 1px 8px; }
</style>
<div id="xrange-panel-fixed">
  <div id="xrange-label">X-axis range:</div>
  <div id="xrange-info"></div>
  <input id="xrange-input" type="text" placeholder="[min, max]" />
  <button id="xrange-apply">Apply</button>
  <div style="height:8px;"></div>
  <div id="yrange-label">Y-axis range:</div>
  <div id="yrange-info"></div>
  <input id="yrange-input" type="text" placeholder="[min, max]" />
  <button id="yrange-apply">Apply</button>
</div>
<script>
function formatRange(r) {
    if (!r) return '';
    return '[' + Number(r[0]).toFixed(2) + ', ' + Number(r[1]).toFixed(2) + ']';
}
function updateXRangeDisplay(layout) {
    var xrange = layout && layout.xaxis && layout.xaxis.range;
    document.getElementById('xrange-info').innerText = formatRange(xrange);
}
function updateYRangeDisplay(layout) {
    var yrange = layout && layout.yaxis && layout.yaxis.range;
    document.getElementById('yrange-info').innerText = formatRange(yrange);
}
var plot = document.getElementsByClassName('js-plotly-plot')[0];
if (plot) {
    // Initial display
    updateXRangeDisplay(plot.layout);
    updateYRangeDisplay(plot.layout);
    plot.on('plotly_relayout', function(e) {
        var layout = plot.layout;
        if (e['xaxis.range[0]'] !== undefined && e['xaxis.range[1]'] !== undefined) {
            layout = {xaxis: {range: [e['xaxis.range[0]'], e['xaxis.range[1]']]}};
        }
        if (e['yaxis.range[0]'] !== undefined && e['yaxis.range[1]'] !== undefined) {
            layout = {yaxis: {range: [e['yaxis.range[0]'], e['yaxis.range[1]']]}};
        }
        updateXRangeDisplay(layout);
        updateYRangeDisplay(layout);
    });
    document.getElementById('xrange-apply').onclick = function() {
        var val = document.getElementById('xrange-input').value.trim();
        if (!val) {
            Plotly.relayout(plot, {'xaxis.autorange': true});
            return;
        }
        var m = val.match(/[\[\(]?\s*([\d.eE+-]+)\s*,\s*([\d.eE+-]+)\s*[\]\)]?/);
        if (m) {
            var min = parseFloat(m[1]);
            var max = parseFloat(m[2]);
            Plotly.relayout(plot, {'xaxis.range': [min, max]});
        } else {
            alert('Please enter a valid range: [min, max]');
        }
    };
    document.getElementById('yrange-apply').onclick = function() {
        var val = document.getElementById('yrange-input').value.trim();
        if (!val) {
            Plotly.relayout(plot, {'yaxis.autorange': true});
            return;
        }
        var m = val.match(/[\[\(]?\s*([\d.eE+-]+)\s*,\s*([\d.eE+-]+)\s*[\]\)]?/);
        if (m) {
            var min = parseFloat(m[1]);
            var max = parseFloat(m[2]);
            Plotly.relayout(plot, {'yaxis.range': [min, max]});
        } else {
            alert('Please enter a valid range: [min, max]');
        }
    };
}
</script>
"""

def get_extended_range_panel():
    """
    Return HTML/JS for an interactive floating panel to control x, y, and y2 axis ranges in Plotly reports.

    Returns:
        str: HTML string for embedding in Plotly output.
    """
    return r"""
<style>
#xrange-panel-fixed {
  position: fixed;
  right: 40px;
  bottom: 40px;
  z-index: 10;
  background: #fff;
  border: 1px solid #ccc;
  border-radius: 6px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  padding: 8px 12px 8px 12px;
  min-width: 180px;
  font-size: 13px;
}
#xrange-label, #yrange-label, #y2range-label { font-size: 12px; font-weight: bold; margin-bottom: 2px; }
#xrange-info, #yrange-info, #y2range-info { font-family: monospace; font-size: 12px; background: #f5f5f5; border: 1px solid #ccc; border-radius: 3px; padding: 2px 6px; margin-bottom: 2px; width: 160px; }
#xrange-input, #yrange-input, #y2range-input { width: 160px; font-family: monospace; font-size: 12px; margin-bottom: 2px; }
#xrange-apply, #yrange-apply, #y2range-apply { font-size: 12px; padding: 1px 8px; }
</style>
<div id="xrange-panel-fixed">
  <div id="xrange-label">X-axis range:</div>
  <div id="xrange-info"></div>
  <input id="xrange-input" type="text" placeholder="[min, max]" />
  <button id="xrange-apply">Apply</button>
  <div style="height:8px;"></div>
  <div id="yrange-label">Y-axis range:</div>
  <div id="yrange-info"></div>
  <input id="yrange-input" type="text" placeholder="[min, max]" />
  <button id="yrange-apply">Apply</button>
  <div style="height:8px;"></div>
  <div id="y2range-label">Y2-axis range:</div>
  <div id="y2range-info"></div>
  <input id="y2range-input" type="text" placeholder="[min, max]" />
  <button id="y2range-apply">Apply</button>
</div>
<script>
function formatRange(r) {
    if (!r) return '';
    return '[' + Number(r[0]).toFixed(2) + ', ' + Number(r[1]).toFixed(2) + ']';
}
function updateXRangeDisplay(layout) {
    var xrange = layout && layout.xaxis && layout.xaxis.range;
    document.getElementById('xrange-info').innerText = formatRange(xrange);
}
function updateYRangeDisplay(layout) {
    var yrange = layout && layout.yaxis && layout.yaxis.range;
    document.getElementById('yrange-info').innerText = formatRange(yrange);
}
function updateY2RangeDisplay(layout) {
    var y2range = layout && layout.yaxis2 && layout.yaxis2.range;
    document.getElementById('y2range-info').innerText = formatRange(y2range);
}
var plot = document.getElementsByClassName('js-plotly-plot')[0];
if (plot) {
    // Initial display
    updateXRangeDisplay(plot.layout);
    updateYRangeDisplay(plot.layout);
    updateY2RangeDisplay(plot.layout);
    plot.on('plotly_relayout', function(e) {
        var layout = plot.layout;
        if (e['xaxis.range[0]'] !== undefined && e['xaxis.range[1]'] !== undefined) {
            layout = {xaxis: {range: [e['xaxis.range[0]'], e['xaxis.range[1]']]}};
        }
        if (e['yaxis.range[0]'] !== undefined && e['yaxis.range[1]'] !== undefined) {
            layout = {yaxis: {range: [e['yaxis.range[0]'], e['yaxis.range[1]']]}};
        }
        if (e['yaxis2.range[0]'] !== undefined && e['yaxis2.range[1]'] !== undefined) {
            layout = {yaxis2: {range: [e['yaxis2.range[0]'], e['yaxis2.range[1]']]}};
        }
        updateXRangeDisplay(layout);
        updateYRangeDisplay(layout);
        updateY2RangeDisplay(layout);
    });
    document.getElementById('xrange-apply').onclick = function() {
        var val = document.getElementById('xrange-input').value.trim();
        if (!val) {
            Plotly.relayout(plot, {'xaxis.autorange': true});
            return;
        }
        var m = val.match(/[\[\(]?\s*([\d.eE+-]+)\s*,\s*([\d.eE+-]+)\s*[\]\)]?/);
        if (m) {
            var min = parseFloat(m[1]);
            var max = parseFloat(m[2]);
            Plotly.relayout(plot, {'xaxis.range': [min, max]});
        } else {
            alert('Please enter a valid range: [min, max]');
        }
    };
    document.getElementById('yrange-apply').onclick = function() {
        var val = document.getElementById('yrange-input').value.trim();
        if (!val) {
            Plotly.relayout(plot, {'yaxis.autorange': true});
            return;
        }
        var m = val.match(/[\[\(]?\s*([\d.eE+-]+)\s*,\s*([\d.eE+-]+)\s*[\]\)]?/);
        if (m) {
            var min = parseFloat(m[1]);
            var max = parseFloat(m[2]);
            Plotly.relayout(plot, {'yaxis.range': [min, max]});
        } else {
            alert('Please enter a valid range: [min, max]');
        }
    };
    document.getElementById('y2range-apply').onclick = function() {
        var val = document.getElementById('y2range-input').value.trim();
        if (!val) {
            Plotly.relayout(plot, {'yaxis2.autorange': true});
            return;
        }
        var m = val.match(/[\[\(]?\s*([\d.eE+-]+)\s*,\s*([\d.eE+-]+)\s*[\]\)]?/);
        if (m) {
            var min = parseFloat(m[1]);
            var max = parseFloat(m[2]);
            Plotly.relayout(plot, {'yaxis2.range': [min, max]});
        } else {
            alert('Please enter a valid range: [min, max]');
        }
    };
}
</script>
"""
