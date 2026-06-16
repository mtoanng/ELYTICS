"""
SOH Service - Utility and helper functions for State of Health analysis
"""
import re
import zlib
import numpy as np
import pandas as pd
import plotly.graph_objs as go
import plotly.express as px
from plotly.subplots import make_subplots
import dash

LIGHT_CELL_COLORS = [
    "#3498db", "#e74c3c", "#07b750", "#2807e3", "#b106cf",
    "#09611b", "#e2cd10", "#3307a0", "#b475a1", "#610890",
]

DARK_CELL_COLORS = [
    "#5dade2", "#ff7f7f", "#58d68d", "#7fb3ff", "#f4a3ff",
    "#82e0aa", "#f7dc6f", "#a29bfe", "#f8c9e6", "#c39bd3",
]

# ============================================================================
# General Utility & Helper Functions
# ============================================================================
def get_plotly_template(theme_data):
    """
    Return the Plotly template string for the given theme.
    """
    return "plotly_dark" if theme_data == "dark" else "plotly"

def adjust_color_brightness(hex_color, factor):
    """
    Darken (factor < 1) or lighten (factor > 1) a hex color.
    E.g. factor=0.6 makes it 40% darker, factor=1.3 makes it 30% lighter.
    """
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    r = min(255, max(0, int(r * factor)))
    g = min(255, max(0, int(g * factor)))
    b = min(255, max(0, int(b * factor)))
    return f"#{r:02x}{g:02x}{b:02x}"


def _is_dark_theme(theme_data=None, plotly_template=None):
    if theme_data == "dark":
        return True
    if isinstance(plotly_template, str):
        return "dark" in plotly_template.lower()
    return False


def _get_cell_palette(theme_data=None, plotly_template=None):
    return DARK_CELL_COLORS if _is_dark_theme(theme_data, plotly_template) else LIGHT_CELL_COLORS


def _sample_color(sample_name, theme_data=None, plotly_template=None):
    """Return a stable, theme-aware color for a sample, independent of filtering/order."""
    if sample_name is None:
        return "#e74c3c"
    palette = _get_cell_palette(theme_data, plotly_template)
    idx = zlib.crc32(str(sample_name).encode("utf-8")) % len(palette)
    return palette[idx]


def get_array_len(arr):
    """
    Get length of array (e.g. uCells_array), handling None and various array types."""
    if arr is None:
        return 0
    if isinstance(arr, (list, tuple, np.ndarray)):
        return len(arr)
    return 0

def get_array_element(arr, idx):
    """
    Get element from array at index, returning None on failure.
    """
    if arr is None:
        return None
    try:
        if isinstance(arr, (list, tuple, np.ndarray)) and -len(arr) <= idx < len(arr):
            return arr[idx]
    except (IndexError, TypeError):
        pass
    return None


def add_binned_traces(
    fig, dff, soh_col, color_bins, bin_colors, color_label_name, row_num, soh_type, xaxis_col, is_pressure=False, label_col="color_bin"):
    """
    Add temperature, pressure etc. binned traces to figure. Supports custom label_col for bin labels.
    """
    for bin in color_bins:
        bin_data = dff[dff[label_col] == bin].sort_values("runtime_hours")
        if not bin_data.empty:
            # Format label based on bin type
            if isinstance(bin, (int, float, np.integer, np.floating)):
                bin_label = (
                    f"{int(bin)}-{int(bin + 10)} bar"
                    if is_pressure
                    else f"{int(bin)}-{int(bin + 10)}°C"
                )
            else:
                bin_label = str(bin)

            customdata = (
                bin_data[["IVnumber"]].values
                if "IVnumber" in bin_data.columns
                else np.full((len(bin_data), 1), None)
            )
            fig.add_trace(
                go.Scattergl(
                    x=bin_data[xaxis_col],
                    y=bin_data[soh_col],
                    mode="markers",
                    name=bin_label,
                    marker=dict(size=8, color=bin_colors.get(bin, "#e74c3c")),
                    hovertemplate=f"<b>{color_label_name}</b>: {bin_label}<br><b>{'Runtime [h]' if xaxis_col == 'runtime_hours' else 'Timestamp'}</b>: %{{x}}<br><b>SOH {soh_type.title()} Stack</b>: %{{y:.3f}}<extra></extra>",
                    legendgroup=f"temp{bin}",
                    showlegend=(row_num == 1),
                    customdata=customdata,
                ),
                row=row_num,
                col=1,
            )

def get_polyfit_smooth(x_vals, y_vals, degree=3, n_points=200):
    """
    Given x and y arrays, returns (x_smooth, y_smooth, poly_coeffs) for a polynomial fit.
    poly_coeffs can be used with np.polyval(poly_coeffs, x) to evaluate the fit at arbitrary points.
    Handles both numeric x-values (like runtime) and datetime-like x-values (like timestamps).
    """
    is_datetime = pd.api.types.is_datetime64_any_dtype(x_vals) or pd.api.types.is_string_dtype(x_vals)
    if is_datetime:
        parsed = pd.to_datetime(x_vals, format="mixed", errors="coerce", utc=True)
        # Convert to float64 so NaT becomes np.nan (int64 iNaT is not NaN)
        x_numeric = np.where(parsed.isna(), np.nan, parsed.astype(np.int64).astype(float))
    else:
        x_numeric = np.asarray(x_vals, dtype=float)
    y_numeric = np.asarray(y_vals, dtype=float)

    valid_mask = ~np.isnan(y_numeric) & ~np.isnan(x_numeric)
    
    if valid_mask.sum() >= 3:
        x_valid = x_numeric[valid_mask]
        y_valid = y_numeric[valid_mask]
        x_smooth_numeric = np.linspace(x_valid.min(), x_valid.max(), n_points)
        
        try:
            fit_degree = min(degree, len(np.unique(x_valid)) - 1)
            if fit_degree < 1:
                return None, None, None
            poly_coeffs = np.polyfit(x_valid, y_valid, fit_degree)
            y_smooth = np.polyval(poly_coeffs, x_smooth_numeric)

            if is_datetime:
                x_smooth = pd.to_datetime(x_smooth_numeric)
            else:
                x_smooth = x_smooth_numeric
            
            return x_smooth, y_smooth, poly_coeffs
            
        except Exception:
            return None, None, None
    return None, None, None


def _add_curve_arrowhead(fig, x_vals, y_vals, color, line_width=2):
    """Draw a line-based arrowhead from the last three finite points of a curve."""
    x_arr = np.asarray(x_vals, dtype=float)
    y_arr = np.asarray(y_vals, dtype=float)
    valid_mask = np.isfinite(x_arr) & np.isfinite(y_arr)
    if valid_mask.sum() < 3:
        return

    x_valid = x_arr[valid_mask]
    y_valid = y_arr[valid_mask]
    x_min, x_max = np.min(x_valid), np.max(x_valid)
    y_min, y_max = np.min(y_valid), np.max(y_valid)
    x_span = x_max - x_min
    y_span = y_max - y_min
    if x_span == 0 and y_span == 0:
        return

    # Work in normalized axis space so the arrowhead size stays visually similar
    # across curves with different scales while preserving the tail direction.
    x_scale = x_span if x_span > 0 else 1.0
    y_scale = y_span if y_span > 0 else 1.0

    tip = np.array([(x_valid[-1] - x_min) / x_scale, (y_valid[-1] - y_min) / y_scale], dtype=float)
    prev = np.array([(x_valid[-2] - x_min) / x_scale, (y_valid[-2] - y_min) / y_scale], dtype=float)
    prev_prev = np.array([(x_valid[-3] - x_min) / x_scale, (y_valid[-3] - y_min) / y_scale], dtype=float)

    direction = tip - prev_prev
    direction_norm = np.linalg.norm(direction)
    if direction_norm == 0:
        direction = tip - prev
        direction_norm = np.linalg.norm(direction)
    if direction_norm == 0:
        return

    direction = direction / direction_norm
    perp = np.array([-direction[1], direction[0]])
    arrow_length = 0.055
    arrow_width = 0.025
    wing_1 = tip - direction * arrow_length + perp * arrow_width
    wing_2 = tip - direction * arrow_length - perp * arrow_width

    wing_1 = np.array([wing_1[0] * x_scale + x_min, wing_1[1] * y_scale + y_min], dtype=float)
    tip = np.array([tip[0] * x_scale + x_min, tip[1] * y_scale + y_min], dtype=float)
    wing_2 = np.array([wing_2[0] * x_scale + x_min, wing_2[1] * y_scale + y_min], dtype=float)

    fig.add_trace(go.Scattergl(
        x=[wing_1[0], tip[0], wing_2[0]],
        y=[wing_1[1], tip[1], wing_2[1]],
        mode="lines",
        line=dict(color=color, width=line_width),
        hoverinfo="skip",
        showlegend=False,
    ))

def make_soh_colored_subplot(template, sample_name, xaxis_col, color_label_name):
    """
    Creates a standard 2-row subplot figure for SOH kinetic and linear plots.
    """
    fig = make_subplots(rows=2, cols=1, row_heights=[0.5, 0.5], vertical_spacing=0.12)
    fig.update_layout(
        template=template,
        showlegend=True,
        title=dict(text=f"Stack SOH colored by {color_label_name}", x=0.5, xanchor="center"),
        legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=0.98),
        margin=dict(l=40, r=120, t=80, b=40),
        height=None,
    )
    if sample_name:
        fig.add_annotation(
            text=sample_name, xref="paper", yref="paper",
            x=0.5, y=1.04, showarrow=False,
            font=dict(size=11, color="gray"), xanchor="center", yanchor="bottom",
        )
    fig.update_xaxes(title_text="", row=1, col=1)
    fig.update_xaxes(title_text="Runtime [h]" if xaxis_col == "runtime_hours" else "Timestamp", row=2, col=1)
    fig.update_yaxes(title_text="SOH Kinetic [-]", row=1, col=1)
    fig.update_yaxes(title_text="SOH Linear [mΩ·cm²]", row=2, col=1)
    return fig

def sci_fmt_interval(interval):
    """
    Format a pandas Interval in scientific notation for display.
    """
    if pd.isna(interval):
        return "N/A"
    left = f"{interval.left:.2e}"
    right = f"{interval.right:.2e}"
    closed = interval.closed
    return f"({left},{right}{']' if closed == 'right' else ')'}"

