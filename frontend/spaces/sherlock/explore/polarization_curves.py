from dash import (
    html,
    dcc,
    callback,
    Output,
    Input,
    State,
    register_page,
    no_update,
    clientside_callback,
)
from dash_iconify import DashIconify
import dash_mantine_components as dmc
import dash_ag_grid as dag

register_page(
    __name__, path="/sherlock/data-exploration/polarization-curves", 
    title="HOLMES - Sherlock - Polarization Curves")

USAGE_BLOCKQUOTE_TEXT = [
    "This page is under construction. Please check back later for updates." 
]

def polarization_curves_layout():
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
                                    dmc.Title("Polarization Curve viewer", order=2),
                                    dmc.ActionIcon(
                                        DashIconify(icon="material-symbols:info-outline", width=20),
                                        id="polcurve-usage-toggle",
                                        variant="subtle",
                                        color="blue",
                                        size="md",
                                        radius="xl",
                                    ),
                                ],
                            ),
                            dmc.Text("This page provides an overview of all polarization curves.", c="dimmed"),
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
                                id="polcurve-usage-collapse",
                            ),
                        ],
                    ),
                    dmc.Paper(
                        withBorder=True,
                        p="md",
                        radius="md",
                        children=[
                            dmc.Stack(
                                gap="md",
                                children=[
                                    dmc.Group(
                                        gap="md",
                                        align="flex-start",
                                        style={"flexWrap": "wrap"},
                                        children=[
                                            dmc.InputWrapper(
                                                dcc.Dropdown(
                                                    id="polcurve-order-id-filter",
                                                    options=[],
                                                    value=[],
                                                    multi=True,
                                                    searchable=True,
                                                    clearable=True,
                                                    placeholder="Select order IDs",
                                                    style={"width": "100%"},
                                                ),
                                                label="Order ID",
                                                htmlFor="polcurve-order-id-filter",
                                                className="dmc",
                                                styles={"label": {"marginBottom": "6px"}},
                                                style={"flex": "0 0 220px", "minWidth": "220px"},
                                            ),
                                            dmc.InputWrapper(
                                                dcc.Dropdown(
                                                    id="polcurve-sample-id-filter",
                                                    options=[],
                                                    value=[],
                                                    multi=True,
                                                    searchable=True,
                                                    clearable=True,
                                                    placeholder="Select order IDs",
                                                    style={"width": "100%"},
                                                ),
                                                label="Sample Name",
                                                htmlFor="polcurve-sample-id-filter",
                                                className="dmc",
                                                styles={"label": {"marginBottom": "6px"}},
                                                style={"flex": "0 0 220px", "minWidth": "220px"},
                                            ),
                                            dmc.Button(
                                                [
                                                    html.I(
                                                        className="bi bi-download",
                                                        style={
                                                            "marginRight": "10px",
                                                            "fontSize": "1.1em",
                                                        },
                                                    ),
                                                    "Download CSV",
                                                ],
                                                id="sample-download-btn",
                                                n_clicks=0,
                                                className="download-btn",
                                                style={"flex": "0 0 auto", "whiteSpace": "nowrap"},
                                            ),
                                        ],
                                    ),
                                    dmc.Group(
                                        gap="md",
                                        align="flex-end",
                                        style={"flexWrap": "nowrap", "overflowX": "auto"},
                                        children=[ 
                                            dmc.InputWrapper(
                                                # No 'label' prop here anymore
                                                style={"flex": "1", "minWidth": "300px"}, # Give it more space
                                                mb="xl",
                                                children=[
                                                    dmc.Group(
                                                        align="center",
                                                        gap="sm",
                                                        preventGrowOverflow=False, # Important for the slider to grow
                                                        children=[
                                                            # 1. The Label as a dmc.Text component
                                                            dmc.Text("Temperature (°C):", size="sm", style={"width": "120px"}),

                                                            # 2. The RangeSlider, taking up the remaining space
                                                            dmc.RangeSlider(
                                                                id="polcurve-temperature-filter",
                                                                min=0,
                                                                max=100,
                                                                value=[20, 80],
                                                                marks=[
                                                                    {"value": 0, "label": "0°"},
                                                                    {"value": 50, "label": "50°"},
                                                                    {"value": 100, "label": "100°"},
                                                                ],
                                                                style={"width": "200px"},
                                                            ),
                                                        ],
                                                    )
                                                ],
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )

layout = polarization_curves_layout