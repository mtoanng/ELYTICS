import dash_mantine_components as dmc
from dash import register_page, Output, Input, clientside_callback, html, callback
from dash_iconify import DashIconify
from components.changelog import build_update_cards, load_changelog_json
from config.access_config import SPACE_ACCESS_MAP
from dash_auth import list_groups
from pathlib import Path

register_page(__name__, path="/", title="HOLMES - Home")

# Space information with descriptions and versions
SPACE_INFO = {
    "sherlock": {
        "title": "Sherlock",
        "subtitle": "asTested",
        "description": "Single platform for all internal and external testing data.",
        "version": None,
        "color": "blue",
        "icon": "tabler:flask",
    },
}

ROOT_CHANGELOG_LABEL = "HOLMES"
ROOT_CHANGELOG_COLOR = "blue"


def _extract_latest_version(changelog: dict) -> str:
    releases = changelog.get("releases") or {}
    candidates: list[tuple[str, str | None]] = []

    if isinstance(releases, dict):
        for version, payload in releases.items():
            date = None
            if isinstance(payload, dict):
                date = (
                    payload.get("date")
                    or payload.get("released")
                    or payload.get("released_at")
                )
            candidates.append((version, date))
    elif isinstance(releases, list):
        for payload in releases:
            if not isinstance(payload, dict):
                continue
            version = payload.get("version") or payload.get("tag")
            if not version:
                continue
            date = payload.get("date") or payload.get("released")
            candidates.append((version, date))

    if not candidates:
        return "N/A"

    dated = [item for item in candidates if item[1]]
    if dated:
        return max(dated, key=lambda item: item[1] or "")[0]

    return max((version for version, _ in candidates), default="N/A")