def _filter_valid_timestamps(dff, xaxis_col, min_date="2024-01-01"):
    """
    Drop rows with timestamps before min_date when in timestamp mode.
    This prevents garbage timestamps (e.g. year 1700) from distorting polynomial
    trendlines, which would otherwise extrapolate to ±10,000 on the y-axis.
    """
    if xaxis_col == "runtime_hours" or xaxis_col not in dff.columns:
        return dff
    parsed = pd.to_datetime(dff[xaxis_col], format="mixed", errors="coerce", utc=True)
    min_bound = pd.Timestamp(min_date, tz="UTC")
    return dff[parsed.ge(min_bound).fillna(False)]


def _add_degradation_rate_fill(fig, dff, xaxis_col, rate_uv_per_h=3.0, row=None, col=None):
    """
    Add a degradation rate reference line (y = rate_uv_per_h / 1000 * runtime_hours [mV])
    and shade the area above it in red. Works for both runtime and timestamp x-axes.
    rate_uv_per_h: degradation rate in µV/h (e.g. 3.0 means 3 µV/h).
    """
    rt = dff["runtime_hours"].dropna()
    if rt.empty:
        return
    rt_min, rt_max = rt.min(), rt.max()
    x_line = np.array([rt_min, rt_max])
    # Convert µV/h to mV/h (y-axis is in mV)
    y_line = (rate_uv_per_h / 1000.0) * x_line

    if xaxis_col == "runtime_hours":
        x_plot = x_line
    else:
        # Map runtime endpoints to timestamps
        ts = dff.sort_values("runtime_hours")[["runtime_hours", xaxis_col]].dropna()
        if ts.empty:
            return
        ts = ts.copy()
        ts[xaxis_col] = pd.to_datetime(ts[xaxis_col], format="mixed", errors="coerce")
        ts = ts.dropna(subset=[xaxis_col])
        if ts.empty:
            return
        x_plot = np.interp(
            x_line,
            ts["runtime_hours"].values,
            ts[xaxis_col].astype(np.int64).values,
        )
        x_plot = pd.to_datetime(x_plot)

    # Set y-ceiling to 10% above the largest y-value already in the figure
    y_max_data = 0
    for trace in fig.data:
        if trace.y is not None:
            try:
                vals = [v for v in trace.y if v is not None and np.isfinite(v)]
                if vals:
                    y_max_data = max(y_max_data, max(vals))
            except (TypeError, ValueError):
                pass
    row_col = dict(row=row, col=col) if row is not None else {}
    # Reference line
    label = f"{rate_uv_per_h} µV/h"
    fig.add_trace(go.Scatter(
        x=list(x_plot), y=list(y_line),
        mode="lines",
        line=dict(color="rgba(231,76,60,0.6)", width=5, dash="dot"),
        name=label,
        showlegend=True,
        hovertemplate=f"<b>{label} reference</b><br>%{{x}}<br>%{{y:.1f}} mV<extra></extra>",
    ), **row_col)


def get_sample_filters(df, sample_name):
    """
    Given a DataFrame and a sample_name, return number_of_cells and ccm_type.
    """
    if sample_name and "sample_name" in df.columns:
        filtered = df[df["sample_name"] == sample_name]
        num_cells = filtered["number_of_cells"].dropna().unique()
        ccm_types = filtered["ccm_type"].dropna().unique()
        num_cells_val = int(num_cells[0]) if len(num_cells) > 0 else None
        ccm_type_val = ccm_types[0] if len(ccm_types) > 0 else None
        return num_cells_val, ccm_type_val
    return None, None


# ============================================================================
# Pol Curve Decomposition Helper Functions
# ============================================================================
def _extract_jStck_from_col(col):
    """
    Extract jStck float value from column name containing 'jStck-X-YYY' pattern.
    """
    m = re.search(r"jStck-(\d+(?:-\d+)*)", col)
    if m:
        return float(m.group(1).replace("-", "."))
    return None

def extract_polcurve_decomposition_data(iv_data):
    """
    Extract stack-level pol curve decomposition from a single IVnumber's data.
    iv_data: DataFrame with all rows for one IVnumber.
    """
    if iv_data.empty:
        return [], [], [], []

    df_row = iv_data.iloc[0]
    pc_dict, bol_kin_dict, bol_lin_dict = {}, {}, {}

    for col, val in df_row.items():
        if isinstance(val, (list, tuple, np.ndarray)):
            if all(pd.isna(v) for v in np.ravel(val)):
                continue
        elif pd.isna(val):
            continue

        jStck_val = _extract_jStck_from_col(col)
        if jStck_val is None:
            # Fallback for older column naming convention
            if "model_uCellAvg_pc_" in col and "_stack" in col:
                part = col.split("model_uCellAvg_pc_")[1].split("_stack")[0]
                try:
                    jStck_val = float(part.replace("-", "."))
                except ValueError:
                    continue
            else:
                continue

        rounded_jStck = round(jStck_val, 4)
        if "model_uCellAvg_pc_" in col and "BoL" not in col and "_stack" in col:
            pc_dict[rounded_jStck] = float(val)
        elif "model_uCellAvg_BoL-kin_ref_" in col and "_stack" in col:
            bol_kin_dict[rounded_jStck] = float(val)
        elif "model_uCellAvg_BoL-lin_ref_" in col and "_stack" in col:
            bol_lin_dict[rounded_jStck] = float(val)

    if not pc_dict:
        return [], [], [], []

    jStck_list = sorted(pc_dict.keys())
    pc_values = [pc_dict[j] for j in jStck_list]
    bol_kin_ref = [bol_kin_dict.get(j, np.nan) for j in jStck_list]
    bol_lin_ref = [bol_lin_dict.get(j, np.nan) for j in jStck_list]

    return jStck_list, pc_values, bol_kin_ref, bol_lin_ref

def get_valid_iv_list(dff):
    """
    Get sorted DataFrame of IVs that have pol curve decomposition data.
    """
    bol_kin_cols = [
        c for c in dff.columns if "model_uCellAvg_BoL-kin_ref_" in c and "jStck-" in c and "_stack" in c
    ]
    if not bol_kin_cols:
        return pd.DataFrame(columns=["IVnumber", "runtime_hours"])

    # Check for non-null values in any of the decomposition columns
    valid_rows = dff[bol_kin_cols].notna().any(axis=1)
    if not valid_rows.any():
        return pd.DataFrame(columns=["IVnumber", "runtime_hours"])

    # Get unique IV numbers from the rows that have data
    valid_iv_df = dff.loc[valid_rows, ["IVnumber", "runtime_hours"]].drop_duplicates()
    return valid_iv_df.sort_values("runtime_hours").reset_index(drop=True)


# ============================================================================
# Figure Creation
# ============================================================================
def create_fleet_soh_plot(df_soh, dff, sample_name, xaxis_col, plotly_template):
    """
    Create a standard SOH plot for fleet overview.
    """
    dff = _filter_valid_timestamps(dff, xaxis_col)
    fig = make_subplots(
        rows=2, cols=1, 
        row_heights=[0.5, 0.5], 
        vertical_spacing=0.12
    )

    for i, sample in enumerate(dff["sample_name"].unique()):
        sample_data = dff[dff["sample_name"] == sample]
        color = _sample_color(sample, plotly_template=plotly_template)

        # Add kinetic scatter points
        fig.add_trace(go.Scattergl(
            x=sample_data[xaxis_col],
            y=sample_data["soh_kin_stack"],
            mode="markers",
            name=f"{sample}",
            marker=dict(size=8, color=color),
            hovertemplate=f"<b>{sample}</b>: {sample}<br><b>{'Runtime [h]' if xaxis_col == 'runtime_hours' else 'Timestamp'}</b>: %{{x}}<br><b>SOH Kinetic</b>: %{{y:.3f}}<extra></extra>",
            legendgroup=f"{sample}",
            showlegend=True
        ), row=1, col=1)

        # Add kinetic trendline
        if len(sample_data) >= 3:
            x_vals = sample_data[xaxis_col].values
            y_vals = sample_data["soh_kin_stack"].values
            x_smooth, y_smooth, _ = get_polyfit_smooth(x_vals, y_vals, degree=2)
            if x_smooth is not None and y_smooth is not None:
                fig.add_trace(go.Scattergl(
                    x=x_smooth,
                    y=y_smooth,
                    mode="lines",
                    line=dict(color=color, width=2, dash="dash"),
                    hoverinfo="skip",
                    legendgroup=f"{sample}",
                    showlegend=False
                ), row=1, col=1)

        # Add linear scatter points
        fig.add_trace(go.Scattergl(
            x=sample_data[xaxis_col],
            y=sample_data["soh_lin_stack"],
            mode="markers",
            name=f"{sample}",
            marker=dict(size=8, color=color),
            hovertemplate=f"<b>{sample}</b>: {sample}<br><b>{'Runtime [h]' if xaxis_col == 'runtime_hours' else 'Timestamp'}</b>: %{{x}}<br><b>SOH Linear</b>: %{{y:.3f}}<extra></extra>",
            legendgroup=f"{sample}",
            showlegend=False
        ), row=2, col=1)

        # Add linear trendline
        if len(sample_data) >= 3:
            x_vals = sample_data[xaxis_col].values
            y_vals = sample_data["soh_lin_stack"].values
            x_smooth, y_smooth, _ = get_polyfit_smooth(x_vals, y_vals, degree=2)
            if x_smooth is not None and y_smooth is not None:
                fig.add_trace(go.Scattergl(
                    x=x_smooth,
                    y=y_smooth,
                    mode="lines",
                    line=dict(color=color, width=2, dash="dash"),
                    hoverinfo="skip",
                    legendgroup=f"{sample}",
                    showlegend=False
                ), row=2, col=1)

    xaxis_label = "Runtime [h]" if xaxis_col == "runtime_hours" else "Timestamp"
    title_suffix = "Runtime Hours" if xaxis_col == "runtime_hours" else "Timestamp"
    fig.update_layout(
        template=plotly_template,
        showlegend=len(dff["sample_name"].unique()) > 1,
        title=dict(text=f"SOH over {title_suffix}", x=0.5, xanchor="center"),
        margin=dict(l=40, r=20, t=70, b=40),
        legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1, font=dict(size=10)),
        autosize=True,
        height=None,
        width=None,
    )
    if sample_name:
        fig.add_annotation(
            text=sample_name, xref="paper", yref="paper",
            x=0.5, y=1.04, showarrow=False,
            font=dict(size=11, color="gray"), xanchor="center", yanchor="bottom",
        )
    fig.update_yaxes(title_text="SOH Kinetic [-]", row=1, col=1)
    fig.update_yaxes(title_text="SOH Linear [mΩ·cm²]", row=2, col=1)
    fig.update_xaxes(title_text=xaxis_label, row=2, col=1)
    return fig

