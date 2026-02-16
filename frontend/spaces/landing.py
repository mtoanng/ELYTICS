import dash_mantine_components as dmc
from dash import register_page, Output, Input, clientside_callback, html, callback
from dash_iconify import DashIconify
from config.access_config import SPACE_ACCESS_MAP
from dash_auth import list_groups
from pathlib import Path
import re

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

def _load_changelog(space_name: str):
    changelog_path = (
        Path(__file__).resolve().parents[1]
        / "content"
        / "changelogs"
        / f"{space_name}.md"
    )
    if not changelog_path.exists():
        return []

    text = changelog_path.read_text(encoding="utf-8")
    entries = []
    current = None

    header_re = re.compile(
        r"^(?P<version>[^()—]+?)\s*(\((?P<status>[^)]+)\))?\s*(—\s*(?P<date>.+))?$"
    )

    for line in text.splitlines():
        line = line.rstrip()
        if line.startswith("## "):
            if current:
                entries.append(current)
            header = line[3:].strip()
            match = header_re.match(header)
            if match:
                version = match.group("version").strip()
                status = (match.group("status") or "Released").strip()
                date = (match.group("date") or "").strip() or None
            else:
                version = header
                status = "Released"
                date = None

            current = {
                "version": version,
                "status": status,
                "date": date,
                "changes": [],
            }
        elif line.lstrip().startswith("- ") and current:
            indent = len(line) - len(line.lstrip())
            text_item = line.lstrip()[2:].strip()
            if indent >= 2:
                text_item = f"↳ {text_item}"
            current["changes"].append(text_item)

    if current:
        entries.append(current)

    return entries

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


def _create_update_log_item(update, space_name: str):
    """Create a single update log entry."""
    status_lower = update["status"].lower()
    is_wip = "work in progress" in status_lower or "wip" in status_lower
    date_text = "N/A" if is_wip or not update["date"] else update["date"]

    status_label = "Work in progress" if is_wip else "Released"
    status_color = "yellow" if is_wip else "green"

    return dmc.Paper(
        [
            dmc.Group(
                [
                    dmc.Group(
                        [
                            dmc.Badge(
                                SPACE_INFO[space_name]["title"],
                                color=SPACE_INFO[space_name]["color"],
                                variant="light",
                            ),
                            dmc.Badge(
                                status_label,
                                color=status_color,
                                variant="light",
                            ),
                            dmc.Badge(
                                update["version"],
                                color="green",
                                variant="dot",
                                size="lg",
                            ),
                        ],
                        gap="xs",
                    ),
                    dmc.Text(
                        date_text,
                        size="sm",
                        c="dimmed",
                    ),
                ],
                justify="space-between",
            ),
            dmc.List(
                [dmc.ListItem(change) for change in update["changes"]],
                spacing="xs",
                size="sm",
                mt="sm",
                icon=DashIconify(icon="tabler:circle-check", width=16, color="green"),
            ),
        ],
        p="md",
        radius="md",
        withBorder=True,
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

    for space_name in selected_spaces:
        updates = _load_changelog(space_name)
        for update in updates:
            cards.append(_create_update_log_item(update, space_name))

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