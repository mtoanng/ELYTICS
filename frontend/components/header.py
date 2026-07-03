import os

from dash.dependencies import Input, Output, State
from dash import callback, clientside_callback, html
import dash_mantine_components as dmc
from dash_iconify import DashIconify

from components.sidebar import SIDEBAR_STRUCTURE
from config.access_config import SPACE_ACCESS_MAP

IS_DEVELOPMENT = os.getenv("ENVIRONMENT", "development").lower() == "development"

SPACE_SELECTOR_META = {
    "home": {"title": "Home", "subtitle": "", "icon": "tabler:home"},
    "elytics": {
        "title": "Elytics",
        "subtitle": "CO2 analytics",
        "icon": "tabler:chart-line",
    },
}


def _space_option_label(space_name: str) -> str:
    meta = SPACE_SELECTOR_META.get(space_name, {})
    title = meta.get("title", space_name.capitalize())
    return title


def _space_subtitle(space_name: str) -> str:
    return SPACE_SELECTOR_META.get(space_name, {}).get("subtitle", "")


def _build_search_options():
    options = []
    for space, groups in SIDEBAR_STRUCTURE.items():
        general_items = []
        if None in groups:
            for page in groups[None]:
                if page.get("path") == "home" or page.get("label", "").strip().lower() == "home":
                    continue
                general_items.append(
                    {
                        "label": page["label"],
                        "value": f"/{space}/{page['path']}",
                    }
                )

        if general_items:
            options.append(
                {
                    "group": f"{_space_option_label(space)} - General",
                    "items": general_items,
                }
            )

        for group, group_data in groups.items():
            if group is None or isinstance(group_data, list):
                continue

            # group_data is now a dict with "path" and "pages"
            group_path = group_data.get("path", group.lower().replace(" ", "-"))
            pages = group_data.get("pages", [])

            if not pages:
                continue

            grouped_items = []
            for page in pages:
                value = f"/{space}/{page['path']}" if not group_path else f"/{space}/{group_path}/{page['path']}"
                grouped_items.append(
                    {
                        "label": page["label"],
                        "value": value,
                    }
                )

            options.append(
                {
                    "group": f"{_space_option_label(space)} - {group}",
                    "items": grouped_items,
                }
            )

    return options

def _create_search():
    return dmc.Select(
        id="header-search",
        placeholder="Search",
        searchable=True,
        clearable=True,
        leftSection=DashIconify(icon="mingcute:search-3-line"),
        data=_build_search_options(),
        w=260,
        nothingFoundMessage="No matches",
        visibleFrom="sm",
        comboboxProps={"shadow": "md"},
    )

def _create_space_selector():
    # Initial placeholder - will be updated by callback after auth
    return dmc.Select(
        id="space-selector",
        data=[],
        placeholder="Select Space",
        leftSectionPointerEvents="none",
        leftSection=DashIconify(
            id="space-selector-left-icon",
            icon="tabler:home",
            width=24,
        ),
        rightSectionPointerEvents="none",
        rightSectionWidth=110,
        rightSection=dmc.Text(
            id="space-selector-subtitle",
            size="xs",
            c="dimmed",
            style={
                "fontStyle": "italic",
                "whiteSpace": "nowrap",
                "width": "100%",
                "textAlign": "right",
                "paddingRight": "10px",
            },
        ),
        checkIconPosition="right",
        maxDropdownHeight=300,
        w=300,
        size="md",
        value=None,
        styles={
            "input": {
                "fontWeight": 700,
                "fontSize": "18px",
                "paddingLeft": "48px",
            }
        },
    )


def _create_link(icon, href):
    return dmc.Anchor(
        dmc.ActionIcon(
            DashIconify(icon=icon, width=22),
            variant="transparent",
            size="lg",
        ),
        href=href,
        target="_blank",
        visibleFrom="xs",
    )


def header_layout():
    dev_banner = None
    if IS_DEVELOPMENT:
        dev_banner = dmc.Text(
            "DEVELOPMENT",
            fw=900,
            size="32px",
            c="red",
            style={"letterSpacing": "1px"},
        )

    return dmc.Group(
        justify="space-between",
        h="100%",
        px=20,
        children=[
            dmc.Group(
                gap="md",
                children=[
                    _create_space_selector(),
                ],
            ),
            *(
                [dmc.Group(gap=0, justify="center", children=[dev_banner])]
                if dev_banner
                else []
            ),
            dmc.Group(
                gap="md",
                children=[
                    _create_search(),
                    _create_link("radix-icons:reader", "https://inside-docupedia.bosch.com/confluence/spaces/ELYSTACK/pages/6751345063/HOLMES+Application"),
                    dmc.Switch(
                        id="theme-switch",
                        checked=False,
                        size="md",
                        color="gray",
                        persistence=True,
                        persistence_type="local",
                        onLabel=DashIconify(icon="radix-icons:moon", width=15, color="var(--mantine-color-yellow-6)"),
                        offLabel=DashIconify(icon="radix-icons:sun", width=15, color="var(--mantine-color-yellow-8)"),
                    ),
                    html.Div(id="bosch-logo-div"),
                ],
            ),
        ],
    )