def create_lin_vs_kin_plot(dff, df_soh, plotly_template, sample_name):
    fig_lin_vs_lin = go.Figure().update_layout(template=plotly_template)
    has_runtime_colorbar = bool(sample_name and sample_name in dff["sample_name"].unique())
    title_x = 0.39 if has_runtime_colorbar else 0.5

    if sample_name and sample_name in dff["sample_name"].unique():
        sample_data = dff[dff["sample_name"] == sample_name]
        
        # Plot the individual data points, colored by runtime
        runtime_vals = sample_data["runtime_hours"]
        fig_lin_vs_lin.add_trace(go.Scattergl(
            x=sample_data["soh_lin_stack"],
            y=sample_data["soh_kin_stack"],
            mode="markers",
            marker=dict(
                size=6, color=runtime_vals, colorscale='Turbo',
                colorbar=dict(
                    title=dict(text="Runtime [h]", side="right"),
                    thickness=20,
                    len=0.82,
                    y=0.5,
                    yanchor="middle",
                    x=1.02,
                    xanchor="left",
                )
            ),
            hovertemplate="<b>Sample</b>: "+sample_name+"<br>SOH Linear: %{x:.3f}<br>SOH Kinetic: %{y:.3f}<br>Runtime: %{marker.color:.1f}h<extra></extra>",
            showlegend=False
        ))
        # Plot the highlighted trendline for the selected sample
        x_fit, y_fit, _ = get_polyfit_smooth(sample_data["soh_lin_stack"], sample_data["soh_kin_stack"])
        if x_fit is not None:
            selected_color = _sample_color(sample_name, plotly_template=plotly_template)
            fig_lin_vs_lin.add_trace(go.Scattergl(
                x=x_fit, y=y_fit, mode="lines",
                line=dict(color=selected_color, width=3, dash="dash"), # Thicker line
                hoverinfo="skip", showlegend=False
            ))
        title = "SOH Trendline"
    else: # no sample name selected
        for other_sample in dff["sample_name"].unique():
            sample_data = dff[dff["sample_name"] == other_sample]
            color = _sample_color(other_sample, plotly_template=plotly_template)
            
            x_fit, y_fit, _ = get_polyfit_smooth(sample_data["soh_lin_stack"], sample_data["soh_kin_stack"])
            
            if x_fit is not None:
                fig_lin_vs_lin.add_trace(go.Scattergl(
                    x=x_fit, y=y_fit, mode="lines",
                    line=dict(color=color, width=2, dash="dash"),
                    name=other_sample,
                    hovertemplate="<b>Sample</b>: "+other_sample+"<extra></extra>"
                ))
        title = "SOH Trendlines"
        
    fig_lin_vs_lin.update_layout(
        template=plotly_template,
        title=dict(text=title, x=title_x, xanchor="center"),
        margin=dict(l=40, r=20, t=80, b=40),
        autosize=True,
        height=None,
        width=None,
        xaxis_title="SOH Linear [mΩ·cm²]",
        yaxis_title="SOH Kinetic [-]",
        showlegend=False
    )
    if sample_name:
        fig_lin_vs_lin.add_annotation(
            text=sample_name,
            xref="paper",
            yref="paper",
            x=title_x,
            y=1.04,
            showarrow=False,
            font=dict(size=11, color="gray"),
            xanchor="center",
            yanchor="bottom",
        )
    return fig_lin_vs_lin

def create_polcurve_decomp_plot(dff, valid_ivs, slider_value, plotly_template, sample_name):
    fig_soh_split = go.Figure().update_layout(template=plotly_template)
    iv_0, iv_1 = slider_value[0], slider_value[1]
    row_0 = valid_ivs[valid_ivs["IVnumber"] == iv_0]
    row_1 = valid_ivs[valid_ivs["IVnumber"] == iv_1]
    rt_0 = row_0["runtime_hours"].iloc[0] if not row_0.empty else None
    rt_1 = row_1["runtime_hours"].iloc[0] if not row_1.empty else None

    if iv_0 == iv_1 or rt_0 is None or rt_1 is None:
        text = "Please select two different IVs for decomposition." if iv_0 == iv_1 else "Selected IVs do not have SOH information."
        fig_soh_split.update_layout(annotations=[dict(
            text=text,
            showarrow=False, xref="paper", yref="paper", x=0.5, y=0.5,
            font=dict(size=14, color="#95a5a6")
        )])
        return fig_soh_split

    # Extract decomposition data for both IVs
    iv_data_0 = dff[dff["IVnumber"] == iv_0]
    iv_data_1 = dff[dff["IVnumber"] == iv_1]
    if iv_data_0.empty or iv_data_1.empty:
        return fig_soh_split

    jStck_0, pc_0, kin_0, lin_0 = extract_polcurve_decomposition_data(iv_data_0)
    jStck_1, pc_1, kin_1, lin_1 = extract_polcurve_decomposition_data(iv_data_1)

    if not jStck_0 or not jStck_1:
        return fig_soh_split

    # Align to common jStck points (use IV0 as anchor)
    pc_0 = np.array(pc_0)
    pc_1 = np.array(pc_1)
    kin_0 = np.array(kin_0)
    lin_0 = np.array(lin_0)
    kin_1 = np.array(kin_1)
    lin_1 = np.array(lin_1)

    # Compute deltas for each IV
    kin_delta_0 = kin_0 - pc_0
    lin_delta_0 = lin_0 - pc_0
    kin_delta_1 = kin_1 - pc_1
    lin_delta_1 = lin_1 - pc_1

    # Difference in deltas between IV1 and IV0
    kin_delta_diff = kin_delta_1 - kin_delta_0
    lin_delta_diff = lin_delta_1 - lin_delta_0

    # Pol curve for IV0 (early)
    fig_soh_split.add_trace(go.Scatter(
        x=jStck_0, y=pc_0.tolist(),
        mode="markers+lines",
        marker=dict(size=6, color="#345bdb"),
        line=dict(color="#345bdb", width=2),
        name=f"IV {int(iv_0)} @ {rt_0:.0f}h",
        hovertemplate="<b>Current Density</b>: %{x:.3f}<br><b>Cell Voltage</b>: %{y:.4f}<extra></extra>"
    ))
    # Pol curve for IV1 (late)
    fig_soh_split.add_trace(go.Scatter(
        x=jStck_1, y=pc_1.tolist(),
        mode="markers+lines",
        marker=dict(size=6, color="#ce6b0f"),
        line=dict(color="#ce6b0f", width=2),
        name=f"IV {int(iv_1)} @ {rt_1:.0f}h",
        hovertemplate="<b>Current Density</b>: %{x:.3f}<br><b>Cell Voltage</b>: %{y:.4f}<extra></extra>"
    ))
    # Fill: linear contribution change (green, alpha=0.3)
    lower_lin = (pc_0 - lin_delta_diff).tolist()
    fig_soh_split.add_trace(go.Scatter(
        x=jStck_0 + jStck_0[::-1],
        y=pc_0.tolist() + lower_lin[::-1],
        fill="toself",
        fillcolor="rgba(46,204,113,0.3)",
        line=dict(color="rgba(0,0,0,0)"),
        name="lin. contribution change",
        hoverinfo="skip"
    ))
    # Dashed line between the two filled areas
    fig_soh_split.add_trace(go.Scatter(
        x=jStck_0, y=lower_lin,
        mode="lines",
        line=dict(color="gray", width=2, dash="dash"),
        name="lin/kin boundary",
        hoverinfo="skip",
        showlegend=False
    ))
    # Fill: kinetic contribution change (purple, alpha=0.3)
    upper_kin = lower_lin
    lower_kin = (pc_0 - lin_delta_diff - kin_delta_diff).tolist()
    fig_soh_split.add_trace(go.Scatter(
        x=jStck_0 + jStck_0[::-1],
        y=upper_kin + lower_kin[::-1],
        fill="toself",
        fillcolor="rgba(155,89,182,0.3)",
        line=dict(color="rgba(0,0,0,0)"),
        name="kin. contribution change",
        hoverinfo="skip"
    ))

    # Add arrows matching the fill regions (relative to total curve)
    annotations = []
    for j_idx, j_val in enumerate(jStck_0):
        # Linear arrow (green): from pc_0[j] to pc_0[j] - lin_delta_diff[j]
        start_y_lin = float(pc_0[j_idx])
        end_y_lin = float(pc_0[j_idx] - lin_delta_diff[j_idx])
        if abs(end_y_lin - start_y_lin) > 1e-7:
            annotations.append(dict(
                x=j_val, y=end_y_lin,
                ax=j_val, ay=start_y_lin,
                xref="x", yref="y", axref="x", ayref="y",
                showarrow=True, arrowhead=1, arrowsize=1, arrowwidth=2,
                arrowcolor="green",
                standoff=0, startstandoff=0,
            ))
        # Kinetic arrow (purple): from (pc_0[j] - lin_delta_diff[j]) to (pc_0[j] - lin_delta_diff[j] - kin_delta_diff[j])
        start_y_kin = float(pc_0[j_idx] - lin_delta_diff[j_idx])
        end_y_kin = float(pc_0[j_idx] - lin_delta_diff[j_idx] - kin_delta_diff[j_idx])
        if abs(end_y_kin - start_y_kin) > 1e-7:
            annotations.append(dict(
                x=j_val, y=end_y_kin,
                ax=j_val, ay=start_y_kin,
                xref="x", yref="y", axref="x", ayref="y",
                showarrow=True, arrowhead=1, arrowsize=1, arrowwidth=2,
                arrowcolor="purple",
                standoff=0, startstandoff=0
            ))

    all_annotations = list(annotations)
    if sample_name:
        all_annotations.append(dict(
            text=sample_name, xref="paper", yref="paper",
            x=0.5, y=1.04, showarrow=False,
            font=dict(size=11, color="gray"), xanchor="center", yanchor="bottom",
        ))
    fig_soh_split.update_layout(
        template=plotly_template,
        title=dict(text="Pol Curve Change (@Ref OpCons) Related to Ageing", x=0.5, xanchor="center"),
        xaxis_title="Current Density [A/cm²]",
        yaxis_title="Cell Voltage [V]",
        margin=dict(l=40, r=40, t=130, b=40),
        legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02),
        annotations=all_annotations,
        height=None
    )
    return fig_soh_split

