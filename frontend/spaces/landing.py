import dash_mantine_components as dmc
from dash import register_page, Output, Input, clientside_callback, html, callback
from dash_iconify import DashIconify
from components.changelog import build_update_cards
from config.access_config import SPACE_ACCESS_MAP
from dash_auth import list_groups
import json
from pathlib import Path

register_page(__name__, path="/", title="HOLMES - Home")

# Space information with descriptions and versions
SPACE_INFO = {
    "sherlock": {
        "title": "Sherlock",
        "description": "Advanced analytics and AI/ML model management for predictive insights and data exploration.",
        "version": "v2.1.0",
        "color": "blue",
        "icon": "tabler:chart-line",
    },
    "watson": {
        "title": "Watson",
        "description": "Intelligent data processing and natural language analysis for enhanced decision-making.",
        "version": "v1.8.3",
        "color": "cyan",
        "icon": "tabler:brain",
    },
    "mycroft": {
        "title": "Mycroft",
        "description": "Data visualization and reporting tools for comprehensive business intelligence.",
        "version": "v2.0.1",
        "color": "grape",
        "icon": "tabler:chart-bar",
    },
    "enola": {
        "title": "Enola",
        "description": "Management and administration tools for system configuration and user access control.",
        "version": "v1.5.0",
        "color": "red",
        "icon": "tabler:settings",
    },
}

ROOT_CHANGELOG_LABEL = "HOLMES"
ROOT_CHANGELOG_COLOR = "blue"


def _load_changelog_json(changelog_path: Path) -> dict:
    if not changelog_path.exists():
        return {}
    with changelog_path.open(encoding="utf-8") as handle:
        return json.load(handle)

def _create_space_card(space_name, space_data, has_access=False):
    """Create a card for a single space."""
    required_groups = SPACE_ACCESS_MAP.get(f"/{space_name}", [])
    required_role = required_groups[0] if required_groups else "No role required"
    
    # Determine icon and color based on access
    if has_access:
        access_icon = "tabler:circle-check"
        access_color = "green"
        button_text = f"Enter {space_data['title']}"
        button_icon = "tabler:arrow-right"
        button_variant = "light"
    else:
        access_icon = "tabler:lock"
        access_color = "gray"
        button_text = "Request Access"
        button_icon = "tabler:lock-open"
        button_variant = "outline"
    
    return dmc.Card(
        children=[
            dmc.CardSection(
                dmc.Group(
                    [
                        dmc.ThemeIcon(
                            DashIconify(icon=space_data["icon"], width=28),
                            size="xl",
                            radius="md",
                            color=space_data["color"],
                            variant="light",
                        ),
                        dmc.Badge(
                            space_data["version"],
                            color=space_data["color"],
                            variant="dot",
                        ),
                    ],
                    justify="space-between",
                ),
                inheritPadding=True,
                py="md",
            ),
            dmc.Stack(
                [
                    dmc.Title(
                        space_data["title"],
                        order=3,
                    ),
                    dmc.Text(
                        space_data["description"],
                        size="sm",
                        c="dimmed",
                        style={"minHeight": "60px"},
                    ),
                    dmc.Group(
                        [
                            DashIconify(icon=access_icon, width=16, color=access_color),
                            dmc.Code(
                                required_role,
                                style={"fontSize": "11px"},
                            ),
                        ],
                        gap="xs",
                    ),
                ],
                gap="sm",
            ),
            dmc.Button(
                [
                    DashIconify(icon=button_icon, width=18),
                    button_text,
                ],
                color=space_data["color"],
                fullWidth=True,
                mt="md",
                radius="md",
                variant=button_variant,
                id={"type": "space-nav-btn", "index": space_name},
            ),
        ],
        withBorder=True,
        shadow="sm",
        radius="md",
        p="lg",
    )


