import dash_mantine_components as dmc
from dash import dcc, page_container, callback, clientside_callback, Output, Input

from components import header, sidebar
from services.auth import check_access
from components.access_warning import create_access_warning
from config.access_config import SPACE_ACCESS_MAP


def create_appshell():
    return dmc.MantineProvider(
        theme={
            "primaryColor": "blue",
            "fontFamily": "'Segoe UI', Arial, sans-serif",
            "breakpoints": {
                "sm": "43em",
                "lg": "67.5em",
                "xl": "78em",
                "xxl": "100em",
            },
        },
        children=dmc.Box(
            [
                dcc.Location(id="url", refresh=False),
                dcc.Store(id="theme-store", data="light"),
                dcc.Store(id="user-access-store", data={"has_access": True}),
                dcc.Store(id="current-space-store", data=None),
                dmc.Box(
                    id="appshell-container",
                ),
            ],
            className="appshell-container",
        ),
    )


@callback(
    Output("appshell-container", "children"),
    Input("url", "pathname"),
    prevent_initial_call=False
)
def update_appshell_content(pathname):
    # If at root path, show landing page without sidebar and no navbar config
    if pathname == "/" or pathname == "":
        return dmc.AppShell(
            [
                dmc.AppShellHeader(header.layout(), h=70),
                dmc.AppShellMain(
                    children=page_container,
                    id="page-content",
                ),
            ],
            header={"height": 70},
            padding="lg",
        )
    
    # Extract space from pathname (e.g., "/sherlock/..." -> "sherlock")
    path_parts = pathname.split("/")
    space = path_parts[1] if len(path_parts) > 1 else None
    required_groups = SPACE_ACCESS_MAP.get(f"/{space}")

    # Check access
    has_access, user, needs_login = check_access(groups=required_groups) if required_groups else (True, None, False)
    
    # If needs login, Dash auth will handle the redirect automatically
    # Just return empty content for now
    if needs_login:
        return dmc.AppShell(
            [
                dmc.AppShellHeader(header.layout(), h=70),
                dmc.AppShellMain(
                    children=dmc.Center(
                        dmc.Loader(size="lg"),
                        style={"minHeight": "calc(100vh - 70px)"}
                    ),
                    id="page-content",
                    p=0,
                    pt="lg",
                ),
            ],
            header={"height": 70},
            padding="lg",
        )
    
    # If no access, show access warning without sidebar
    if not has_access:
        access_content = create_access_warning(space)
        return dmc.AppShell(
            [
                dmc.AppShellHeader(header.layout(), h=70),
                dmc.AppShellMain(
                    children=dmc.Center(
                        access_content,
                        style={"minHeight": "calc(100vh - 70px)"}
                    ),
                    id="page-content",
                    p=0,
                    pt="lg",
                ),
            ],
            header={"height": 70},
            padding="lg",
        )
    
    # Has access, show full layout with sidebar
    return dmc.AppShell(
        [
            dmc.AppShellHeader(header.layout(), h=70),
            dmc.AppShellNavbar(
                sidebar.sidebar_layout(pathname),
                id="sidebar-container",
                w=300,
                display="block",
            ),
            dmc.AppShellMain(
                children=page_container,
                id="page-content",
            ),
        ],
        header={"height": 70},
        navbar={
            "width": 300,
            "breakpoint": "lg",
            "collapsed": {"mobile": True},
        },
        padding="lg",
    )