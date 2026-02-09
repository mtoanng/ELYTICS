import dash_mantine_components as dmc
from dash import dcc, page_container, callback, clientside_callback, Output, Input

from components import header, sidebar


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
                dmc.AppShell(
                    [
                        dmc.AppShellHeader(header.layout(), h=70),
                        dmc.AppShellNavbar(
                            sidebar.sidebar_layout(None),
                            id="sidebar-container",
                            w=300,
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
                ),
            ],
            className="appshell-container",
        ),
    )


@callback(
    Output("sidebar-container", "children"),
    Input("url", "pathname"),
    prevent_initial_call=False
)
def update_sidebar(pathname):
    return sidebar.sidebar_layout(pathname)


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