def create_landing():
    """Create the landing page layout."""
    # Get current user's groups
    user_groups = list_groups()
    
    # Determine which spaces the user has access to
    user_access = {}
    for space_name in SPACE_INFO.keys():
        required_groups = SPACE_ACCESS_MAP.get(f"/{space_name}", [])
        has_access = user_groups and any(group in user_groups for group in required_groups)
        user_access[space_name] = has_access
    
    return dmc.Container(
        [
            # Hidden div for callback output
            html.Div(id="landing-nav-trigger", style={"display": "none"}),
            
            # Header section
            dmc.Stack(
                [
                    dmc.Center(
                        dmc.Stack(
                            [
                                dmc.Title(
                                    "HOLMES Application Suite",
                                    order=1,
                                    style={"textAlign": "center"},
                                ),
                                dmc.Text(
                                    "Select a space to begin your journey",
                                    size="lg",
                                    c="dimmed",
                                    style={"textAlign": "center"},
                                ),
                            ],
                            gap="xs",
                        ),
                    ),
                    
                    # Space cards grid
                    dmc.SimpleGrid(
                        cols={"base": 1, "sm": 2, "lg": 4},
                        spacing="lg",
                        children=[
                            _create_space_card(space_name, space_data, user_access.get(space_name, False))
                            for space_name, space_data in SPACE_INFO.items()
                        ],
                    ),
                    
                    # Divider
                    dmc.Divider(
                        label="Application Updates",
                        labelPosition="center",
                        my="xl",
                    ),

                    # Filter
                    dmc.MultiSelect(
                        id="changelog-space-filter",
                        data=[
                            {"value": space_name, "label": SPACE_INFO[space_name]["title"]}
                            for space_name in SPACE_INFO.keys()
                        ],
                        value=list(SPACE_INFO.keys()),
                        label="Filter by space",
                        placeholder="Select spaces",
                        searchable=True,
                        clearable=False,
                        w="100%",
                    ),
                    
                    # Update log section (flat list)
                    dmc.Stack(
                        [
                            dmc.Title(
                                "Updates",
                                order=2,
                            ),
                            dmc.Stack(
                                id="changelog-list",
                                gap="md",
                            ),
                        ],
                        gap="lg",
                    ),
                ],
                gap="xl",
                py="xl",
            ),
        ],
        size="xl",
    )


layout = create_landing

@callback(
    Output("changelog-list", "children"),
    Input("changelog-space-filter", "value"),
    prevent_initial_call=False
)
def update_changelog_list(selected_spaces):
    selected_spaces = selected_spaces or []
    cards = []

    base_path = Path(__file__).resolve().parents[1]
    root_changelog = _load_changelog_json(base_path / "changelog.json")
    cards.extend(build_update_cards(root_changelog, ROOT_CHANGELOG_LABEL, ROOT_CHANGELOG_COLOR))

    for space_name in selected_spaces:
        space_path = base_path / "spaces" / space_name / "changelog.json"
        space_changelog = _load_changelog_json(space_path)
        cards.extend(
            build_update_cards(
                space_changelog,
                SPACE_INFO[space_name]["title"],
                SPACE_INFO[space_name]["color"],
            )
        )

    return cards

# Navigation callback for space cards
clientside_callback(
    """
    function(n1, n2, n3, n4) {
        const triggered = window.dash_clientside.callback_context.triggered;
        if (triggered && triggered.length > 0 && triggered[0].prop_id !== '.') {
            try {
                const propId = JSON.parse(triggered[0].prop_id.split('.')[0]);
                const spaceName = propId.index;
                if (spaceName) {
                    window.location.href = '/' + spaceName + '/home';
                }
            } catch (e) {
                console.error('Error parsing callback context:', e);
            }
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output("landing-nav-trigger", "children"),
    Input({"type": "space-nav-btn", "index": "sherlock"}, "n_clicks"),
    Input({"type": "space-nav-btn", "index": "watson"}, "n_clicks"),
    Input({"type": "space-nav-btn", "index": "mycroft"}, "n_clicks"),
    Input({"type": "space-nav-btn", "index": "enola"}, "n_clicks"),
    prevent_initial_call=True,
)