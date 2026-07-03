import json
from pathlib import Path

import dash_mantine_components as dmc

SIDEBAR_STRUCTURE = {
    "elytics": {
        "Analytics": {
            "path": "",
            "pages": [
                {"path": "co-reporting", "label": "Reporting"},
            ],
        },
    },
}


def get_visible_sidebar_structure() -> dict:
    return SIDEBAR_STRUCTURE


def get_space_from_path(pathname: str | None) -> str | None:
    if not pathname:
        return None
    parts = [p for p in pathname.split("/") if p]
    return parts[0] if parts else None


def _status_badge(page: dict):
    children = [
        dmc.Box(
            dmc.Text(page["label"], size="sm"),
            style={
                "display": "flex",
                "alignItems": "center",
                "lineHeight": 1,
                "minHeight": "100%",
            },
        )
    ]

    status_label = None
    status_color = None
    if page.get("disabled", False):
        status_label = "Disabled"
        status_color = "gray"
    elif page.get("preview", False):
        status_label = "Preview"
        status_color = "blue"

    if status_label and status_color:
        badge = dmc.Badge(
            status_label,
            size="xs",
            radius="xl",
            variant="filled",
            color=status_color,
            styles={
                "root": {
                    "display": "flex",
                    "alignItems": "center",
                    "justifyContent": "center",
                    "fontSize": "10px",
                    "padding": "2px 6px",
                    "fontWeight": 600,
                    "lineHeight": 1,
                    "textTransform": "none",
                    "cursor": "inherit",
                    "pointerEvents": "none",
                }
            },
        )
        if page.get("tooltip"):
            badge = dmc.Tooltip(
                multiline=True,
                w=260,
                label=page["tooltip"],
                position="right",
                withArrow=True,
                children=[badge],
            )
        children.append(
            dmc.Box(
                badge,
                style={
                    "marginLeft": "auto",
                    "display": "flex",
                    "alignItems": "center",
                    "justifyContent": "flex-end",
                    "flex": "0 0 auto",
                    "alignSelf": "center",
                    "minHeight": "100%",
                },
            )
        )

    return dmc.Box(
        children,
        style={
            "display": "flex",
            "alignItems": "center",
            "gap": "6px",
            "width": "100%",
            "height": "100%",
            "minWidth": 0,
        },
    )


def create_content(space: str, groups: dict, latest_version: str):
    body = []

    def _nav_link(
        page: dict, href: str, *, h: int, pl: int, description: str | None = None
    ):
        disabled = bool(page.get("disabled"))
        link = dmc.NavLink(
            label=_status_badge(page),
            description=description,
            href=None if disabled else href,
            active=False if disabled else "exact",
            className="navbar-link",
            h=h,
            pl=pl,
            style=(
                {
                    "opacity": 0.65,
                    "cursor": "default",
                }
                if disabled
                else None
            ),
        )
        return link

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
            body.append(_nav_link(page, f"/{space}/{page['path']}", h=32, pl=8))

    # Grouped pages
    for group, group_data in groups.items():
        if group is None or isinstance(group_data, list):
            continue

        # Group section header as a link
        group_path = group_data.get("path", group.lower().replace(" ", "-"))
        pages = group_data.get("pages", [])

        body.append(
            dmc.Divider(
                label=dmc.Text(group, size="sm", fw=700),
                labelPosition="left",
                mt=24,
                mb=8,
            )
        )

        for page in pages:
            href = f"/{space}/{page['path']}" if not group_path else f"/{space}/{group_path}/{page['path']}"
            body.append(_nav_link(page, href, h=32, pl=18))

    return dmc.Stack(
        gap=0,
        children=[
            dmc.ScrollArea(
                offsetScrollbars=False,
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
                href="https://apps-p-p3-outsystems.de.bosch.com/pemely/Main?inp_Screen=Feedback&inp_Id=0",
                target="_blank",
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
        changelog_path = (
            Path(__file__).resolve().parents[1] / "spaces" / space / "changelog.json"
        )
        latest_version = get_latest_version_from_changelog(changelog_path)

    if space and space in SIDEBAR_STRUCTURE:
        groups = SIDEBAR_STRUCTURE[space]
    else:
        groups = {}

    return create_content(space, groups, latest_version) if space else dmc.Text("")


layout = sidebar_layout
