from dash import html, dcc, callback, Output, Input, State, register_page, no_update, clientside_callback
from dash.dcc.express import send_data_frame
import dash_mantine_components as dmc
import dash_ag_grid as dag

import pandas as pd
import plotly.express as px

from services.backend_service import get_table_as_df

register_page(
    __name__,
    path="/sherlock/data-exploration/ccm-overview",
    title="HOLMES - Sherlock - CCM Overview"
)

def ccm_overview_layout():
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
                            dmc.Title("CCM Runtime Overview", order=2),
                            dmc.Text("Timeline view of stack-level CCM executions.", c="dimmed"),
                        ],
                    ),
                    dcc.Store(id="ccm-data-store"),
                    dmc.Paper(
                        withBorder=True,
                        p="md",
                        radius="md",
                        children=[
                            dmc.Group(
                                gap="md",
                                align="flex-end",
                                style={"flexWrap": "wrap"},
                                children=[
                                    dmc.InputWrapper(
                                        dcc.Dropdown(
                                            id="testrig-location-filter",
                                            options=[],
                                            value=[],
                                            multi=True,
                                            placeholder="Select one or more locations",
                                            style={"width": "100%"},
                                        ),
                                        label="Filter by Testrig Location",
                                        htmlFor="testrig-location-filter",
                                        className="dmc",
                                        styles={"label": {"marginBottom": "6px"}},
                                        style={"flex": "1", "minWidth": "280px"},
                                    ),
                                    dmc.InputWrapper(
                                        dcc.Dropdown(
                                            id="ccm-filter",
                                            options=[],
                                            value=[],
                                            multi=True,
                                            placeholder="Select CCM names",
                                            style={"width": "360px"},
                                        ),
                                        label="Filter by CCM Name",
                                        htmlFor="ccm-filter",
                                        className="dmc",
                                        styles={"label": {"marginBottom": "6px"}},
                                    ),
                                    dmc.Stack(
                                        gap=6,
                                        children=[
                                            dmc.Text("Last N days", size="sm", fw=600),
                                            dmc.NumberInput(
                                                id="last-n-days",
                                                value=30,
                                                min=1,
                                                step=1,
                                                style={"width": "160px"},
                                            ),
                                        ],
                                    ),
                                    dmc.Button(
                                        [
                                            html.I(className="bi bi-download", style={"marginRight": "10px", "fontSize": "1.1em"}),
                                            "Download CSV",
                                        ],
                                        id="ccm-download-btn",
                                        n_clicks=0,
                                        className="download-btn",
                                    ),
                                    dcc.Download(id="ccm-download-csv"),
                                ],
                            ),
                        ],
                    ),
                    dmc.Paper(
                        withBorder=True,
                        p="md",
                        radius="md",
                        children=[
                            dcc.Loading(
                                id="ccm-runtime-loading",
                                children=[dcc.Graph(id="ccm-runtime-plot")],
                                type="default",
                            )
                        ],
                    ),
                    dmc.Stack(
                        gap="sm",
                        children=[
                            dmc.Title("Full Dataset Table", order=3),
                            dmc.Paper(
                                withBorder=True,
                                p="md",
                                radius="md",
                                children=[
                                    dcc.Loading(
                                        id="ccm-table-loading",
                                        children=[
                                            dag.AgGrid(
                                                id="ccm-table",
                                                columnDefs=[],
                                                rowData=[],
                                                defaultColDef={
                                                    "resizable": True,
                                                    "sortable": True,
                                                    "filter": True,
                                                },
                                                dashGridOptions={
                                                    "pagination": True,
                                                    "paginationPageSize": 15,
                                                    "theme": {
                                                        "function": (
                                                            "themeQuartz.withParams({"
                                                            "accentColor: 'var(--mantine-primary-color-filled)', "
                                                            "fontFamily: 'var(--mantine-font-family)', "
                                                            "headerFontWeight: 'bold'"
                                                            "})"
                                                        )
                                                    },
                                                },
                                                style={"height": "600px"},
                                            )
                                        ],
                                        type="default",
                                    ),
                                ],
                            ),
                        ],
                    ),
                    html.Div(id="ccm-table-theme-dummy"),
                ],
            )
        ],
    )

# Load data and populate dropdowns/table columns
@callback(
    Output("ccm-data-store", "data"),
    Output("testrig-location-filter", "options"),
    Output("ccm-filter", "options"),
    Output("ccm-table", "columnDefs"),
    Output("testrig-location-filter", "value"),
    Output("ccm-filter", "value"),
    Input("ccm-runtime-plot", "id"),  # Dummy input to trigger on page load
)
def load_ccm_data(_):
    df = get_table_as_df("sherlock", "ccm_overview")
    if df.empty:
        return [], [], [], [], [], []
    for col in ["start_time", "end_time"]:
        # Convert only if value is not null and is numeric
        df[col] = pd.to_numeric(df[col], errors="coerce")
        df[col] = pd.to_datetime(df[col], errors="coerce", unit="ms")
    df = df[df["sample_id"].notna() & (df["sample_id"] != "null")]
    df["ccm_name"] = df["ccm_name"].fillna("Unknown")
    testrig_options = [
        {"label": x, "value": x}
        for x in sorted(df["testrig_label"].dropna().unique())
    ]
    ccm_options = [
        {"label": c, "value": c}
        for c in sorted(df["ccm_name"].unique())
    ]
    columnDefs = [{"field": col} for col in df.columns]
    
    # Set default values to show all options
    testrig_values = [x["value"] for x in testrig_options]
    ccm_values = [x["value"] for x in ccm_options]
    
    return df.to_dict("records"), testrig_options, ccm_options, columnDefs, testrig_values, ccm_values

