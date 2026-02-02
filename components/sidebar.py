import os
from dash import html
import dash_bootstrap_components as dbc
from services.changelog_service import get_latest_released_version

SPACES_DIR = os.path.join(os.path.dirname(__file__), "..", "spaces")

def get_sidebar_structure():
    """
    Returns a dict of the form:
    {
        "mycroft": {
            "ai": ["polarization", "predictions", "rate"],
            "general": ["timeseries"],
            None: ["home"]
        },
        ...
    }
    """
    sidebar = {}
    for section in os.listdir(SPACES_DIR):
        section_path = os.path.join(SPACES_DIR, section)
        if not os.path.isdir(section_path):
            continue
        groups = {}
        for root, _, files in os.walk(section_path):
            rel_path = os.path.relpath(root, section_path)
            for file in files:
                if file.endswith(".py") and not file.startswith("__"):
                    page_name = file[:-3]
                    if rel_path == ".":
                        group = None
                    else:
                        group = rel_path.replace("\\", "/")  # For Windows paths
                    groups.setdefault(group, []).append(page_name)
        sidebar[section] = groups
    return sidebar

def make_nav_links(section, group, pages):
    links = []
    for page in sorted(pages):
        # Build the href
        if group:
            href = f"/{section}/{group}/{page}"
        else:
            href = f"/{section}/{page}"
        # Capitalize nicely
        label = page.replace("_", " ").title()
        links.append(dbc.NavLink(label, href=href, active="exact", className="ps-4" if group else ""))
    return links

def sidebar_layout():
    latest_version = get_latest_released_version() or "Unknown"
    sidebar_structure = get_sidebar_structure()

    nav_sections = []
    for section, groups in sidebar_structure.items():
        nav_sections.append(html.Hr())
        nav_sections.append(html.H5(section.title(), className="ps-2", style={"marginTop": "1rem"}))
        # Top-level pages (not in a group)
        if None in groups:
            nav_sections.extend(make_nav_links(section, None, groups[None]))
        # Grouped pages
        for group, pages in groups.items():
            if group is None:
                continue
            group_id = f"{section}-{group}-group"
            nav_sections.append(
                dbc.Button(
                    [html.I(className="bi bi-chevron-right me-2", id=f"{group_id}-icon"), group.title()],
                    id=f"{group_id}-toggle",
                    className="sidebar-group-btn",
                    color="link",
                    style={"textAlign": "left", "width": "100%"},
                )
            )
            nav_sections.append(
                dbc.Collapse(
                    dbc.Nav(
                        make_nav_links(section, group, pages),
                        vertical=True,
                        pills=True,
                    ),
                    id=f"{group_id}-collapse",
                    is_open=False,
                )
            )

    return html.Div(
        [
            html.Div(
                [
                    dbc.NavLink([
                        html.Span(f"Version {latest_version}", style={"fontSize": "0.85em", "fontWeight": "normal"})
                    ], href="/version_history", active="exact", className="ps-2", style={"marginBottom": "0.25rem", "marginTop": "0.5rem", "textAlign": "left"}),
                    html.Hr(),
                    *nav_sections,
                ],
                id="sidebar",
                className="sidebar",
            ),
            dbc.Button(
                id="sidebar-toggle",
                color="secondary",
                className="sidebar-toggle-btn",
                n_clicks=0,
                outline=True,
                size="sm",
                style={"marginTop": 0},
                children=html.I(className="bi bi-arrow-left-short", id="sidebar-toggle-icon")
            ),
        ],
        className="sidebar-container"
    )

layout = sidebar_layout