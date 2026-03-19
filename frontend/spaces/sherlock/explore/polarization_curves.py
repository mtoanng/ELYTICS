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
                            dmc.Group(
                                gap="md",
                                align="flex-end",
                                style={"flexWrap": "nowrap", "overflowX": "auto"},
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
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )

layout = polarization_curves_layout