def create_overpotential_plots(df_soh, dff, xaxis_col, theme_data, sample_name):
    plotly_template = get_plotly_template(theme_data)
    dff = _filter_valid_timestamps(dff, xaxis_col)
    fig = make_subplots(rows=3, cols=1, row_heights=[0.33, 0.33, 0.33], vertical_spacing=0.08)

    col_bol_lin = "model_uCellAvg_BoL-lin_ref_jStck-3-0pAndeOut-2-5pCtdeOut-40tAndeIn-70vfAndeIn-5-2delta_Rohm-0_stack"
    col_bol_kin = "model_uCellAvg_BoL-kin_ref_jStck-3-0pAndeOut-2-5pCtdeOut-40tAndeIn-70vfAndeIn-5-2ECSA-1_stack"
    col_pc = "model_uCellAvg_pc_3-0_stack"

    required_cols = {col_bol_lin, col_bol_kin, col_pc}
    if not required_cols.issubset(dff.columns):
        fig.update_layout(template=plotly_template)
        return fig, {}

    fit_coeffs = {}  # {sample_name: {"kin": coeffs, "lin": coeffs}}

    for sample in dff["sample_name"].unique():
        sample_data = dff[dff["sample_name"] == sample]
        color = _sample_color(sample, theme_data=theme_data)

        eta_tot = 1000 * (-sample_data[col_bol_lin] - sample_data[col_bol_kin] + 2*sample_data[col_pc])
        eta_kin = 1000 * (-sample_data[col_bol_kin] + sample_data[col_pc])
        eta_lin = 1000 * (-sample_data[col_bol_lin] + sample_data[col_pc])

        fig.add_trace(go.Scattergl(
            x=sample_data[xaxis_col],
            y=eta_tot,
            mode="markers", #"lines+markers",
            marker=dict(size=6, color=color),
            line=dict(color=color),
            hovertemplate="<b>Sample</b>: "+sample+"<br>Runtime/Date: %{x}<br>Overpotential: %{y:.3f}[mV]<extra></extra>",
            legendgroup=sample,
            showlegend=True,
            name=sample,
        ), row=1, col=1)

        if len(sample_data) >= 3:
            x_vals = sample_data[xaxis_col].values
            y_vals = eta_tot
            x_smooth, y_smooth, _ = get_polyfit_smooth(x_vals, y_vals, degree=2)
            if x_smooth is not None and y_smooth is not None:
                fig.add_trace(go.Scattergl(
                    x=x_smooth,
                    y=y_smooth,
                    mode="lines",
                    line=dict(color=color, width=2, dash="dash"),
                    hoverinfo="skip",
                    legendgroup=f"{sample}",
                    showlegend=False
                ), row=1, col=1)

        fig.add_trace(go.Scattergl(
            x=sample_data[xaxis_col],
            y=eta_lin, # this gives the overpotential rel. to linear contribution
            mode="markers", #"lines+markers",
            marker=dict(size=6, color=color, symbol="diamond"),
            line=dict(color=color),
            hovertemplate="<b>Sample</b>: "+sample+"<br>Runtime/Date: %{x}<br>Overpotential lin.: %{y:.3f}[mV]<extra></extra>",
            legendgroup=sample,
            showlegend=False,
            name=sample,
        ), row=2, col=1)

        if len(sample_data) >= 3:
            x_vals = sample_data[xaxis_col].values
            y_vals = eta_lin
            x_smooth, y_smooth, _ = get_polyfit_smooth(x_vals, y_vals, degree=2)
            # Always fit coefficients against runtime_hours for the parametric lin-vs-kin trendline
            _, _, coeffs_kin = get_polyfit_smooth(sample_data["runtime_hours"].values, y_vals, degree=2)
            if coeffs_kin is not None:
                fit_coeffs.setdefault(sample, {})["kin"] = coeffs_kin
            if x_smooth is not None and y_smooth is not None:
                fig.add_trace(go.Scattergl(
                    x=x_smooth,
                    y=y_smooth,
                    mode="lines",
                    line=dict(color=color, width=2, dash="dash"),
                    hoverinfo="skip",
                    legendgroup=f"{sample}",
                    showlegend=False
                ), row=2, col=1)

        fig.add_trace(go.Scattergl(
            x=sample_data[xaxis_col],
            y=eta_kin, # this gives the overpotential rel. to kinetic contribution
            mode="markers", #"lines+markers",
            marker=dict(size=6, color=color, symbol="square"),
            line=dict(color=color),
            hovertemplate="<b>Sample</b>: "+sample+"<br>Runtime/Date: %{x}<br>Overpotential kin.: %{y:.3f}[mV]<extra></extra>",
            legendgroup=sample,
            showlegend=False,
            name=sample,
        ), row=3, col=1)

        if len(sample_data) >= 3:
            x_vals = sample_data[xaxis_col].values
            y_vals = eta_kin
            x_smooth, y_smooth, _ = get_polyfit_smooth(x_vals, y_vals, degree=2)
            # Always fit coefficients against runtime_hours for the parametric lin-vs-kin trendline
            _, _, coeffs_lin = get_polyfit_smooth(sample_data["runtime_hours"].values, y_vals, degree=2)
            if coeffs_lin is not None:
                fit_coeffs.setdefault(sample, {})["lin"] = coeffs_lin
            if x_smooth is not None and y_smooth is not None:
                fig.add_trace(go.Scattergl(
                    x=x_smooth,
                    y=y_smooth,
                    mode="lines",
                    line=dict(color=color, width=2, dash="dash"),
                    hoverinfo="skip",
                    legendgroup=f"{sample}",
                    showlegend=False
                ), row=3, col=1)

    xaxis_label = "Runtime [h]" if xaxis_col == "runtime_hours" else "Timestamp"
    fig.update_layout(
        template=plotly_template,
        title=dict(text="Additional Overpotential (due to Ageing) over Time (@Ref OpCons)", x=0.5, xanchor="center"),
        margin=dict(l=40, r=20, t=110, b=40),
        autosize=True,
        height=None,
        width=None,
        showlegend=True,
        legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1, font=dict(size=10)),
    )
    if sample_name:
        fig.add_annotation(
            text=sample_name, xref="paper", yref="paper",
            x=0.5, y=1.04, showarrow=False,
            font=dict(size=11, color="gray"), xanchor="center", yanchor="bottom",
        )
    # Add 3 mV/h degradation reference line + shaded area (row 1 = Δη_tot)
    _add_degradation_rate_fill(fig, dff, xaxis_col, rate_uv_per_h=3.0, row=1, col=1)

    fig.update_yaxes(title_text="Δη<sub>tot</sub> [mV]", row=1, col=1)
    fig.update_yaxes(title_text="Δη<sub>lin</sub> [mV]", row=2, col=1)
    fig.update_yaxes(title_text="Δη<sub>kin</sub> [mV]", row=3, col=1)
    fig.update_xaxes(title_text="", row=1, col=1)
    fig.update_xaxes(title_text="", row=2, col=1)
    fig.update_xaxes(title_text=xaxis_label, row=3, col=1)

    return fig, fit_coeffs

