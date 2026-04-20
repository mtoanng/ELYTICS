import dash_mantine_components as dmc
from dash import dcc, page_container, callback, Output, Input, State
from dash_iconify import DashIconify

from components import header, sidebar
from services.auth import check_access
from components.access_warning import create_access_warning
from config.access_config import SPACE_ACCESS_MAP


HEADER_HEIGHT = 70
NAVBAR_WIDTH = 300


def _toggle_style(chrome_hidden: bool) -> dict[str, str | int]:
    style = {
        "position": "fixed",
        "zIndex": 250,
        "boxShadow": "0 4px 12px rgba(0, 0, 0, 0.16)",
    }
    if chrome_hidden:
        style.update({"top": "8px", "left": "8px"})
    else:
        style.update(
            {
                "top": f"{HEADER_HEIGHT}px",
                "left": f"{NAVBAR_WIDTH}px",
                "transform": "translate(-50%, -50%)",
            }
        )
    return style


def _chrome_toggle_button(chrome_hidden: bool):
    icon = (
        "material-symbols:fullscreen"
        if chrome_hidden
        else "material-symbols:fullscreen-exit"
    )
    label = "Show header and sidebar" if chrome_hidden else "Hide header and sidebar"
    style = _toggle_style(chrome_hidden)

    return dmc.Tooltip(
        id="appshell-chrome-tooltip",
        label=label,
        position="right",
        withArrow=True,
        children=dmc.ActionIcon(
            DashIconify(id="appshell-chrome-toggle-icon", icon=icon, width=18),
            id="appshell-chrome-toggle",
            variant="filled",
            radius="xl",
            size="md",
            color="gray",
            style=style,
            attributes={"aria-label": label, "title": label},
        ),
    )


def _page_content(children, chrome_hidden: bool):
    return [
        _chrome_toggle_button(chrome_hidden),
        dmc.Box(children, className="appshell-page-content"),
    ]


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
                dcc.Store(id="appshell-chrome-hidden", data=True),
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
    State("appshell-chrome-hidden", "data"),
    prevent_initial_call=False,
)
def update_appshell_content(pathname, chrome_hidden):
    shell_class = "appshell-root chrome-hidden" if chrome_hidden else "appshell-root"

    # If at root path, show landing page without sidebar and no navbar config
    if pathname == "/" or pathname == "":
        return dmc.AppShell(
            id="main-appshell",
            className=shell_class,
            children=[
                dmc.AppShellHeader(header.layout(), h=HEADER_HEIGHT),
                dmc.AppShellMain(
                    children=_page_content(page_container, bool(chrome_hidden)),
                    id="page-content",
                ),
            ],
            header={"height": HEADER_HEIGHT},
            padding=0,
        )

    # Extract space from pathname (e.g., "/sherlock/..." -> "sherlock")
    path_parts = pathname.split("/")
    space = path_parts[1] if len(path_parts) > 1 else None
    required_groups = SPACE_ACCESS_MAP.get(f"/{space}")

    # Check access
    has_access, user, needs_login = (
        check_access(groups=required_groups) if required_groups else (True, None, False)
    )

    # If needs login, Dash auth will handle the redirect automatically
    # Just return empty content for now
    if needs_login:
        return dmc.AppShell(
            id="main-appshell",
            className=shell_class,
            children=[
                dmc.AppShellHeader(header.layout(), h=HEADER_HEIGHT),
                dmc.AppShellMain(
                    children=_page_content(
                        dmc.Center(
                            dmc.Loader(size="lg"),
                            style={"minHeight": f"calc(100vh - {HEADER_HEIGHT}px)"},
                        ),
                        bool(chrome_hidden),
                    ),
                    id="page-content",
                    p=0,
                    pt="lg",
                ),
            ],
            header={"height": HEADER_HEIGHT},
            padding=0,
        )

    # If no access, show access warning without sidebar
    if not has_access and space is not None:
        access_content = create_access_warning(space)
        return dmc.AppShell(
            id="main-appshell",
            className=shell_class,
            children=[
                dmc.AppShellHeader(header.layout(), h=HEADER_HEIGHT),
                dmc.AppShellMain(
                    children=_page_content(
                        dmc.Center(
                            access_content,
                            style={"minHeight": f"calc(100vh - {HEADER_HEIGHT}px)"},
                        ),
                        bool(chrome_hidden),
                    ),
                    id="page-content",
                    p=0,
                    pt="lg",
                ),
            ],
            header={"height": HEADER_HEIGHT},
            padding=0,
        )

    return dmc.AppShell(
        id="main-appshell",
        className=shell_class,
        children=[
            dmc.AppShellHeader(header.layout(), h=HEADER_HEIGHT),
            dmc.AppShellNavbar(
                sidebar.sidebar_layout(pathname),
                id="sidebar-container",
                w=NAVBAR_WIDTH,
            ),
            dmc.AppShellMain(
                children=_page_content(page_container, bool(chrome_hidden)),
                id="page-content",
            ),
        ],
        header={"height": HEADER_HEIGHT},
        navbar={
            "width": NAVBAR_WIDTH,
            "breakpoint": "lg",
            "collapsed": {"mobile": True},
        },
        padding=0,
    )


@callback(
    Output("appshell-chrome-hidden", "data"),
    Input("appshell-chrome-toggle", "n_clicks"),
    State("appshell-chrome-hidden", "data"),
    prevent_initial_call=True,
)
def toggle_appshell_chrome(_, chrome_hidden):
    return not bool(chrome_hidden)


@callback(
    Output("main-appshell", "className"),
    Output("appshell-chrome-toggle", "style"),
    Output("appshell-chrome-toggle-icon", "icon"),
    Output("appshell-chrome-toggle", "attributes"),
    Output("appshell-chrome-tooltip", "label"),
    Input("appshell-chrome-hidden", "data"),
    prevent_initial_call=True,
)
def sync_chrome_visibility(chrome_hidden):
    hidden = bool(chrome_hidden)
    shell_class = "appshell-root chrome-hidden" if hidden else "appshell-root"
    icon = "material-symbols:fullscreen" if hidden else "material-symbols:fullscreen-exit"
    label = "Show header and sidebar" if hidden else "Hide header and sidebar"
    attributes = {"aria-label": label, "title": label}
    return shell_class, _toggle_style(hidden), icon, attributes, label