def _create_space_card(space_name, space_data, version, has_access=False):
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
                            version,
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
                    dmc.Group(
                        [
                            dmc.Title(
                                space_data["title"],
                                order=3,
                            ),
                            dmc.Text(
                                space_data.get("subtitle", ""),
                                size="xs",
                                c="dimmed",
                                style={"fontStyle": "italic"},
                            ),
                        ],
                        gap="xs",
                        align="baseline",
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
                                style={"fontSize": "11px", "background": "rgba(128,128,128,0.14)"},
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
    base_path = Path(__file__).resolve().parents[1]

    space_versions = {}
    for space_name in SPACE_INFO.keys():
        space_path = base_path / "spaces" / space_name / "changelog.json"
        space_changelog = load_changelog_json(space_path)
        space_versions[space_name] = _extract_latest_version(space_changelog)

    # Get current user's groups
    user_groups = list_groups()

    # Determine which spaces the user has access to
    user_access = {}
    for space_name in SPACE_INFO.keys():
        required_groups = SPACE_ACCESS_MAP.get(f"/{space_name}", [])
        has_access = user_groups and any(
            group in user_groups for group in required_groups
        )
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
                                dmc.Stack(
                                    [
                                        dmc.Text(
                                            "“It is a capital mistake to theorize before one has data.  "
                                            "Insensibly one begins to twist facts to suit theories, instead of theories to suit facts.”",
                                            ta="center",
                                            style={"fontStyle": "italic"},
                                        ),
                                        dmc.Text(
                                            "- Arthur Conan Doyle, from “The Complete Sherlock Holmes, Vol 2”",
                                            ta="center",
                                            c="dimmed",
                                            size="sm",
                                        ),
                                    ],
                                    gap=2,
                                ),
                                dmc.Text(
                                    "The Holmes application Suite is your central hub for navigating, visualizing, and understanding all ELY related stack data at Bosch. Effortlessly browse and search through complex datasets, generate insightful summaries, and uncover trends with advanced analytics and AI-powered tools.",
                                    size="md",
                                    ta="center",
                                ),
                                dmc.Divider(
                                    label="Application spaces",
                                    labelPosition="center",
                                    my="xs",
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
                            _create_space_card(
                                space_name,
                                space_data,
                                space_versions.get(space_name) or "N/A",
                                user_access.get(space_name, False),
                            )
                            for space_name, space_data in SPACE_INFO.items()
                        ],
                    ),
                    dmc.Stack(
                        [
                            dmc.Divider(
                                label="Additional sources & documentation",
                                labelPosition="center",
                                my="sm",
                            ),
                            dmc.Group(
                                [
                                    dmc.Stack(
                                        [
                                            html.A(
                                                [
                                                    dmc.Image(
                                                        id="docupedia-logo-img",
                                                        src="/assets/docupedia_logo.png",
                                                        w=120,
                                                        h="auto",
                                                        lightHidden=False,
                                                        darkHidden=True,
                                                    ),
                                                    dmc.Image(
                                                        id="docupedia-logo-img-dark",
                                                        src="/assets/docupedia_logo.png",
                                                        w=120,
                                                        h="auto",
                                                        style={
                                                            "filter": "invert(1) hue-rotate(180deg)"
                                                        },
                                                        lightHidden=True,
                                                        darkHidden=False,
                                                    ),
                                                ],
                                                href="https://inside-docupedia.bosch.com/confluence/spaces/ELYSTACK/pages/2693376926/ELY+Data",
                                                target="_blank",
                                                style={
                                                    "display": "flex",
                                                    "justifyContent": "center",
                                                    "alignItems": "center",
                                                },
                                            ),
                                            dmc.Text(
                                                "ELY Data documentation and resources",
                                                size="sm",
                                                ta="center",
                                            ),
                                        ],
                                        gap="xs",
                                        align="center",
                                        style={"width": "250px", "maxWidth": "250px"},
                                    ),
                                    dmc.Divider(orientation="vertical", size="sm", h=64),
                                    dmc.Stack(
                                        [
                                            html.A(
                                                [
                                                    dmc.Image(
                                                        id="leepa-logo-img",
                                                        src="/assets/leepa_logo.png",
                                                        w=120,
                                                        h="auto",
                                                        lightHidden=False,
                                                        darkHidden=True,
                                                    ),
                                                    dmc.Image(
                                                        id="leepa-logo-img-dark",
                                                        src="/assets/leepa_logo.png",
                                                        w=120,
                                                        h="auto",
                                                        style={
                                                            "filter": "invert(1) hue-rotate(180deg)"
                                                        },
                                                        lightHidden=True,
                                                        darkHidden=False,
                                                    ),
                                                ],
                                                href="https://leepa.app.bosch.com/en/bapmfe/",
                                                target="_blank",
                                                style={
                                                    "display": "flex",
                                                    "justifyContent": "center",
                                                    "alignItems": "center",
                                                },
                                            ),
                                            dmc.Text("Test & Order Management", size="sm", ta="center"),
                                        ],
                                        gap="xs",
                                        align="center",
                                        style={"width": "250px", "maxWidth": "250px"},
                                    ),
                                    dmc.Divider(orientation="vertical", size="sm", h=64),
                                    dmc.Stack(
                                        [
                                            html.A(
                                                [
                                                    dmc.Image(
                                                        id="outsystems-logo-img",
                                                        src="/assets/outsystems_logo.png",
                                                        w=120,
                                                        h="auto",
                                                        lightHidden=False,
                                                        darkHidden=True,
                                                    ),
                                                    dmc.Image(
                                                        id="outsystems-logo-img-dark",
                                                        src="/assets/outsystems_logo_dark.png",
                                                        w=120,
                                                        h="auto",
                                                        style={
                                                            "filter": "invert(1) hue-rotate(180deg)"
                                                        },
                                                        lightHidden=True,
                                                        darkHidden=False,
                                                    ),
                                                ],
                                                href="https://apps-p-p3-outsystems.de.bosch.com/pemely/Main?inp_Id=0&inp_Screen=MainPage",
                                                target="_blank",
                                                style={
                                                    "display": "flex",
                                                    "justifyContent": "center",
                                                    "alignItems": "center",
                                                },
                                            ),
                                            dmc.Text("Sample & Stack Browser", size="sm", ta="center"),
                                        ],
                                        gap="xs",
                                        align="center",
                                        style={"width": "250px", "maxWidth": "250px"},
                                    ),
                                ],
                                gap="xl",
                                justify="center",
                                align="center",
                                wrap="wrap",
                            ),
                            dmc.Divider(
                                label="Application Updates",
                                labelPosition="center",
                                my="sm",
                            ),
                            dmc.MultiSelect(
                                id="changelog-space-filter",
                                data=[
                                    {
                                        "value": space_name,
                                        "label": SPACE_INFO[space_name]["title"],
                                    }
                                    for space_name in SPACE_INFO.keys()
                                ],
                                value=list(SPACE_INFO.keys()),
                                label="Filter by space",
                                placeholder="Select spaces",
                                searchable=True,
                                clearable=False,
                                w="100%",
                            ),
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
                        gap="sm",
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
    prevent_initial_call=False,
)
def update_changelog_list(selected_spaces):
    selected_spaces = selected_spaces or []
    cards = []

    base_path = Path(__file__).resolve().parents[1]
    root_changelog = load_changelog_json(base_path / "changelog.json")
    cards.extend(
        build_update_cards(root_changelog, ROOT_CHANGELOG_LABEL, ROOT_CHANGELOG_COLOR)
    )

    for space_name in selected_spaces:
        space_path = base_path / "spaces" / space_name / "changelog.json"
        space_changelog = load_changelog_json(space_path)
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
    function(n1) {
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
    prevent_initial_call=True,
)