def create_overpotential_lin_vs_kin_plot(dff, df_soh, plotly_template, sample_name, fit_coeffs=None):
    fig_lin_vs_lin = go.Figure().update_layout(template=plotly_template)
    has_runtime_colorbar = bool(sample_name and sample_name in dff["sample_name"].unique())
    title_x = 0.46 if has_runtime_colorbar else 0.5

    col_bol_lin = "model_uCellAvg_BoL-lin_ref_jStck-3-0pAndeOut-2-5pCtdeOut-40tAndeIn-70vfAndeIn-5-2delta_Rohm-0_stack"
    col_bol_kin = "model_uCellAvg_BoL-kin_ref_jStck-3-0pAndeOut-2-5pCtdeOut-40tAndeIn-70vfAndeIn-5-2ECSA-1_stack"
    col_pc = "model_uCellAvg_pc_3-0_stack"

    if sample_name and sample_name in dff["sample_name"].unique():
        sample_data = dff[dff["sample_name"] == sample_name]
        eta_kin = 1000 * (-sample_data[col_bol_kin] + sample_data[col_pc])
        eta_lin = 1000 * (-sample_data[col_bol_lin] + sample_data[col_pc])
        selected_color = _sample_color(sample_name, plotly_template=plotly_template)
        runtime_vals = sample_data["runtime_hours"]

        # Color selected-sample points by runtime to show temporal progression.
        fig_lin_vs_lin.add_trace(go.Scattergl(
            x=eta_kin,
            y=eta_lin,
            mode="markers",
            marker=dict(
                size=7,
                color=runtime_vals,
                colorscale="Turbo",
                colorbar=dict(
                    title=dict(text="Runtime [h]", side="right"),
                    thickness=18,
                    len=0.82,
                    y=0.5,
                    yanchor="middle",
                    x=1.02,
                    xanchor="left",
                ),
            ),
            hovertemplate="<b>Sample</b>: "+sample_name+"<br>Kinetic: %{x:.3f} mV<br>Linear: %{y:.3f} mV<br>Runtime: %{customdata:.1f}h<extra></extra>",
            customdata=runtime_vals,
            showlegend=False
        ))

        # Plot parametric trendline from fit coefficients (kin(t) vs lin(t)).
        # Fallback to direct fit on selected sample data if coefficients were not provided.
        sc = fit_coeffs.get(sample_name) if fit_coeffs else None
        if (not sc or "kin" not in sc or "lin" not in sc) and len(sample_data) >= 3:
            runtime_vals_np = sample_data["runtime_hours"].values
            if np.isfinite(runtime_vals_np).sum() >= 3:
                _, _, coeffs_lin_runtime = get_polyfit_smooth(runtime_vals_np, eta_kin.values, degree=2)
                _, _, coeffs_kin_runtime = get_polyfit_smooth(runtime_vals_np, eta_lin.values, degree=2)
                if coeffs_lin_runtime is not None and coeffs_kin_runtime is not None:
                    sc = {"lin": coeffs_lin_runtime, "kin": coeffs_kin_runtime}

        if sc and "kin" in sc and "lin" in sc:
            t_vals = sample_data["runtime_hours"].values
            finite_mask = np.isfinite(t_vals)
            if finite_mask.sum() >= 2:
                t_min = np.nanmin(t_vals[finite_mask])
                t_max = np.nanmax(t_vals[finite_mask])
                t_smooth = np.linspace(t_min, t_max, 200)
                x_curve = np.polyval(sc["lin"], t_smooth)
                y_curve = np.polyval(sc["kin"], t_smooth)
                fig_lin_vs_lin.add_trace(go.Scattergl(
                    x=x_curve, y=y_curve, mode="lines",
                    line=dict(color=selected_color, width=2, dash="dash"),
                    hoverinfo="skip", showlegend=False
                ))
                _add_curve_arrowhead(fig_lin_vs_lin, x_curve, y_curve, selected_color, line_width=2)
        title = "Overpotential Trendlines"
    else:  # no sample name selected
        for other_sample in dff["sample_name"].unique():
            sample_data = dff[dff["sample_name"] == other_sample]
            color = _sample_color(other_sample, plotly_template=plotly_template)
            eta_kin = 1000 * (-sample_data[col_bol_kin] + sample_data[col_pc])
            eta_lin = 1000 * (-sample_data[col_bol_lin] + sample_data[col_pc])

            # Use fit coefficients for parametric curve if available.
            if fit_coeffs and other_sample in fit_coeffs:
                sc = fit_coeffs[other_sample]
                if "kin" in sc and "lin" in sc:
                    t_vals = sample_data["runtime_hours"].values
                    t_smooth = np.linspace(np.nanmin(t_vals), np.nanmax(t_vals), 200)
                    x_curve = np.polyval(sc["lin"], t_smooth)
                    y_curve = np.polyval(sc["kin"], t_smooth)
                    fig_lin_vs_lin.add_trace(go.Scattergl(
                        x=x_curve, y=y_curve, mode="lines",
                        line=dict(color=color, width=2, dash="dash"),
                        name=other_sample,
                        hovertemplate="<b>Sample</b>: "+other_sample+"<extra></extra>"
                    ))
                    _add_curve_arrowhead(fig_lin_vs_lin, x_curve, y_curve, color, line_width=2)
            else:
                # Fallback: fit directly on kin vs lin.
                x_fit, y_fit, _ = get_polyfit_smooth(eta_kin, eta_lin)
                if x_fit is not None and len(x_fit) > 0 and len(y_fit) > 0:
                    fig_lin_vs_lin.add_trace(go.Scattergl(
                        x=x_fit, y=y_fit, mode="lines",
                        line=dict(color=color, width=2, dash="dash"),
                        name=other_sample,
                        hovertemplate="<b>Sample</b>: "+other_sample+"<extra></extra>"
                    ))
                    _add_curve_arrowhead(fig_lin_vs_lin, x_fit, y_fit, color, line_width=2)
        title = "Overpotential Trendlines"

    fig_lin_vs_lin.update_layout(
        template=plotly_template,
        title=dict(text=title, x=title_x, xanchor="center"),
        margin=dict(l=40, r=20, t=110, b=40),
        autosize=True,
        height=None,
        width=None,
        xaxis_title="Δη<sub>kin</sub> [mV]",
        yaxis_title="Δη<sub>lin</sub> [mV]",
        showlegend=False,
    )
    if sample_name:
        fig_lin_vs_lin.add_annotation(
            text=sample_name, xref="paper", yref="paper",
            x=title_x, y=1.04, showarrow=False,
            font=dict(size=11, color="gray"), xanchor="center", yanchor="bottom",
        )
    return fig_lin_vs_lin

def create_overpotential_plot_all_in_one(df_soh, dff, xaxis_col, theme_data, sample_name, slider_value=None, valid_ivs=None):
    plotly_template = get_plotly_template(theme_data)
    dff = _filter_valid_timestamps(dff, xaxis_col)
    fig = go.Figure().update_layout(template=plotly_template)

    col_bol_lin = "model_uCellAvg_BoL-lin_ref_jStck-3-0pAndeOut-2-5pCtdeOut-40tAndeIn-70vfAndeIn-5-2delta_Rohm-0_stack"
    col_bol_kin = "model_uCellAvg_BoL-kin_ref_jStck-3-0pAndeOut-2-5pCtdeOut-40tAndeIn-70vfAndeIn-5-2ECSA-1_stack"
    col_pc = "model_uCellAvg_pc_3-0_stack"

    required_cols = {col_bol_lin, col_bol_kin, col_pc}
    if not required_cols.issubset(dff.columns):
        fig.update_layout(template=plotly_template)
        return fig, {}

    fit_coeffs = {}  # {sample_name: {"kin": coeffs, "lin": coeffs}}

    for sample in dff["sample_name"].unique():
        sample_data = dff[dff["sample_name"] == sample]
        color = _sample_color(sample, theme_data=theme_data)

        eta_tot = 1000 * (-sample_data[col_bol_lin] - sample_data[col_bol_kin] + 2*sample_data[col_pc])
        eta_kin = 1000 * (-sample_data[col_bol_kin] + sample_data[col_pc])
        eta_lin = 1000 * (-sample_data[col_bol_lin] + sample_data[col_pc])

        fig.add_trace(go.Scattergl(
            x=sample_data[xaxis_col],
            y=eta_tot,
            mode="markers",
            marker=dict(size=6, color=color),
            hovertemplate="<b>Sample</b>: "+sample+"<br>Runtime/Date: %{x}<br>Overpotential: %{y:.3f}[mV]<extra></extra>",
            legendgroup=sample,
            showlegend=False,
            name="total",
        ))
        if len(sample_data) >= 3:
            x_vals = sample_data[xaxis_col].values
            y_vals = eta_tot
            x_smooth, y_smooth, _ = get_polyfit_smooth(x_vals, y_vals, degree=2)
            if x_smooth is not None and y_smooth is not None:
                fig.add_trace(go.Scattergl(
                    x=x_smooth,
                    y=y_smooth,
                    mode="lines",
                    line=dict(color=color, width=2, dash="dash"),
                    hoverinfo="skip",
                    legendgroup=f"{sample}",
                    showlegend=False
                ))

        color_lighter = adjust_color_brightness(color, 1.5)
        color_darker = adjust_color_brightness(color, 0.5)

        fig.add_trace(go.Scattergl(
            x=sample_data[xaxis_col],
            y=eta_lin,
            mode="markers",
            marker=dict(size=6, color=color_lighter, symbol="square"),
            line=dict(color=color_lighter),
            hovertemplate="<b>Sample</b>: "+sample+"<br>Runtime/Date: %{x}<br>Overpotential: %{y:.3f}[mV]<extra></extra>",
            legendgroup=sample,
            showlegend=False,
            name="linear",
        ))
        if len(sample_data) >= 3:
            x_vals = sample_data[xaxis_col].values
            y_vals = eta_lin
            x_smooth, y_smooth, _ = get_polyfit_smooth(x_vals, y_vals, degree=2)
            if x_smooth is not None and y_smooth is not None:
                fig.add_trace(go.Scattergl(
                    x=x_smooth,
                    y=y_smooth,
                    mode="lines",
                    line=dict(color=color_lighter, width=2, dash="dash"),
                    hoverinfo="skip",
                    legendgroup=f"{sample}",
                    showlegend=False
                ))

        fig.add_trace(go.Scattergl(
            x=sample_data[xaxis_col],
            y=eta_kin,
            mode="markers",
            marker=dict(size=6, color=color_darker, symbol="diamond"),
            line=dict(color=color_darker),
            hovertemplate="<b>Sample</b>: "+sample+"<br>Runtime/Date: %{x}<br>Overpotential: %{y:.3f}[mV]<extra></extra>",
            legendgroup=sample,
            showlegend=False,
            name="kinetic",
        ))
        if len(sample_data) >= 3:
            x_vals = sample_data[xaxis_col].values
            y_vals = eta_kin
            x_smooth, y_smooth, _ = get_polyfit_smooth(x_vals, y_vals, degree=2)
            if x_smooth is not None and y_smooth is not None:
                fig.add_trace(go.Scattergl(
                    x=x_smooth,
                    y=y_smooth,
                    mode="lines",
                    line=dict(color=color_darker, width=2, dash="dash"),
                    hoverinfo="skip",
                    legendgroup=f"{sample}",
                    showlegend=False
                ))

    # Add traces for the marker-type legend (symbol key)
    fig.add_trace(go.Scattergl(
        x=[None], y=[None], mode="markers",
        marker=dict(size=8, color=color, symbol="circle"),
        name="Δη total", legendgroup="_legend_total", showlegend=True,
    ))
    fig.add_trace(go.Scattergl(
        x=[None], y=[None], mode="markers",
        marker=dict(size=8, color=color_lighter, symbol="square"),
        name="Δη linear", legendgroup="_legend_lin", showlegend=True,
    ))
    fig.add_trace(go.Scattergl(
        x=[None], y=[None], mode="markers",
        marker=dict(size=8, color=color_darker, symbol="diamond"),
        name="Δη kinetic", legendgroup="_legend_kin", showlegend=True,
    ))

    xaxis_label = "Runtime [h]" if xaxis_col == "runtime_hours" else "Timestamp"
    fig.update_layout(
        template=plotly_template,
        title=dict(text="Additional Overpotential (due to Ageing) over Time (@Ref OpCons)", x=0.5, xanchor="center"),
        margin=dict(l=40, r=20, t=130, b=40),
        autosize=True,
        height=None,
        width=None,
        showlegend=True,
        legend=dict(
            orientation="v", yanchor="top", y=0.98, xanchor="left", x=0.01,
            font=dict(size=10),
            bgcolor="rgba(44,48,53,0.7)" if theme_data == "dark" else "rgba(255,255,255,0.7)",
            borderwidth=0,
        ),
    )
    if sample_name:
        fig.add_annotation(
            text=sample_name, xref="paper", yref="paper",
            x=0.5, y=1.04, showarrow=False,
            font=dict(size=11, color="gray"), xanchor="center", yanchor="bottom",
        )
    # Add 3 mV/h degradation reference line + shaded area
    _add_degradation_rate_fill(fig, dff, xaxis_col, rate_uv_per_h=3.0)

    fig.update_yaxes(title_text="Δη [mV]")
    fig.update_xaxes(title_text=xaxis_label)

    # Add vertical lines for selected slider IV values
    if slider_value and valid_ivs is not None and not valid_ivs.empty:
        colors = ["#345bdb", "#ce6b0f"]
        for i, iv_num in enumerate(slider_value[:2]):
            iv_row = valid_ivs[valid_ivs["IVnumber"] == iv_num]
            if not iv_row.empty:
                rt = iv_row["runtime_hours"].iloc[0]
                if xaxis_col == "runtime_hours":
                    x_val = rt
                else:
                    matched = dff[dff["IVnumber"] == iv_num]
                    if not matched.empty:
                        x_val = matched[xaxis_col].iloc[0]
                    else:
                        continue
                fig.add_vline(
                    x=x_val, line_dash="dash", line_color=colors[i % 2], line_width=2,
                )
                fig.add_annotation(
                    x=x_val, y=1.02, yref="paper", showarrow=False,
                    text=f"IV {int(iv_num)} @ {rt:.0f}h",
                    font=dict(size=10, color=colors[i % 2]),
                    xanchor="left" if i == 0 else "right",
                )

    return fig, fit_coeffs

