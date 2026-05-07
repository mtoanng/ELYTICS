import logging

from dash import Input, Output, State, callback, clientside_callback, dcc, html, no_update, register_page
from dash.dcc.express import send_data_frame
from dash.exceptions import PreventUpdate
import dash_mantine_components as dmc
from dash_iconify import DashIconify
import pandas as pd
import plotly.graph_objs as go

from services.backend_service import get_metadata, get_tabular
from services import soh_service
from services import soh_layout_service


logger = logging.getLogger(__name__)


register_page(
    __name__,
    path="/sherlock/ai-ml/soh",
    title="HOLMES - Sherlock - State of Health",
)


USAGE_BLOCKQUOTE_TEXT = [
    "Explore SOH trends with lazy-loaded fleet and stack datasets.",
    "Select a sample to unlock stack-level detail plots.",
    "Download the currently relevant SOH dataset as CSV.",
]


def _empty_figure(theme_data: str | None) -> go.Figure:
    return go.Figure().update_layout(template=soh_service.get_plotly_template(theme_data))


def _normalize_bool_filter(selection: str | None) -> bool | None:
    if selection == "rising":
        return True
    if selection == "falling":
        return False
    return None


def _filter_stack_dataframe(
    df: pd.DataFrame,
    is_rising: str | None,
) -> pd.DataFrame:
    if df.empty:
        return df

    filtered = df

    rising_value = _normalize_bool_filter(is_rising)
    if rising_value is not None and "is_rising" in filtered.columns:
        lowered = filtered["is_rising"].astype(str).str.strip().str.lower()
        truthy = {"true", "1", "yes"}
        falsy = {"false", "0", "no"}
        filtered = filtered.loc[
            filtered["is_rising"].eq(rising_value)
            | lowered.isin(truthy if rising_value else falsy)
        ]

    return filtered


def _section_panel(title: str, children: list) -> dmc.AccordionItem:
    return dmc.AccordionItem(
        value=title,
        children=[
            dmc.AccordionControl(title),
            dmc.AccordionPanel(
                dmc.Box(
                    p="md",
                    children=children,
                    style={"overflow": "hidden"},
                )
            ),
        ],
    )