layout = header_layout


# Callbacks registered below

@callback(
    [Output("space-selector", "data"),
     Output("space-selector", "value")],
    Input("url", "pathname"),
    State("space-selector", "value"),
    prevent_initial_call=False
)
def update_space_selector(pathname, current_value):
    options = [
        {
            "label": _space_option_label("home"),
            "value": "home",
            "disabled": False,
        },
        {
            "group": "Spaces",
            "items": [
                {
                    "label": _space_option_label(space_path.strip("/")),
                    "value": space_path.strip("/"),
                    "disabled": False,
                }
                for space_path in SPACE_ACCESS_MAP.keys()
            ],
        },
    ]

    if pathname == "/" or pathname == "":
        return options, "home"

    current_space = pathname.split("/")[1] if pathname and len(pathname.split("/")) > 1 else None
    if current_space:
        return options, current_space

    return options, "home"


@callback(
    Output("space-selector-left-icon", "icon"),
    Input("space-selector", "value"),
    prevent_initial_call=False,
)
def update_space_selector_icon(space):
    selected = (space or "home").strip().lower()
    return SPACE_SELECTOR_META.get(selected, SPACE_SELECTOR_META["home"])["icon"]


@callback(
    Output("space-selector-subtitle", "children"),
    Input("space-selector", "value"),
    prevent_initial_call=False,
)
def update_space_selector_subtitle(space):
    selected = (space or "home").strip().lower()
    return _space_subtitle(selected)


@callback(
    Output("bosch-logo-div", "children"),
    Input("theme-store", "data"),
    prevent_initial_call=False
)
def update_bosch_logo(theme):
    if theme == "dark":
        src = "/assets/Bosch_symbol_logo_black.png"
        class_name = "header-logo-right invert-logo"
    else:
        src = "/assets/Bosch_symbol_logo_black_red.png"
        class_name = "header-logo-right"
    return html.Img(
        src=src,
        height="50px",
        className=class_name,
        style={"cursor": "pointer", "display": "block", "alignSelf": "center"},
    )


# Clientside callbacks - these reference components that may not exist initially
clientside_callback(
    """
    function(space) {
        // Don't do anything if space is null or undefined
        if (!space) {
            return window.dash_clientside.no_update;
        }
        
        // Only navigate if user manually changed the selector AND current URL doesn't match
        if (window.dash_clientside.callback_context.triggered.length > 0) {
            const trigger = window.dash_clientside.callback_context.triggered[0];
            const currentPath = window.location.pathname;
            const currentSpace = currentPath.split('/')[1];
            
            // Only navigate if:
            // 1. Triggered by space-selector value change
            // 2. Selected space is different from current URL space
            if (trigger.prop_id === 'space-selector.value' && space) {
                if (space === 'home' && currentPath !== '/') {
                    window.location.href = '/';
                    return window.dash_clientside.no_update;
                }
                if (space !== 'home' && space !== currentSpace) {
                    const defaultRoutes = {
                        elytics: '/elytics/co-reporting'
                    };
                    window.location.href = defaultRoutes[space] || ('/' + space + '/home');
                }
            }
        }
        
        return window.dash_clientside.no_update;
    }
    """,
    Output("space-selector", "id"),
    Input("space-selector", "value"),
    prevent_initial_call=True,
)

clientside_callback(
    """
    function(checked) {
        const logoDiv = document.getElementById('bosch-logo-div');
        if (logoDiv && logoDiv.querySelector('img')) {
            const img = logoDiv.querySelector('img');
            if (checked) {
                img.src = '/assets/Bosch_symbol_logo_black.png';
                img.classList.add('invert-logo');
            } else {
                img.src = '/assets/Bosch_symbol_logo_black_red.png';
                img.classList.remove('invert-logo');
            }
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output("theme-switch", "id"),
    Input("theme-switch", "checked"),
    prevent_initial_call=True,
)

clientside_callback(
    """
    function(value) {
        if (value) {
            window.location.href = value;
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output("header-search", "value"),
    Input("header-search", "value"),
    prevent_initial_call=True,
)

clientside_callback(
    """
    function(switchOn, storeId) {
        let theme;
        if (switchOn !== null && switchOn !== undefined) {
            // User switched theme
            theme = switchOn ? 'dark' : 'light';
        } else {
            // Auto-detect system theme on first load
            theme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        }
        document.documentElement.setAttribute('data-mantine-color-scheme', theme);
        return theme;
    }
    """,
    Output("theme-store", "data"),
    Input("theme-switch", "checked"),
    Input("theme-store", "id"),
    prevent_initial_call=True,
)