def create_cell_based_soh_time_plot(dff, xaxis_col, click_data, theme_data, sample_name):
    plotly_template = get_plotly_template(theme_data)

    col_bol_lin_cells = "model_uCellAvg_BoL-lin_ref_jStck-3-0pAndeOut-2-5pCtdeOut-40tAndeIn-70vfAndeIn-5-2delta_Rohm-0_cells"
    col_bol_kin_cells = "model_uCellAvg_BoL-kin_ref_jStck-3-0pAndeOut-2-5pCtdeOut-40tAndeIn-70vfAndeIn-5-2ECSA-1_cells"
    col_pc = "model_uCellAvg_pc_3-0_stack"

    has_required = {col_bol_lin_cells, col_bol_kin_cells, col_pc}.issubset(dff.columns)

    num_cells = None
    if "number_of_cells" in dff.columns:
        num_cells = int(dff["number_of_cells"].iloc[0]) if len(dff) > 0 and pd.notna(dff["number_of_cells"].iloc[0]) else None
    if num_cells is None and has_required:
        max_len = dff[col_bol_kin_cells].apply(get_array_len).max()
        num_cells = int(max_len) if max_len > 0 else None
    if num_cells is None or num_cells == 0 or not has_required:
        fig = go.Figure().update_layout(template=plotly_template)
        return fig

    dff = _filter_valid_timestamps(dff, xaxis_col)
    fig_soh_cells_time = make_subplots(
        rows=3, cols=1,
        row_heights=[0.33, 0.33, 0.33],
        vertical_spacing=0.08
    )

    # Add cell-level overpotential traces to 3 subplots
    cell_palette = _get_cell_palette(theme_data=theme_data)
    for cell_idx in range(num_cells):
        color = cell_palette[cell_idx % len(cell_palette)]
        bol_lin_vals = dff[col_bol_lin_cells].apply(lambda arr, ci=cell_idx: get_array_element(arr, ci))
        bol_kin_vals = dff[col_bol_kin_cells].apply(lambda arr, ci=cell_idx: get_array_element(arr, ci))
        pc_vals = dff[col_pc]
        x_values = dff[xaxis_col]

        eta_tot = 1000 * (-bol_lin_vals - bol_kin_vals + 2 * pc_vals)
        eta_kin = 1000 * (-bol_kin_vals + pc_vals)
        eta_lin = 1000 * (-bol_lin_vals + pc_vals)

        custom_data = np.stack([np.full(len(dff), cell_idx + 1), dff["IVnumber"].values], axis=-1) if "IVnumber" in dff.columns else None

        for row_num, y_vals, symbol, label in [
            (1, eta_tot, "circle", "Δη_tot"),
            (2, eta_lin, "diamond", "Δη_lin"),
            (3, eta_kin, "square", "Δη_kin"),
        ]:
            fig_soh_cells_time.add_trace(go.Scattergl(
                x=x_values, y=y_vals,
                mode="lines+markers",
                name=f"Cell {cell_idx + 1}",
                marker=dict(size=5, color=color, symbol=symbol),
                line=dict(color=color),
                legendgroup=f"Cell {cell_idx + 1}",
                showlegend=(row_num == 1),
                customdata=custom_data,
                hovertemplate=(
                    f"<b>Cell {cell_idx + 1}</b><br>"
                    "<b>Runtime</b>: %{x:.1f}h<br>"
                    f"<b>{label}</b>: %{{y:.3f}} mV<extra></extra>"
                ),
            ), row=row_num, col=1)

    ctx = dash.callback_context
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]
    if triggered_id in ['soh-table', 'soh-xaxis-filter']:
        click_data = None

    if click_data:
        point = click_data["points"][0]
        selected_time = point["x"]
        clicked_cell = point['curveNumber'] % num_cells + 1 if 'curveNumber' in point else None

        if xaxis_col == 'runtime_hours':
            time_diff = abs(dff[xaxis_col] - selected_time)
            closest_idx = time_diff.idxmin()
            closest_row = dff.loc[closest_idx]
        else:
            closest_row_df = dff[dff[xaxis_col] == selected_time]
            closest_row = closest_row_df.iloc[0] if not closest_row_df.empty else None

        if closest_row is not None:
            actual_time = closest_row[xaxis_col]
            for row_num in [1, 2, 3]:
                fig_soh_cells_time.add_vline(x=actual_time, line_dash="dash", line_color="#e74c3c", line_width=2, row=row_num, col=1)

            if clicked_cell is not None:
                cell_idx = clicked_cell - 1
                bol_lin_val = get_array_element(closest_row[col_bol_lin_cells], cell_idx)
                bol_kin_val = get_array_element(closest_row[col_bol_kin_cells], cell_idx)
                pc_val = closest_row[col_pc]

                if bol_lin_val is not None and bol_kin_val is not None and pd.notna(bol_lin_val) and pd.notna(bol_kin_val) and pd.notna(pc_val):
                    highlight_vals = [
                        (1, 1000 * (-bol_lin_val - bol_kin_val + 2 * pc_val)),
                        (2, 1000 * (-bol_lin_val + pc_val)),
                        (3, 1000 * (-bol_kin_val + pc_val)),
                    ]
                    time_display = f"{actual_time:.1f}" if xaxis_col == "runtime_hours" else f"{actual_time}"
                    for row_num, y_val in highlight_vals:
                        fig_soh_cells_time.add_trace(go.Scatter(
                            x=[actual_time], y=[y_val],
                            mode="markers",
                            marker=dict(size=16, color="#e74c3c", line=dict(width=3, color="#c0392b")),
                            name=f"Selected: Cell {clicked_cell}",
                            hovertemplate=(
                                f"<b>Cell {clicked_cell} (Selected)</b><br>"
                                f"<b>{'Runtime [h]' if xaxis_col == 'runtime_hours' else 'Timestamp'}</b>: {time_display}<br>"
                            ),
                            showlegend=False
                        ), row=row_num, col=1)

    xaxis_label = "Runtime [h]" if xaxis_col == "runtime_hours" else "Timestamp"
    fig_soh_cells_time.update_layout(
        template=plotly_template,
        showlegend=True,
        title=dict(text="Cell-based Overpotential over Time (@Ref OpCons)", x=0.5, xanchor="center"),
        legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1, font=dict(size=10)),
        margin=dict(l=40, r=20, t=80, b=40),
        height=None
    )
    if sample_name:
        fig_soh_cells_time.add_annotation(
            text=sample_name, xref="paper", yref="paper",
            x=0.5, y=1.04, showarrow=False,
            font=dict(size=11, color="gray"), xanchor="center", yanchor="bottom",
        )
    fig_soh_cells_time.update_yaxes(title_text="Δη<sub>tot</sub> [mV]", row=1, col=1)
    fig_soh_cells_time.update_yaxes(title_text="Δη<sub>lin</sub> [mV]", row=2, col=1)
    fig_soh_cells_time.update_yaxes(title_text="Δη<sub>kin</sub> [mV]", row=3, col=1)
    fig_soh_cells_time.update_xaxes(title_text="", row=1, col=1)
    fig_soh_cells_time.update_xaxes(title_text="", row=2, col=1)
    fig_soh_cells_time.update_xaxes(title_text=xaxis_label, row=3, col=1)

    return fig_soh_cells_time