layout = dmc.Container(
    size="xl",
    py="md",
    style={
        "minHeight": "calc(100dvh - var(--app-shell-header-offset, 0rem))",
        "display": "flex",
        "flexDirection": "column",
    },
    children=[
        dmc.Stack(
            gap="md",
            style={"flex": "1 1 0", "minHeight": 0},
            children=[
                dmc.Stack(
                    gap=2,
                    children=[
                        dmc.Group(
                            gap="xs",
                            align="center",
                            children=[
                                dmc.Title("State of Health", order=2),
                                dmc.ActionIcon(
                                    DashIconify(icon="material-symbols:info-outline", width=20),
                                    id="soh-usage-toggle",
                                    variant="subtle",
                                    color="blue",
                                    size="md",
                                    radius="xl",
                                ),
                            ],
                        ),
                        dmc.Text(
                            "Monitor stack and fleet SOH behavior for Sherlock.", c="dimmed"
                        ),
                        dmc.Collapse(
                            dmc.Blockquote(
                                dmc.List(
                                    withPadding=False,
                                    children=[dmc.ListItem(item) for item in USAGE_BLOCKQUOTE_TEXT],
                                ),
                                color="blue",
                            ),
                            id="soh-usage-collapse",
                        ),
                    ],
                ),
                dmc.Paper(
                    withBorder=True,
                    p="md",
                    radius="md",
                    style={
                        "display": "flex",
                        "flexDirection": "column",
                        "overflow": "visible",
                    },
                    children=[
                        dmc.Group(
                            gap="md",
                            align="flex-end",
                            style={"flexWrap": "nowrap", "overflowX": "auto"},
                            children=[
                                dmc.InputWrapper(
                                    dcc.Dropdown(
                                        id="soh-sample-name-filter",
                                        placeholder="Sample Name",
                                        clearable=True,
                                        style={"width": "100%"},
                                    ),
                                    label="Sample Name",
                                    htmlFor="soh-sample-name-filter",
                                    className="dmc",
                                    styles={"label": {"marginBottom": "6px"}},
                                    style={"flex": 1, "minWidth": "220px"},
                                ),
                                dmc.InputWrapper(
                                    dcc.Dropdown(
                                        id="soh-number-of-cells-filter",
                                        placeholder="Number of Cells",
                                        clearable=True,
                                        style={"width": "100%"},
                                    ),
                                    label="Number of Cells",
                                    htmlFor="soh-number-of-cells-filter",
                                    className="dmc",
                                    styles={"label": {"marginBottom": "6px"}},
                                    style={"flex": 1, "minWidth": "160px"},
                                ),
                                dmc.InputWrapper(
                                    dcc.Dropdown(
                                        id="soh-ccm-type-filter",
                                        placeholder="CCM Type",
                                        clearable=True,
                                        style={"width": "100%"},
                                    ),
                                    label="CCM Type",
                                    htmlFor="soh-ccm-type-filter",
                                    className="dmc",
                                    styles={"label": {"marginBottom": "6px"}},
                                    style={"flex": 1, "minWidth": "180px"},
                                ),
                                dmc.InputWrapper(
                                    dcc.Dropdown(
                                        id="soh-xaxis-filter",
                                        options=soh_layout_service.X_AXIS_OPTIONS,
                                        value="runtime_hours",
                                        clearable=False,
                                        style={"width": "100%"},
                                    ),
                                    label="X-axis",
                                    htmlFor="soh-xaxis-filter",
                                    className="dmc",
                                    styles={"label": {"marginBottom": "6px"}},
                                    style={"flex": 1, "minWidth": "170px"},
                                ),
                                dmc.Stack(
                                    gap=4,
                                    style={"minWidth": "180px"},
                                    children=[
                                        dmc.Text("Direction", fw=500, size="sm"),
                                        dmc.SegmentedControl(
                                            id="soh-is-rising-filter",
                                            data=soh_layout_service.IS_RISING_OPTIONS,
                                            value="all",
                                            fullWidth=True,
                                        ),
                                    ],
                                ),
                                dmc.Button(
                                    [
                                        html.I(
                                            className="bi bi-download",
                                            style={"marginRight": "10px", "fontSize": "1.1em"},
                                        ),
                                        "Download CSV",
                                    ],
                                    id="soh-download-btn",
                                    n_clicks=0,
                                    className="download-btn",
                                    style={
                                        "flex": "0 0 auto",
                                        "whiteSpace": "nowrap",
                                        "alignSelf": "flex-end",
                                    },
                                ),
                            ],
                        ),
                        dcc.Download(id="soh-download-csv"),
                        dmc.Space(h="sm"),
                        dmc.Text(
                            id="soh-empty-message",
                            c="red",
                            fw=600,
                            style={"display": "none"},
                        ),
                        dmc.Text(
                            id="soh-plot-message",
                            c="yellow",
                            fw=600,
                            style={"textAlign": "center"},
                        ),
                        dmc.Text(
                            id="soh-view-label",
                            c="dimmed",
                            fw=500,
                            style={"textAlign": "center"},
                        ),
                        dmc.Divider(size="xs", my="sm"),
                        dmc.Accordion(
                            id="soh-accordion",
                            multiple=True,
                            value=["① FLEET INFO: STACK SOH (AS OVERPOTENTIAL)"],
                            children=[
                                _section_panel(
                                    "① FLEET INFO: STACK SOH (AS OVERPOTENTIAL)",
                                    [
                                        dmc.Box(
                                            style={
                                                "display": "grid",
                                                "gridTemplateColumns": "minmax(320px, 7fr) minmax(280px, 3fr)",
                                                "gap": "16px",
                                            },
                                            children=[
                                                dcc.Graph(id="soh-overpotential-plots", config={"responsive": True}, style={"height": "600px"}),
                                                dcc.Graph(id="soh-overpotential-lin-vs-kin-plot", config={"responsive": True}, style={"height": "600px"}),
                                            ],
                                        )
                                    ],
                                ),
                                _section_panel(
                                    "② STACK SOH & LOAD CYCLES",
                                    [
                                        dmc.Text(
                                            id="soh-decomp-message",
                                            c="yellow",
                                            fw=600,
                                            style={"textAlign": "center"},
                                        ),
                                        dmc.Box(
                                            id="soh-decomp-plot-container",
                                            children=[
                                                dmc.Box(
                                                    style={
                                                        "display": "grid",
                                                        "gridTemplateColumns": "repeat(2, minmax(300px, 1fr))",
                                                        "gap": "16px",
                                                    },
                                                    children=[
                                                        dcc.Graph(
                                                            id="soh-overpotential-all-in-one",
                                                            config={"responsive": True},
                                                            style={"height": "480px"},
                                                        ),
                                                        dcc.Graph(
                                                            id="soh-decomp-plot",
                                                            config={"responsive": True},
                                                            style={"height": "480px"},
                                                        ),
                                                    ],
                                                ),
                                                dmc.Space(h="xs"),
                                                dmc.Text("Select IV Pair (by Runtime)", fw=500, size="sm"),
                                                dcc.RangeSlider(
                                                    id="soh-decomp-diff-range-slider",
                                                    min=0,
                                                    max=1,
                                                    step=1,
                                                    value=[0, 1],
                                                    marks={},
                                                    tooltip={"placement": "bottom", "always_visible": True},
                                                ),
                                                dmc.Space(h="md"),
                                                dcc.Graph(
                                                    id="soh-load-cycle-plots",
                                                    config={"responsive": True},
                                                    style={"height": "480px"},
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                                _section_panel(
                                    "③ CELL-BASED SOH (AS OVERPOTENTIAL)",
                                    [
                                        dmc.Text(
                                            id="soh-cells-message",
                                            c="yellow",
                                            fw=600,
                                            style={"textAlign": "center"},
                                        ),
                                        dmc.Box(
                                            id="soh-cells-container",
                                            children=[
                                                dmc.Box(
                                                    style={
                                                        "display": "grid",
                                                        "gridTemplateColumns": "minmax(360px, 3fr) minmax(300px, 2fr)",
                                                        "gap": "16px",
                                                    },
                                                    children=[
                                                        dcc.Graph(id="soh-cells-time-plot", config={"responsive": True},style={"height": "600px"}),
                                                        dcc.Graph(id="soh-cells-across-plot", config={"responsive": True},style={"height": "600px"}),
                                                    ],
                                                )
                                            ],
                                        ),
                                    ],
                                ),
                                _section_panel(
                                    "④ STACK SOH VALUES (ORIG: SOH_KIN vs SOH_LIN)",
                                    [
                                        dmc.Box(
                                            id="soh-color-by-container",
                                            style={"display": "none", "maxWidth": "340px", "marginBottom": "12px"},
                                            children=[
                                                dmc.InputWrapper(
                                                    dcc.Dropdown(
                                                        id="soh-color-by",
                                                        options=soh_layout_service.COLOR_BY_OPTIONS,
                                                        value="none",
                                                        clearable=False,
                                                        style={"width": "100%"},
                                                    ),
                                                    label="Color SOH By",
                                                    htmlFor="soh-color-by",
                                                    className="dmc",
                                                    styles={"label": {"marginBottom": "6px"}},
                                                )
                                            ],
                                        ),
                                        dmc.Box(
                                            id="soh-fleet-stack-plot-container",
                                            style={
                                                "display": "grid",
                                                "gridTemplateColumns": "minmax(320px, 7fr) minmax(280px, 3fr)",
                                                "gap": "16px",
                                            },
                                            children=[
                                                dcc.Graph(id="soh-fleet-stack-soh-plot", config={"responsive": True},style={"height": "600px"}),
                                                dcc.Graph(id="soh-fleet-lin-vs-lin-plot", config={"responsive": True},style={"height": "600px"}),
                                            ],
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
                dcc.Store(id="soh-metadata-store"),
                dcc.Store(id="soh-fleet-data-store"),
                dcc.Store(id="soh-stack-data-store"),
                dcc.Store(id="soh-stack-load-status", data={"state": "idle"}),
                dcc.Store(id="soh-usage-open", data=False),
                dcc.Store(id="soh-theme-store"),
                dcc.Store(id="soh-cell-plot-click-store", data=None),
                dcc.Store(id="soh-plot-resize-store")
            ],
        )
    ],
)


clientside_callback(
    """
    function(sampleValue, stackData, themeData, decompFig, allInOneFig, loadCycleFig, accordionValue, decompStyle) {
        if (!window.Plotly) return null;

        const graphIds = [
            "soh-overpotential-plots",
            "soh-overpotential-lin-vs-kin-plot",
            "soh-decomp-plot",
            "soh-overpotential-all-in-one",
            "soh-load-cycle-plots",
            "soh-cells-time-plot",
            "soh-cells-across-plot",
            "soh-fleet-stack-soh-plot",
            "soh-fleet-lin-vs-lin-plot"
        ];

        const isVisible = (el) =>
            !!el && el.offsetParent !== null && el.clientWidth > 20 && el.clientHeight > 20;

        const resizeVisible = () => {
            graphIds.forEach((id) => {
                const el = document.getElementById(id);
                if (!isVisible(el)) return;
                try {
                    window.Plotly.Plots.resize(el);
                } catch (e) {
                    console.warn("Plot resize failed:", id, e);
                }
            });
        };

        // Let accordion + plot DOM settle first
        requestAnimationFrame(() => {
            requestAnimationFrame(resizeVisible);
        });
        setTimeout(resizeVisible, 220);
        setTimeout(resizeVisible, 480);

        return Date.now();
    }
    """,
    Output("soh-plot-resize-store", "data"),
    Input("soh-sample-name-filter", "value"),
    Input("soh-stack-data-store", "data"),
    Input("soh-theme-store", "data"),
    Input("soh-decomp-plot", "figure"),
    Input("soh-overpotential-all-in-one", "figure"),
    Input("soh-load-cycle-plots", "figure"),
    Input("soh-accordion", "value"),
    Input("soh-decomp-plot-container", "style"),
)


@callback(
    Output("soh-usage-open", "data"),
    Input("soh-usage-toggle", "n_clicks"),
    State("soh-usage-open", "data"),
    prevent_initial_call=True,
)
def toggle_usage(n_clicks, is_open):
    if not n_clicks:
        raise PreventUpdate
    return not bool(is_open)


@callback(
    Output("soh-usage-collapse", "opened"),
    Input("soh-usage-open", "data"),
)
def sync_usage(is_open):
    return bool(is_open)


@callback(
    Output("soh-theme-store", "data"),
    Input("theme-store", "data"),
)
def sync_theme(theme_data):
    return theme_data


@callback(
    Output("soh-metadata-store", "data"),
    Input("soh-sample-name-filter", "id"),
)
def load_metadata(_):
    meta = get_metadata("sherlock", "soh")
    df = pd.DataFrame(meta)
    return df.to_dict("list") if not df.empty else {}


@callback(
    Output("soh-sample-name-filter", "options"),
    Input("soh-metadata-store", "data"),
)
def update_sample_options(metadata_store):
    if not metadata_store:
        return []
    values = pd.Series(metadata_store.get("sample_name", [])).dropna().unique().tolist()
    return [{"label": str(v), "value": str(v)} for v in sorted(values)]


@callback(
    Output("soh-number-of-cells-filter", "options"),
    Output("soh-ccm-type-filter", "options"),
    Input("soh-metadata-store", "data"),
    Input("soh-sample-name-filter", "value"),
)
def update_secondary_filter_options(metadata_store, sample_name):
    if not metadata_store:
        return [], []
    df = pd.DataFrame(metadata_store)
    if df.empty:
        return [], []
    if sample_name and "sample_name" in df.columns:
        df = df[df["sample_name"] == sample_name]

    num_cells = []
    ccm_types = []
    if "number_of_cells" in df.columns:
        vals = pd.to_numeric(df["number_of_cells"], errors="coerce").dropna().astype(int)
        num_cells = [{"label": str(v), "value": int(v)} for v in sorted(vals.unique().tolist())]
    if "ccm_type" in df.columns:
        vals = [str(v) for v in df["ccm_type"].dropna().unique().tolist()]
        ccm_types = [{"label": v, "value": v} for v in sorted(vals)]
    return num_cells, ccm_types


@callback(
    Output("soh-number-of-cells-filter", "value"),
    Output("soh-ccm-type-filter", "value"),
    Input("soh-sample-name-filter", "value"),
    State("soh-metadata-store", "data"),
)
def autofill_filters_for_sample(sample_name, metadata_store):
    if not metadata_store or not sample_name:
        return no_update, no_update
    df = pd.DataFrame(metadata_store)
    if df.empty:
        return no_update, no_update
    return soh_service.get_sample_filters(df, sample_name)


@callback(
    Output("soh-fleet-data-store", "data"),
    Output("soh-empty-message", "children"),
    Output("soh-empty-message", "style"),
    Input("soh-sample-name-filter", "value"),
    Input("soh-number-of-cells-filter", "value"),
    Input("soh-ccm-type-filter", "value"),
    Input("soh-is-rising-filter", "value"),
)
def load_fleet_data(sample_name, number_of_cells, ccm_type, is_rising):
    filters = {}
    if sample_name:
        filters["sample_name"] = sample_name
    if number_of_cells is not None:
        filters["number_of_cells"] = str(number_of_cells)
    if ccm_type:
        filters["ccm_type"] = ccm_type
    rising_value = _normalize_bool_filter(is_rising)
    if rising_value is not None:
        filters["is_rising"] = rising_value

    df = get_tabular("sherlock", "soh_fleet", filters=filters, sort_by="runtime_hours")
    if df.empty:
        return [], "No SOH fleet data found for the selected filters.", {"display": "block"}
    return df.to_dict("records"), "", {"display": "none"}


@callback(
    Output("soh-stack-data-store", "data"),
    Output("soh-stack-load-status", "data"),
    Input("soh-sample-name-filter", "value"),
    Input("soh-number-of-cells-filter", "value"),
    Input("soh-ccm-type-filter", "value"),
    Input("soh-is-rising-filter", "value"),
)
def load_stack_data(sample_name, number_of_cells, ccm_type, is_rising):
    _ = number_of_cells, ccm_type
    if not sample_name:
        return [], {"state": "idle"}

    primary_error = None
    try:
        df = get_tabular(
            "sherlock",
            "soh_stack",
            filters={"sample_name": sample_name},
            sort_by="runtime_hours",
        )
    except Exception as exc:
        primary_error = exc
        logger.exception("Failed stack SOH request with backend sorting for sample %s", sample_name)
        try:
            # Retry without backend sorting; some deployed views reject runtime_hours sort.
            df = get_tabular(
                "sherlock",
                "soh_stack",
                filters={"sample_name": sample_name},
            )
            if "runtime_hours" in df.columns:
                df = df.sort_values("runtime_hours")
        except Exception as retry_exc:
            logger.exception("Failed stack SOH request without backend sorting for sample %s", sample_name)
            return [], {
                "state": "error",
                "message": f"Stack data request failed. sorted={primary_error}; unsorted={retry_exc}",
                "sample_name": sample_name,
            }

    df = _filter_stack_dataframe(df, is_rising)
    if df.empty:
        return [], {"state": "empty", "sample_name": sample_name}
    records = df.to_dict("records")
    return records, {"state": "ok", "sample_name": sample_name, "rows": len(records)}


@callback(
    Output("soh-fleet-stack-soh-plot", "figure"),
    Output("soh-fleet-lin-vs-lin-plot", "figure"),
    Output("soh-overpotential-plots", "figure"),
    Output("soh-overpotential-lin-vs-kin-plot", "figure"),
    Output("soh-plot-message", "children"),
    Output("soh-color-by-container", "style"),
    Input("soh-fleet-data-store", "data"),
    Input("soh-stack-data-store", "data"),
    Input("soh-stack-load-status", "data"),
    Input("soh-sample-name-filter", "value"),
    Input("soh-number-of-cells-filter", "value"),
    Input("soh-ccm-type-filter", "value"),
    Input("soh-xaxis-filter", "value"),
    Input("soh-color-by", "value"),
    Input("soh-theme-store", "data"),
)
def update_soh_outputs(
    fleet_data,
    stack_data,
    stack_load_status,
    sample_name,
    number_of_cells,
    ccm_type,
    xaxis_col,
    color_by,
    theme_data,
):
    empty_fig = _empty_figure(theme_data)
    if not fleet_data:
        return empty_fig, empty_fig, empty_fig, empty_fig, "", "", {"display": "none"}

    df_fleet = pd.DataFrame(fleet_data)
    df_stack = pd.DataFrame(stack_data) if stack_data else pd.DataFrame()
    plot_df = df_stack if sample_name and not df_stack.empty else df_fleet
    fleet_plot_df = df_fleet

    if xaxis_col not in plot_df.columns:
        xaxis_col = "runtime_hours"

    plotly_template = soh_service.get_plotly_template(theme_data)

    if sample_name and color_by and color_by != "none":
        colored_result = soh_service.create_colored_soh_plot(
            df_fleet,
            plot_df,
            xaxis_col,
            color_by,
            theme_data,
            sample_name,
        )
        if isinstance(colored_result, tuple):
            fleet_fig = empty_fig
            plot_message = str(colored_result[1])
        else:
            fleet_fig = colored_result
            plot_message = ""
    else:
        fleet_fig = soh_service.create_fleet_soh_plot(df_fleet, plot_df, sample_name, xaxis_col, plotly_template)
        plot_message = ""

    lin_vs_kin_fig = soh_service.create_lin_vs_kin_plot(
        fleet_plot_df,
        df_fleet,
        plotly_template,
        sample_name,
    )
    overpotential_fig, fit_coeffs = soh_service.create_overpotential_plots(
        df_fleet,
        plot_df,
        xaxis_col,
        theme_data,
        sample_name,
    )
    overpotential_lin_vs_kin_fig = soh_service.create_overpotential_lin_vs_kin_plot(
        fleet_plot_df,
        df_fleet,
        plotly_template,
        sample_name,
        fit_coeffs if plot_df is df_fleet else None,
    )

    color_by_style = {"display": "block", "maxWidth": "340px", "marginBottom": "12px"}
    if not sample_name:
        color_by_style = {"display": "none"}

    detail_msg = ""
    stack_state = (stack_load_status or {}).get("state")
    if sample_name and df_stack.empty:
        if stack_state == "error":
            err_text = str((stack_load_status or {}).get("message", "")).strip()
            detail_msg = (
                "Stack data endpoint failed for the selected sample; detailed plots are unavailable and fleet-level data is shown. "
                + (f"Details: {err_text}" if err_text else "")
            )
        elif stack_state == "empty":
            detail_msg = "No stack-level rows found for the selected sample; detailed plots use fleet-level data."
        else:
            detail_msg = "No stack-level data returned for selected sample; detailed plots use fleet-level data."
    if plot_message:
        detail_msg = plot_message

    return (
        fleet_fig,
        lin_vs_kin_fig,
        overpotential_fig,
        overpotential_lin_vs_kin_fig,
        detail_msg,
        color_by_style,
    )


@callback(
    Output("soh-decomp-plot-container", "style"),
    Output("soh-decomp-message", "children"),
    Output("soh-decomp-diff-range-slider", "min"),
    Output("soh-decomp-diff-range-slider", "max"),
    Output("soh-decomp-diff-range-slider", "marks"),
    Output("soh-decomp-diff-range-slider", "value"),
    Input("soh-stack-data-store", "data"),
    State("soh-sample-name-filter", "value"),
)
def update_decomp_slider_and_visibility(stack_data, sample_name):
    defaults = ({"display": "none"}, "", 0, 1, {}, [0, 1])
    if not sample_name:
        return {"display": "none"}, "Select a sample name to view decomposition and load-cycle plots.", 0, 1, {}, [0, 1]
    if not stack_data:
        return defaults

    df = pd.DataFrame(stack_data)
    if df.empty or "IVnumber" not in df.columns or "runtime_hours" not in df.columns:
        return defaults

    df = df.sort_values("runtime_hours")
    valid_ivs = soh_service.get_valid_iv_list(df)
    if valid_ivs.empty or len(valid_ivs) < 2:
        return defaults

    iv_numbers = [int(v) for v in valid_ivs["IVnumber"].tolist()]
    min_iv = min(iv_numbers)
    max_iv = max(iv_numbers)

    max_n_marks = 7
    n_marks = min(max_n_marks, len(iv_numbers))
    if n_marks > 1:
        indices = [round(i * (len(iv_numbers) - 1) / (n_marks - 1)) for i in range(n_marks)]
    else:
        indices = [0]
    marks = {
        int(valid_ivs.iloc[i]["IVnumber"]): f"{float(valid_ivs.iloc[i]['runtime_hours']):.0f}h"
        for i in indices
    }
    default_value = [int(iv_numbers[0]), int(iv_numbers[-1])]
    return {"display": "block"}, "", min_iv, max_iv, marks, default_value


@callback(
    Output("soh-decomp-plot", "figure"),
    Output("soh-overpotential-all-in-one", "figure"),
    Output("soh-load-cycle-plots", "figure"),
    Input("soh-decomp-diff-range-slider", "value"),
    Input("soh-theme-store", "data"),
    Input("soh-xaxis-filter", "value"),
    State("soh-fleet-data-store", "data"),
    State("soh-stack-data-store", "data"),
    State("soh-sample-name-filter", "value"),
)
def update_decomp_and_load_cycle_plots(
    slider_value,
    theme_data,
    xaxis_col,
    fleet_data,
    stack_data,
    sample_name,
):
    empty_fig = _empty_figure(theme_data)
    if not stack_data or not fleet_data or not slider_value:
        return empty_fig, empty_fig, empty_fig

    df_stack = pd.DataFrame(stack_data)
    df_fleet = pd.DataFrame(fleet_data)
    if df_stack.empty or df_fleet.empty:
        return empty_fig, empty_fig, empty_fig

    valid_ivs = soh_service.get_valid_iv_list(df_stack.sort_values("runtime_hours"))
    if valid_ivs.empty:
        return empty_fig, empty_fig, empty_fig

    plotly_template = soh_service.get_plotly_template(theme_data)
    decomp_fig = soh_service.create_polcurve_decomp_plot(
        df_stack,
        valid_ivs,
        slider_value,
        plotly_template,
        sample_name,
    )
    all_in_one_fig, _ = soh_service.create_overpotential_plot_all_in_one(
        df_fleet,
        df_stack,
        xaxis_col,
        theme_data,
        sample_name,
        slider_value,
        valid_ivs,
    )
    load_cycle_fig = soh_service.create_load_cycle_plots(
        df_stack,
        theme_data,
        sample_name,
        slider_value,
        valid_ivs,
    )
    return decomp_fig, all_in_one_fig, load_cycle_fig


@callback(
    Output("soh-cells-time-plot", "figure"),
    Output("soh-cells-message", "children"),
    Output("soh-cells-container", "style"),
    Input("soh-stack-data-store", "data"),
    Input("soh-xaxis-filter", "value"),
    Input("soh-sample-name-filter", "value"),
    Input("soh-cells-time-plot", "clickData"),
    Input("soh-theme-store", "data"),
)
def update_cell_based_soh_time_plot(stack_data, xaxis_col, sample_name, click_data, theme_data):
    empty_fig = _empty_figure(theme_data)
    if not sample_name:
        return empty_fig, "Select a sample name to view cell-level SOH data.", {"display": "none"}
    if not stack_data:
        return empty_fig, "", {"display": "none"}

    df = pd.DataFrame(stack_data)
    fig = soh_service.create_cell_based_soh_time_plot(
        df,
        xaxis_col,
        click_data,
        theme_data,
        sample_name,
    )
    return fig, "", {"display": "block"}


@callback(
    Output("soh-cell-plot-click-store", "data"),
    Input("soh-cells-time-plot", "clickData"),
    prevent_initial_call=True,
)
def store_last_clicked_cell_based_point(click_data):
    return click_data


@callback(
    Output("soh-cells-across-plot", "figure"),
    Input("soh-stack-data-store", "data"),
    Input("soh-cell-plot-click-store", "data"),
    Input("soh-xaxis-filter", "value"),
    Input("soh-theme-store", "data"),
    State("soh-sample-name-filter", "value"),
    State("soh-number-of-cells-filter", "value"),
)
def update_cell_based_soh_across_height_plot(
    stack_data,
    click_data,
    xaxis_col,
    theme_data,
    sample_name,
    num_cells_from_filter,
):
    plotly_template = soh_service.get_plotly_template(theme_data)
    fig = go.Figure().update_layout(template=plotly_template)
    if not stack_data or not sample_name:
        fig.update_layout(
            annotations=[
                dict(
                    text="Select a sample to view SOH across stack height.",
                    showarrow=False,
                    xref="paper",
                    yref="paper",
                    x=0.5,
                    y=0.5,
                )
            ],
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
        )
        return fig

    df = pd.DataFrame(stack_data)
    if df.empty:
        return fig

    return soh_service.create_cell_based_soh_across_height_plot(
        fig,
        df,
        click_data,
        xaxis_col,
        plotly_template,
        sample_name,
        num_cells_from_filter,
    )


@callback(
    Output("soh-download-csv", "data"),
    Input("soh-download-btn", "n_clicks"),
    State("soh-fleet-data-store", "data"),
    State("soh-stack-data-store", "data"),
    State("soh-sample-name-filter", "value"),
    prevent_initial_call=True,
)
def download_soh_table(n_clicks, fleet_data, stack_data, sample_name):
    if not n_clicks:
        raise PreventUpdate

    use_stack = bool(sample_name and stack_data)
    selected_data = stack_data if use_stack else fleet_data
    if not selected_data:
        raise PreventUpdate

    df = pd.DataFrame(selected_data)
    if df.empty:
        raise PreventUpdate

    sort_cols = [c for c in ["sample_name", "runtime_hours", "IVnumber"] if c in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols)

    csv_name = "soh_stack.csv" if use_stack else "soh_fleet.csv"
    return send_data_frame(df.to_csv, csv_name, index=False)