# Main Gantt callback
@callback(
    Output("ccm-runtime-plot", "figure"),
    Output("ccm-table", "rowData"),
    Input("ccm-filter", "value"),
    Input("testrig-location-filter", "value"),
    Input("last-n-days", "value"),
    Input("theme-store", "data"),
    State("ccm-data-store", "data"),
)
def update_ccm_plot(ccm_filter, testrig_location_filter, days_selected, theme_store, data_store):
    if not data_store:
        return no_update, no_update

    df = pd.DataFrame(data_store)
    for col in ["start_time", "end_time"]:
        df[col] = pd.to_datetime(df[col], errors="coerce")
    is_dark = theme_store == "dark"
    template = "plotly_dark" if is_dark else "plotly"
    font_color = "#ffffff" if is_dark else "#000000"

    dff = df.copy()

    # Time filter
    days = days_selected if days_selected and days_selected > 0 else 30
    cutoff = dff["end_time"].max() - pd.Timedelta(days=days)
    dff = dff[dff["end_time"] >= cutoff]

    # CCM filter
    if ccm_filter:
        dff = dff[dff["ccm_name"].isin(ccm_filter)]

    # Testrig location filter
    if testrig_location_filter:
        dff = dff[dff["testrig_label"].isin(testrig_location_filter)]

    # Sort
    dff = dff.sort_values(
        by=["testrig_id", "order_id", "start_time"],
        ascending=[True, True, True],
    )

    dff["order_id"] = pd.Categorical(
        dff["order_id"],
        categories=dff["order_id"].unique(),
        ordered=True,
    )

    # Text fields
    dff["bar_text"] = dff["ccm_name"]
    dff["total_runtime_hours"] = dff["total_runtime"].round(2)
    dff["right_label"] = dff["total_runtime_hours"].map(lambda x: f"{x:.2f} h")
    dff["start_time_fmt"] = dff["start_time"].dt.strftime("%Y-%m-%d %H:%M")
    dff["end_time_fmt"] = dff["end_time"].dt.strftime("%Y-%m-%d %H:%M")
    dff["end_time_fmt"] = dff["end_time_fmt"].fillna("Ongoing")

    # Build Gantt
    fig = px.timeline(
        dff,
        x_start="start_time",
        x_end="end_time",
        y="order_id",
        color="testrig_label",
        text="bar_text",
        custom_data=[
            "testrig_label",
            "order_id",
            "sample_id",
            "ccm_name",
            "PTL_name",
            "GDL_name",
            "active_area_per_cell",
            "total_runtime_hours",
            "start_time_fmt",
            "end_time_fmt",
        ],
        title=f"CCM Test Timelines (Last {days} Days)",
        template=template,
    )

    fig.update_traces(
        textposition="inside",
        insidetextanchor="middle",
        textfont=dict(color="white"),
    )

    fig.update_traces(
        hovertemplate=
        "<b>Testrig Location:</b> %{customdata[0]}<br>"
        "<b>Order ID:</b> %{customdata[1]}<br>"
        "<b>Sample ID:</b> %{customdata[2]}<br>"
        "<b>CCM Name:</b> %{customdata[3]}<br>"
        "<b>PTL Name:</b> %{customdata[4]}<br>"
        "<b>GDL Name:</b> %{customdata[5]}<br>"
        "<b>Active Area per Cell:</b> %{customdata[6]}<br>"
        "<b>Total Run Time (hours):</b> %{customdata[7]:.2f} h<br>"
        "<b>Start Date:</b> %{customdata[8]}<br>"
        "<b>End Date:</b> %{customdata[9]}"
        "<extra></extra>"
    )

    for rig in dff["testrig_label"].dropna().unique():
        rig_df = dff[dff["testrig_label"] == rig]
        fig.add_scatter(
            x=rig_df["end_time"],
            y=rig_df["order_id"],
            text=" " + rig_df["right_label"],
            mode="text",
            textposition="middle right",
            legendgroup=str(rig),
            showlegend=False,
            hoverinfo="skip",
        )

    fig.update_yaxes(
        autorange="reversed",
        title="Order ID",
        categoryorder="array",
        categoryarray=dff["order_id"].astype(str).unique(),
    )

    fig.update_xaxes(
        title="Time",
        showgrid=True,
    )

    fig.update_layout(
        height=1000,
        font=dict(color=font_color),
        legend_title="Testrig Location",
        hoverlabel=dict(align="left"),
    )

    fig.add_vline(
        x=pd.Timestamp.utcnow(),
        line_width=2,
        line_dash="dot",
        line_color="red",
    )

    return fig, dff.to_dict("records")

# Download callback
@callback(
    Output("ccm-download-csv", "data"),
    Input("ccm-download-btn", "n_clicks"),
    State("ccm-table", "rowData"),
    State("last-n-days", "value"),
    prevent_initial_call=True,
)
def download_ccm_table(n_clicks, table_data, days_selected):
    if not table_data:
        return no_update
    days = days_selected if days_selected and days_selected > 0 else 30
    df_filtered = pd.DataFrame(table_data)
    return send_data_frame(
        df_filtered.to_csv,
        f"ccm_runtime_last_{days}_days.csv",
        index=False,
    )

# Clientside callback to update AG Grid theme based on Mantine color scheme
clientside_callback(
    """
    (theme) => {
       document.documentElement.setAttribute('data-ag-theme-mode', theme === 'dark' ? 'dark' : 'light');  
       return window.dash_clientside.no_update;        
    }
    """,
    Output("ccm-table-theme-dummy", "children"),
    Input("theme-store", "data"),
)

layout = ccm_overview_layout