def create_cell_based_soh_across_height_plot(fig_soh_cells_across, dff, click_data, xaxis_col, plotly_template, sample_name, num_cells_from_filter):
    num_cells = num_cells_from_filter
    if num_cells is None and "number_of_cells" in dff.columns:
        num_cells = int(dff["number_of_cells"].iloc[0]) if len(dff) > 0 and pd.notna(dff["number_of_cells"].iloc[0]) else None
    # If still not found, determine from array length
    if num_cells is None and "soh_kin_cells" in dff.columns:
        max_len = dff["soh_kin_cells"].apply(get_array_len).max()
        num_cells = int(max_len) if max_len > 0 else None
    if num_cells is None or num_cells == 0:
        # Handle case where num_cells couldn't be determined
        fig_soh_cells_across.update_layout(title_text="⚠️ Could not determine number of cells.")
        return fig_soh_cells_across
    
    ctx = dash.callback_context
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]
    if triggered_id in ['soh-table', 'soh-xaxis-filter']:
        click_data = None

    selected_time = click_data["points"][0]["x"] if click_data else None
    clicked_cell = click_data["points"][0]['curveNumber'] % num_cells + 1 if click_data else None

    if selected_time is not None:
        # Create a subplot grid for the cross-section plot (tot, kin, lin)
        fig_soh_cells_across = make_subplots(
            rows=1, cols=3, 
            column_widths=[0.33, 0.33, 0.33], 
            horizontal_spacing=0.07,
            subplot_titles=("Total Overpotential", "Kinetic Overpotential", "Linear Overpotential")
        )
        # Find the specific row of data corresponding to the click
        if xaxis_col == 'runtime_hours':
            time_diff = abs(dff[xaxis_col] - selected_time)
            closest_idx = time_diff.idxmin()
            closest_row = dff.loc[closest_idx]
        else:
            closest_row_df = dff[dff[xaxis_col] == selected_time]
            if not closest_row_df.empty:
                closest_row = closest_row_df.iloc[0]
            else:
                closest_row = None
        if closest_row is not None:
            actual_time = closest_row[xaxis_col]
        
        iv_number = closest_row.get("IVnumber") if closest_row is not None else None

        # Use BoL reference columns for Δη calculation (per-cell, as in time plot)
        col_bol_lin_cells = "model_uCellAvg_BoL-lin_ref_jStck-3-0pAndeOut-2-5pCtdeOut-40tAndeIn-70vfAndeIn-5-2delta_Rohm-0_cells"
        col_bol_kin_cells = "model_uCellAvg_BoL-kin_ref_jStck-3-0pAndeOut-2-5pCtdeOut-40tAndeIn-70vfAndeIn-5-2ECSA-1_cells"
        col_pc = "model_uCellAvg_pc_3-0_stack"
        pc_val = closest_row.get(col_pc) if closest_row is not None else None
        bol_kin_vals = closest_row.get(col_bol_kin_cells) if closest_row is not None else None
        bol_lin_vals = closest_row.get(col_bol_lin_cells) if closest_row is not None else None

        # Calculate overpotentials for each cell
        if (
            pc_val is not None
            and bol_kin_vals is not None and len(bol_kin_vals) > 0
            and bol_lin_vals is not None and len(bol_lin_vals) > 0
        ):
            if closest_row is not None:

                eta_tot_cells = []
                eta_kin_cells = []
                eta_lin_cells = []
                y_cells = []
                if bol_kin_vals is not None and bol_lin_vals is not None and pc_val is not None:
                    for cell_idx in range(num_cells):
                        bol_kin = get_array_element(bol_kin_vals, cell_idx)
                        bol_lin = get_array_element(bol_lin_vals, cell_idx)
                        if bol_kin is not None and bol_lin is not None and pd.notna(bol_kin) and pd.notna(bol_lin):
                            eta_tot = 1000 * (-bol_lin - bol_kin + 2 * pc_val)
                            eta_kin = 1000 * (-bol_kin + pc_val)
                            eta_lin = 1000 * (-bol_lin + pc_val)
                            eta_tot_cells.append(eta_tot)
                            eta_kin_cells.append(eta_kin)
                            eta_lin_cells.append(eta_lin)
                            y_cells.append(cell_idx + 1)
                # Plotting code
                if y_cells:
                    fig_soh_cells_across.add_trace(go.Scatter(
                        x=eta_tot_cells, y=y_cells, mode="markers",
                        marker=dict(size=10, color="#e6b522"), name="Δη Total",
                        hovertemplate="<b>Cell %{y}</b><br>Δη Total: %{x:.3f} mV<extra></extra>",
                        showlegend=False
                    ), row=1, col=1)
                    if clicked_cell and clicked_cell in y_cells:
                        idx = y_cells.index(clicked_cell)
                        fig_soh_cells_across.add_trace(go.Scatter(
                            x=[eta_tot_cells[idx]], y=[clicked_cell], mode="markers",
                            marker=dict(size=16, color="#e74c3c", line=dict(width=3, color="#c0392b")),
                            hovertemplate=f"<b>Cell {clicked_cell} (Selected)</b><br>Δη Total: %{{x:.3f}} mV<extra></extra>",
                            showlegend=False
                        ), row=1, col=1)

                    fig_soh_cells_across.add_trace(go.Scatter(
                        x=eta_lin_cells, y=y_cells, mode="markers",
                        marker=dict(size=10, color="#3498db"), name="Δη Linear",
                        hovertemplate="<b>Cell %{y}</b><br>Δη Linear: %{x:.3f} mV<extra></extra>",
                        showlegend=False
                    ), row=1, col=2)
                    if clicked_cell and clicked_cell in y_cells:
                        idx = y_cells.index(clicked_cell)
                        fig_soh_cells_across.add_trace(go.Scatter(
                            x=[eta_lin_cells[idx]], y=[clicked_cell], mode="markers",
                            marker=dict(size=16, color="#e74c3c", line=dict(width=3, color="#c0392b")),
                            hovertemplate=f"<b>Cell {clicked_cell} (Selected)</b><br>Δη Linear: %{{x:.3f}} mV<extra></extra>",
                            showlegend=False
                        ), row=1, col=2)

                    fig_soh_cells_across.add_trace(go.Scatter(
                        x=eta_kin_cells, y=y_cells, mode="markers",
                        marker=dict(size=10, color="#2ecc71"), name="Δη Kinetic",
                        hovertemplate="<b>Cell %{y}</b><br>Δη Kinetic: %{x:.3f} mV<extra></extra>",
                        showlegend=False
                    ), row=1, col=3)
                    if clicked_cell and clicked_cell in y_cells:
                        idx = y_cells.index(clicked_cell)
                        fig_soh_cells_across.add_trace(go.Scatter(
                            x=[eta_kin_cells[idx]], y=[clicked_cell], mode="markers",
                            marker=dict(size=16, color="#e74c3c", line=dict(width=3, color="#c0392b")),
                            hovertemplate=f"<b>Cell {clicked_cell} (Selected)</b><br>Δη Kinetic: %{{x:.3f}} mV<extra></extra>",
                            showlegend=False
                        ), row=1, col=3)

        # Add annotation and update layout
        if xaxis_col == 'runtime_hours':
            annotation_text = f"@ Runtime: {actual_time:.1f}h"
        else:
            annotation_text = f"@ Timestamp: {actual_time}"
        if iv_number is not None and pd.notna(iv_number):
            annotation_text += f", IV number: {int(iv_number)}"
            
        _annotations = [dict(
            text=annotation_text, xref="paper", yref="paper", x=0.5, y=1.02,
            showarrow=False, font=dict(size=11, color="#666")
        )]
        if sample_name:
            _annotations.append(dict(
                text=sample_name, xref="paper", yref="paper",
                x=0.5, y=1.05, showarrow=False,
                font=dict(size=11, color="gray"), xanchor="center", yanchor="bottom",
            ))
        fig_soh_cells_across.update_layout(
            template=plotly_template, showlegend=False,
            title=dict(text="SOH Across Cells", x=0.5, xanchor="center"),
            margin=dict(l=40, r=40, t=80, b=40),
            annotations=_annotations
        )
        fig_soh_cells_across.update_xaxes(title_text="Δη<sub>tot</sub> [mV]", row=1, col=1)
        fig_soh_cells_across.update_xaxes(title_text="Δη<sub>lin</sub> [mV]", row=1, col=2)
        fig_soh_cells_across.update_xaxes(title_text="Δη<sub>kin</sub> [mV]", row=1, col=3)
        if num_cells <= 10:
            fig_soh_cells_across.update_yaxes(
                title_text="Cell Number", row=1, col=1,
                tickmode="linear", tick0=1, dtick=1
            )
            fig_soh_cells_across.update_yaxes(
                title_text="", row=1, col=2,
                tickmode="linear", tick0=1, dtick=1
            )
            fig_soh_cells_across.update_yaxes(
                title_text="", row=1, col=3,
                tickmode="linear", tick0=1, dtick=1
            )
        else:
            fig_soh_cells_across.update_yaxes(title_text="Cell Number", row=1, col=1)
            fig_soh_cells_across.update_yaxes(title_text="", row=1, col=2)
            fig_soh_cells_across.update_yaxes(title_text="", row=1, col=3)
    else:
        fig_soh_cells_across.update_layout(
            template=plotly_template,
            annotations=[dict(
                text="ℹ️ Click a point on the cell-based plot<br>to view SOH across all cells.",
                showarrow=False, xref="paper", yref="paper", x=0.5, y=0.5,
                font=dict(size=14, color="#95a5a6")
            )],
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            margin=dict(l=40, r=40, t=40, b=40)
        )
    return fig_soh_cells_across

