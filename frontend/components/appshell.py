import dash_mantine_components as dmc
from dash import dcc, page_container, callback, clientside_callback, Output, Input

from components import header, sidebar
from services.auth import check_access
from components.access_warning import create_access_warning
from config.access_config import PAGE_ACCESS_MAP


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
                dmc.AppShell(
                    [
                        dmc.AppShellHeader(header.layout(), h=70),
                        dmc.AppShellNavbar(
                            sidebar.sidebar_layout(None),
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
    # Extract space from pathname (e.g., "/sherlock/..." -> "sherlock")
    path_parts = pathname.split("/")
    space = path_parts[1] if len(path_parts) > 1 else None
    required_groups = PAGE_ACCESS_MAP.get(f"/{space}")

    # Check access
    has_access, _ = check_access(groups=required_groups) if required_groups else (True, None)
    
    # If no access, show access warning without sidebar
    if not has_access:
        access_content = create_access_warning(space)
        return [
            dmc.AppShellHeader(header.layout(), h=70),
            dmc.AppShellMain(
                children=dmc.Center(
                    access_content,
                    style={"minHeight": "calc(100vh - 70px)"}
                ),
                id="page-content",
                p=0,
                pt="lg"
            ),
        ]
    
    # Has access, show full layout with sidebar
    return [
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
    ]

# Combined theme detection and switch handling
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
    prevent_initial_call=False
)