from dash.dependencies import Input, Output, State
from dash import callback, clientside_callback
from dash import html, dcc
import dash_mantine_components as dmc
from dash_iconify import DashIconify

from components.sidebar import SIDEBAR_STRUCTURE
from dash_auth import list_groups


def _build_search_options():
    options = []
    for space, groups in SIDEBAR_STRUCTURE.items():
        if None in groups:
            for page in groups[None]:
                options.append({
                    "label": f"{space.title()} / {page['label']}",
                    "value": f"/{space}/{page['path']}"
                })
        for group, group_data in groups.items():
            if group is None or isinstance(group_data, list):
                continue
            
            # group_data is now a dict with "path" and "pages"
            group_path = group_data.get("path", group.lower().replace(" ", "-"))
            pages = group_data.get("pages", [])
            
            for page in pages:
                options.append({
                    "label": f"{space.title()} / {group} / {page['label']}",
                    "value": f"/{space}/{group_path}/{page['path']}"
                })
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
        leftSection=html.Img(
            id="space-logo-img",
            src="/assets/sherlock_logo.png",
            height="32px",
            style={"marginLeft": "8px"},
        ),
        w=240,
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

@callback(
    [Output("space-selector", "data"),
     Output("space-selector", "value")],
    Input("url", "pathname"),
    State("space-selector", "value"),
    prevent_initial_call=False
)
def update_space_selector(pathname, current_value):
    # Map group names to allowed spaces
    group_space_map = {
        "IdM2BCD_holmes_pemely_user": ["sherlock", "watson", "mycroft"],
        "IdM2BCD_holmes_pemely_management": ["enola"],
    }

    # Get current user's groups
    user_groups = list_groups()
    allowed_spaces = set()
    if user_groups:
        for group, spaces in group_space_map.items():
            if group in user_groups:
                allowed_spaces.update(spaces)

    # Define all spaces and their logos
    spaces = [
        {"label": "Mycroft", "value": "mycroft"},
        {"label": "Sherlock", "value": "sherlock"},
        {"label": "Enola", "value": "enola"},
        {"label": "Watson", "value": "watson"},
    ]

    # Build options, disabling those not allowed
    options = []
    for space in spaces:
        options.append({
            "label": space["label"],
            "value": space["value"],
            "disabled": space["value"] not in allowed_spaces,
        })

    # Get current space from URL
    current_space = pathname.split("/")[1] if pathname and len(pathname.split("/")) > 1 else None
    
    # Only update value if it's different from URL space (prevents loop)
    if current_space and current_space in allowed_spaces:
        return options, current_space
    
    # Default to first allowed space if no valid space in URL
    default_value = next((s["value"] for s in spaces if s["value"] in allowed_spaces), None)
    return options, default_value

# Combined callback for logo switching and navigation
clientside_callback(
    """
    function(space) {
        const logoMap = {
            "mycroft": "/assets/mycroft_logo.png",
            "sherlock": "/assets/sherlock_logo.png",
            "enola": "/assets/enola_logo.png",
            "watson": "/assets/watson_logo.png"
        };
        const img = document.getElementById('space-logo-img');
        if (img && logoMap[space]) {
            img.src = logoMap[space];
        }
        
        // Only navigate if user manually changed the selector AND current URL doesn't match
        if (window.dash_clientside.callback_context.triggered.length > 0) {
            const trigger = window.dash_clientside.callback_context.triggered[0];
            const currentPath = window.location.pathname;
            const currentSpace = currentPath.split('/')[1];
            
            // Only navigate if:
            // 1. Triggered by space-selector value change
            // 2. Selected space is different from current URL space
            if (trigger.prop_id === 'space-selector.value' && space && space !== currentSpace) {
                window.location.href = '/' + space + '/home';
            }
        }
        
        return window.dash_clientside.no_update;
    }
    """,
    Output("space-selector", "id"),
    Input("space-selector", "value"),
    prevent_initial_call=True,
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
        style={"cursor": "pointer"},
    )

# Instant logo update on client side
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
)