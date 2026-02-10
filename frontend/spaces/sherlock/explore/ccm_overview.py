from dash_auth import protected
from dash import html, dcc, callback, Output, Input, State, register_page, no_update
from dash import dash_table
from dash.dcc.express import send_data_frame

import pandas as pd
import plotly.express as px

from services.backend_service import get_table_as_df
from services.auth import protected

register_page(
    __name__,
    path="/sherlock/data-exploration/ccm-overview",
    title="CCM Overview Space"
)

@protected(
    html.Div("Access denied", style={"color": "red", "padding": "2rem"}),
    groups=["IdM2BCD_holmes_pemely_user"]
)
def ccm_overview_layout():
    return html.Div([
        html.H2("CCM Runtime Overview", style={"marginTop": "1rem"}),
        html.P("Timeline view of stack-level CCM executions."),

        dcc.Store(id="ccm-data-store"),

        html.Div([
            html.Div([
                html.Label("Filter by Testrig Location"),
                dcc.Dropdown(
                    id="testrig-location-filter",
                    options=[],  # Populated by callback
                    multi=True,
                    placeholder="Select one or more locations",
                ),
            ], style={
                "width": "350px",
                "minWidth": "260px",
            }),

            html.Div([
                html.Label("Filter by CCM Name"),
                dcc.Dropdown(
                    id="ccm-filter",
                    options=[],  # Populated by callback
                    multi=True,
                    placeholder="Select CCM names",
                )
            ], style={
                "width": "500px",
                "minWidth": "280px",
            }),

            html.Div([
                html.Div([
                    html.Label("Time Range"),
                    html.Div([
                        dcc.RadioItems(
                            id="time-range",
                            options=[
                                {"label": " Last 7 Days", "value": 7},
                                {"label": " Last 14 Days", "value": 14},
                                {"label": " Last 30 Days", "value": 30},
                                {"label": " Last 60 Days", "value": 60},
                                {"label": " Custom", "value": "custom"},
                            ],
                            value=30,
                            labelStyle={
                                "display": "inline-block",
                                "marginRight": "16px",
                            },
                        ),
                        html.Div([
                            html.Span("Last"),
                            dcc.Input(
                                id="custom-days",
                                type="number",
                                min=1,
                                step=1,
                                placeholder="N",
                                style={
                                    "width": "90px",
                                    "margin": "0 6px",
                                    "padding": "6px 10px",
                                    "borderRadius": "8px",
                                    "border": "1px solid #ccc",
                                    "fontSize": "14px",
                                },
                            ),
                            html.Span("Days"),
                        ], style={
                            "display": "inline-flex",
                            "alignItems": "center",
                            "marginRight": "16px",
                        }),
                    ], style={
                        "display": "flex",
                        "alignItems": "center",
                    }),
                ]),

                html.Button(
                    [
                        html.I(className="bi bi-download", style={"marginRight": "15px", "fontSize": "1.2em"}),
                        "Download CSV",
                    ],
                    id="ccm-download-btn",
                    n_clicks=0,
                    className="download-btn",
                    style={
                        "display": "flex",
                        "alignItems": "center",
                        "borderRadius": "6px",
                        "padding": "6px 12px",
                        "fontWeight": "600",
                        "fontSize": "14px",
                        "cursor": "pointer",
                        "whiteSpace": "nowrap",
                        "marginLeft": "20px",
                        "marginTop": "23px",
                    },
                ),
                dcc.Download(id="ccm-download-csv"),
            ], style={"display": "flex", "alignItems": "center", "flex": "1"}),
        ], style={"display": "flex", "gap": "30px", "width": "100%"}),

        html.Br(),
        html.Br(),

        dcc.Loading(
            id="ccm-runtime-loading",
            children=[dcc.Graph(id="ccm-runtime-plot")],
            type="default"
        ),

        html.Br(),
        html.H3("Full Dataset Table"),

        dcc.Loading(
            id="ccm-table-loading",
            children=[
                dash_table.DataTable(
                    id="ccm-table",
                    columns=[],  # Populated by callback
                    data=[],
                    page_size=15,
                    style_table={"overflowX": "auto"},
                    style_cell={"fontSize": "12px"},
                )
            ],
            type="default"
        ),
    ])

# Load data and populate dropdowns/table columns
@callback(
    Output("ccm-data-store", "data"),
    Output("testrig-location-filter", "options"),
    Output("ccm-filter", "options"),
    Output("ccm-table", "columns"),
    Input("ccm-runtime-plot", "id"),  # Dummy input to trigger on page load
)
def load_ccm_data(_):
    df = get_table_as_df("ccm_overview")
    if df.empty:
        return [], [], [], []
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
    columns = [{"name": col, "id": col} for col in df.columns]
    return df.to_dict("records"), testrig_options, ccm_options, columns

# Main Gantt callback
@callback(
    Output("ccm-runtime-plot", "figure"),
    Output("ccm-table", "data"),
    Input("ccm-filter", "value"),
    Input("testrig-location-filter", "value"),
    Input("time-range", "value"),
    Input("custom-days", "value"),
    Input("theme-store", "data"),
    State("ccm-data-store", "data"),
)
def update_ccm_plot(ccm_filter, testrig_location_filter, days_selected, custom_days, theme_store, data_store):
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
    if days_selected == "custom":
        days = custom_days if custom_days and custom_days > 0 else 30
    else:
        days = days_selected
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
        by=["testrig_id", "test_id", "start_time"],
        ascending=[True, True, True],
    )

    dff["test_id"] = pd.Categorical(
        dff["test_id"],
        categories=dff["test_id"].unique(),
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
        y="test_id",
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
            y=rig_df["test_id"],
            text=" " + rig_df["right_label"],
            mode="text",
            textposition="middle right",
            legendgroup=str(rig),
            showlegend=False,
            hoverinfo="skip",
        )

    fig.update_yaxes(
        autorange="reversed",
        title="Test ID",
        categoryorder="array",
        categoryarray=dff["test_id"].astype(str).unique(),
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
    State("ccm-table", "data"),
    State("time-range", "value"),
    State("custom-days", "value"),
    prevent_initial_call=True,
)
def download_ccm_table(n_clicks, table_data, days_selected, custom_days):
    if not table_data:
        return no_update
    days = custom_days if custom_days and custom_days > 0 else days_selected
    df_filtered = pd.DataFrame(table_data)
    return send_data_frame(
        df_filtered.to_csv,
        f"ccm_runtime_last_{days}_days.csv",
        index=False,
    )

layout = ccm_overview_layout