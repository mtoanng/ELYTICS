import dash_mantine_components as dmc
from pathlib import Path
import json

SIDEBAR_STRUCTURE = {
    "mycroft": {
        None: [{"path": "home", "label": "Home"}],
    },
    "sherlock": {
        None: [{"path": "home", "label": "Home"}],
        "Management": {
            "path": "management",
            "pages": [
                {"path": "test-statistics", "label": "Test Statistics"},
                {"path": "test-rig-activity", "label": "Test Rig Activity"},
            ],
        },
        "Data Exploration": {
            "path": "data-exploration",
            "pages": [
                {"path": "order-overview", "label": "Order Overview"},
                {"path": "sample-overview", "label": "Sample Overview"},
                {"path": "ccm-overview", "label": "CCM Overview"},
                {"path": "polarization-curves", "label": "Polarization Curves"},
                {"path": "timeseries-overview", "label": "Timeseries Overview"},
            ],
        },
        "Data Analysis": {
            "path": "data-analysis",
            "pages": [
                {"path": "summary-stats", "label": "Summary Stats"},
                {"path": "charts", "label": "Charts"},
            ],
        },
        "AI/ML": {
            "path": "ai-ml",
            "pages": [
                {"path": "model-overview", "label": "Model Overview"},
                {"path": "predictions", "label": "Predictions"},
            ],
        },
    },
    "enola": {
        None: [{"path": "home", "label": "Home"}],
    },
    "watson": {
        None: [{"path": "home", "label": "Home"}],
    },
}

def get_space_from_path(pathname: str | None) -> str | None:
    if not pathname:
        return None
    parts = [p for p in pathname.split("/") if p]
    return parts[0] if parts else None

def create_content(space: str, groups: dict, latest_version: str):
    body = []

    # Version + Home as main NavLink
    if None in groups:
        home_page = groups[None][0]  # Assume first item is Home
        body.append(
            dmc.NavLink(
                label=home_page["label"],
                description=f"Version {latest_version}",
                href=f"/{space}/{home_page['path']}",
                active="exact",
                className="navbar-link",
                h=50,
                pl=8,
            )
        )
        
        # Add remaining ungrouped pages (if any)
        for page in groups[None][1:]:
            body.append(
                dmc.NavLink(
                    label=page["label"],
                    href=f"/{space}/{page['path']}",
                    active="exact",
                    className="navbar-link",
                    h=32,
                    pl=8,
                )
            )

    # Grouped pages
    for group, group_data in groups.items():
        if group is None or isinstance(group_data, list):
            continue

        # Group section header as a link
        group_path = group_data.get("path", group.lower().replace(" ", "-"))
        pages = group_data.get("pages", [])

        body.append(
            dmc.Divider(
                label=dmc.Anchor(
                    dmc.Text(group, size="sm", fw=700),
                    href=f"/{space}/{group_path}",
                    underline=False,
                ),
                labelPosition="left",
                mt=24,
                mb=8,
            )
        )

        for page in pages:
            body.append(
                dmc.NavLink(
                    label=page["label"],
                    href=f"/{space}/{group_path}/{page['path']}",
                    active="exact",
                    className="navbar-link",
                    h=32,
                    pl=18,
                )
            )

    return dmc.Stack(
        gap=0,
        children=[
            dmc.ScrollArea(
                offsetScrollbars=True,
                type="scroll",
                style={"height": "100%", "flex": 1},
                children=dmc.Stack(
                    gap=0,
                    children=[*body, dmc.Space(h=90)],
                    pl="xs",
                    pr="xs",
                    pt="sm",
                ),
            ),
            dmc.Divider(m=0),
            dmc.NavLink(
                label="Submit Feedback",
                href="#",
                active=False,
                className="navbar-link",
                h=50,
                pl=8,
                style={"borderRadius": 0, "textAlign": "center"},
            ),
        ],
        style={"height": "100%"},
    )

def get_latest_version_from_changelog(changelog_path: Path) -> str:
    """Read the latest released version from a JSON changelog file."""
    try:
        if changelog_path.exists():
            with changelog_path.open(encoding="utf-8") as f:
                changelog = json.load(f)
            releases = changelog.get("releases", {})
            if releases:
                # Get the first key (latest version)
                return next(iter(releases.keys()))
    except (json.JSONDecodeError, OSError):
        pass
    return "0.0.0"

def sidebar_layout(pathname: str | None = None):
    space = get_space_from_path(pathname)
    
    # Get the changelog path for the space
    latest_version = "0.0.0"
    if space:
        changelog_path = Path(__file__).resolve().parents[1] / "spaces" / space / "changelog.json"
        latest_version = get_latest_version_from_changelog(changelog_path)

    if space and space in SIDEBAR_STRUCTURE:
        groups = SIDEBAR_STRUCTURE[space]
    else:
        groups = {}

    return create_content(space, groups, latest_version) if space else dmc.Text("")

layout = sidebar_layout