def create_colored_soh_plot(df_soh, dff, xaxis_col, color_by, theme_data, sample_name):
    plotly_template = get_plotly_template(theme_data)
    dff = _filter_valid_timestamps(dff, xaxis_col)
    fig_colored_soh = go.Figure().update_layout(template=plotly_template)

    if color_by == "fitting_error_binned" and "model_min_obj_stack" in dff.columns:
        # Bin the fitting error (sqrt for scale, then bin)
        fit_err = np.sqrt(dff["model_min_obj_stack"].clip(lower=0)) * 1000  # mV
        
        # Prevent error if fit_err is all NaNs or empty
        if fit_err.dropna().empty:
             return go.Figure(), "⚠️ 'model_min_obj_stack' contains no valid data to bin.", {"display": "block", "color": "red"}

        # Use quantile bins for better distribution, only show non-empty bins
        n_bins = 6
        dff["color_bin"], bin_edges = pd.qcut(fit_err, q=n_bins, retbins=True, duplicates="drop")
        dff["color_bin_label"] = dff["color_bin"].apply(sci_fmt_interval)
        
        # Only use bins that are present in the data
        color_bins = dff["color_bin_label"].unique()
        color_label_name = "Fitting Error (binned in [mV])"
        fit_colors = dict(zip(color_bins, px.colors.sequential.Turbo[:len(color_bins)]))
        
        fig_colored_soh = make_soh_colored_subplot(plotly_template, sample_name, xaxis_col, color_label_name)
        add_binned_traces(fig_colored_soh, dff, "soh_kin_stack", color_bins, fit_colors, color_label_name, 1, "kinetic", xaxis_col, False, label_col="color_bin_label")
        add_binned_traces(fig_colored_soh, dff, "soh_lin_stack", color_bins, fit_colors, color_label_name, 2, "linear", xaxis_col, False, label_col="color_bin_label")

    else:
        color_col = color_by if color_by else "tAndeIn"
        is_pressure = (color_col == "pCtdeOut")
        is_updown = (color_col == "is_rising")
        
        color_label_map = {
            "tAndeIn": "Anode Inlet Temperature (tAndeIn)",
            "pCtdeOut": "Cathode Outlet Pressure (pCtdeOut)",
            "is_rising": "Up/Down Pol Curve (is_rising)",
        }
        color_label_name = color_label_map.get(color_col, color_col)

        if is_updown and "is_rising" in dff.columns:
            dff["color_bin"] = dff["is_rising"].map({True: "Up", False: "Down"})
            color_bins = ["Up", "Down"]
            updown_colors = (
                {"Up": "#f1e05a", "Down": "#d291ff"}
                if theme_data == "dark"
                else {"Up": "#e3d532", "Down": "#7f1366"}
            )
            fig_colored_soh = make_soh_colored_subplot(plotly_template, sample_name, xaxis_col, color_label_name)
            add_binned_traces(fig_colored_soh, dff, "soh_kin_stack", color_bins, updown_colors, color_label_name, 1, "kinetic", xaxis_col, False, label_col="color_bin")
            add_binned_traces(fig_colored_soh, dff, "soh_lin_stack", color_bins, updown_colors, color_label_name, 2, "linear", xaxis_col, False, label_col="color_bin")

        elif color_col in dff.columns:
            # handle cases where the column might be non-numeric
            if not pd.api.types.is_numeric_dtype(dff[color_col]):
                return go.Figure(), f"⚠️ Column '{color_col}' is not numeric and cannot be binned.", {"display": "block", "color": "red"}
                
            dff["color_bin"] = (dff[color_col] // 10) * 10
            color_bins = sorted(dff["color_bin"].dropna().unique())
            
            t_or_p_colors = {}
            color_scale = px.colors.sequential.Turbo
            for idx, temp in enumerate(color_bins):
                color_idx = int((idx / max(len(color_bins) - 1, 1)) * (len(color_scale) - 1))
                t_or_p_colors[temp] = color_scale[color_idx]      
            fig_colored_soh = make_soh_colored_subplot(plotly_template, sample_name, xaxis_col, color_label_name)
            add_binned_traces(fig_colored_soh, dff, "soh_kin_stack", color_bins, t_or_p_colors, color_label_name, 1, "kinetic", xaxis_col, is_pressure, label_col="color_bin")
            add_binned_traces(fig_colored_soh, dff, "soh_lin_stack", color_bins, t_or_p_colors, color_label_name, 2, "linear", xaxis_col, is_pressure, label_col="color_bin")
        else:
            # Data for the selected color_by option is not available
            fig_colored_soh = make_soh_colored_subplot(plotly_template, sample_name, xaxis_col, color_label_name)
            fig_colored_soh.update_layout(
                annotations=[dict(text=f"Data for '{color_label_name}' not available", showarrow=False, xref="paper", yref="paper", x=0.5, y=0.5)]
            )
    # Add overall polyfit lines for all data (not per bin)
    for row_num, soh_col in [(1, "soh_kin_stack"), (2, "soh_lin_stack")]:
        x_vals = dff[xaxis_col].values
        y_vals = dff[soh_col].values
        x_smooth, y_smooth, _ = get_polyfit_smooth(x_vals, y_vals, degree=2)
        color = _sample_color(sample_name, theme_data=theme_data)

        if x_smooth is not None and y_smooth is not None:
            fig_colored_soh.add_trace(
                go.Scattergl(
                    x=x_smooth,
                    y=y_smooth,
                    mode="lines",
                    name=f"Overall {soh_col} (fit)",
                    line=dict(color=color, width=2, dash="dash"),
                    showlegend=False,
                ),
                row=row_num, col=1
            )

    return fig_colored_soh


def compute_ageing_rate_subtitle(dff, iv_0, iv_1, rt_0, rt_1):
    """
    Compute trendline-based ageing-rate subtitle for Δη_tot, Δη_lin, Δη_kin between two IVs.
    Returns None when required columns or valid IV rows are unavailable.
    """
    col_lin = "model_uCellAvg_BoL-lin_ref_jStck-3-0pAndeOut-2-5pCtdeOut-40tAndeIn-70vfAndeIn-5-2delta_Rohm-0_stack"
    col_kin = "model_uCellAvg_BoL-kin_ref_jStck-3-0pAndeOut-2-5pCtdeOut-40tAndeIn-70vfAndeIn-5-2ECSA-1_stack"
    col_pc = "model_uCellAvg_pc_3-0_stack"

    if not {col_lin, col_kin, col_pc, "runtime_hours", "IVnumber"}.issubset(dff.columns):
        return None

    dt = rt_1 - rt_0
    if dt == 0:
        return None

    row_iv0 = dff[dff["IVnumber"] == iv_0]
    row_iv1 = dff[dff["IVnumber"] == iv_1]
    if row_iv0.empty or row_iv1.empty:
        return None

    rt_early, rt_late = (rt_0, rt_1) if dt > 0 else (rt_1, rt_0)
    dt_abs = abs(dt)

    rt_all = np.asarray(dff["runtime_hours"].values, dtype=float)
    finite_rt = np.isfinite(rt_all)
    if finite_rt.sum() < 3:
        return None

    def _trend_rate(y_series):
        y_vals = np.asarray(y_series, dtype=float)
        x_fit, y_fit, coeffs = get_polyfit_smooth(rt_all, y_vals, degree=2)
        _ = x_fit, y_fit
        if coeffs is None:
            return None
        return (np.polyval(coeffs, rt_late) - np.polyval(coeffs, rt_early)) / dt_abs * 1000

    tr_tot = _trend_rate(1000 * (-dff[col_lin] - dff[col_kin] + 2 * dff[col_pc]))
    tr_lin = _trend_rate(1000 * (-dff[col_lin] + dff[col_pc]))
    tr_kin = _trend_rate(1000 * (-dff[col_kin] + dff[col_pc]))

    def _fmt(v):
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return "N/A"
        return f"{v:+.2f}"

    return (
        "Ageing Rate Estimation:  "
        f"Δη<sub>tot</sub>/Δη<sub>lin</sub>/Δη<sub>kin</sub>: "
        f"{_fmt(tr_tot)}/{_fmt(tr_lin)}/{_fmt(tr_kin)} µV/h"
    )

def create_load_cycle_plots(dff, theme_data, sample_name, slider_value, valid_ivs):
    plotly_template = get_plotly_template(theme_data)
    fig = make_subplots(
        rows=2, cols=3,
        row_heights=[0.5, 0.5],
        vertical_spacing=0.16,
        horizontal_spacing=0.08,
        subplot_titles=(
            "Current Density [A/cm²]", "Cell Voltage [V]", "Temperature [°C]",
            "Cathode Pressure Out [bar]", "Water Inflow [l/min]", "Anode Pressure Out [bar]",
        ),
    )

    if not slider_value or valid_ivs is None or valid_ivs.empty:
        fig.update_layout(template=plotly_template)
        return fig

    iv_0, iv_1 = slider_value[0], slider_value[1]
    row_0 = valid_ivs[valid_ivs["IVnumber"] == iv_0]
    row_1 = valid_ivs[valid_ivs["IVnumber"] == iv_1]
    if row_0.empty or row_1.empty:
        fig.update_layout(template=plotly_template)
        # Add empty traces so Plotly renders all subplot axes
        for r, c in [(1,1),(1,2),(1,3),(2,1),(2,2),(2,3)]:
            fig.add_trace(go.Scatter(x=[], y=[], showlegend=False), row=r, col=c)
        # Hide subplot titles
        fig.layout.annotations = []
        fig.add_annotation(
            text="Selected IVs do not have SOH information.",
            showarrow=False, xref="paper", yref="paper", x=0.5, y=0.5,
            font=dict(size=14, color="#95a5a6"),
        )
        return fig

    rt_0 = row_0["runtime_hours"].iloc[0]
    rt_1 = row_1["runtime_hours"].iloc[0]
    rt_min, rt_max = min(rt_0, rt_1), max(rt_0, rt_1)
    ageing_annotation = compute_ageing_rate_subtitle(dff, iv_0, iv_1, rt_0, rt_1)

    # Filter data between the two selected IVs (by runtime range)
    df_range = dff[(dff["runtime_hours"] >= rt_min) & (dff["runtime_hours"] <= rt_max)]
    if df_range.empty:
        fig.update_layout(template=plotly_template)
        return fig

    hist_color = "#3498db"
    hist_configs = [
        ("jStck",    1, 1),
        ("uCellAvg", 1, 2),
        ("tAndeIn",  1, 3),
        ("pCtdeOut", 2, 1),
        ("vfAndeIn", 2, 2),
        ("pAndeOut", 2, 3),
    ]

    for col_name, row, col in hist_configs:
        if col_name not in df_range.columns:
            subplot_idx = (row - 1) * 3 + col
            fig.add_annotation(
                text="No data", showarrow=False,
                xref=f"x{subplot_idx}" if subplot_idx > 1 else "x",
                yref=f"y{subplot_idx}" if subplot_idx > 1 else "y",
                x=0.5, y=0.5,
                font=dict(size=12, color="#95a5a6"),
            )
            continue

        # Flatten arrays if the column contains array values
        vals = df_range[col_name].dropna()
        flat_vals = []
        for v in vals:
            if isinstance(v, (list, tuple, np.ndarray)):
                flat_vals.extend([x for x in v if x is not None and not pd.isna(x)])
            elif not pd.isna(v):
                flat_vals.append(v)

        if flat_vals:
            fig.add_trace(
                go.Histogram(
                    x=flat_vals,
                    marker_color=hist_color,
                    opacity=0.8,
                    showlegend=False,
                    hovertemplate=f"<b>{col_name}</b>: %{{x:.3f}}<br>Count: %{{y}}<extra></extra>",
                ),
                row=row, col=col,
            )

    ageing_part = f"  <br>  {ageing_annotation}" if ageing_annotation is not None else ""
    fig.update_layout(
        template=plotly_template,
        title=dict(
            text=f"Load Cycle Histograms (IV {int(iv_0)} @ {rt_0:.0f}h → IV {int(iv_1)} @ {rt_1:.0f}h{ageing_part})",
            x=0.5, xanchor="center",
        ),
        margin=dict(l=40, r=20, t=140, b=40),
        showlegend=False,
        bargap=0.05,
        height=None,
    )
    if sample_name:
        fig.add_annotation(
            text=sample_name, xref="paper", yref="paper",
            x=0.5, y=1.08, showarrow=False,
            font=dict(size=11, color="gray"), xanchor="center", yanchor="bottom",
        )
    return fig