import dash_mantine_components as dmc
from dash import dcc, page_container, callback, Output, Input, State
from dash_iconify import DashIconify

from components import header, sidebar
from services.auth import check_access
from components.access_warning import create_access_warning
from config.access_config import SPACE_ACCESS_MAP


HEADER_HEIGHT = 70
NAVBAR_WIDTH = 300


def _toggle_style(chrome_hidden: bool, visible: bool = True) -> dict[str, str | int]:
    style = {
        "position": "fixed",
        "zIndex": 250,
        "top": "calc(var(--app-shell-header-offset, 0rem) + 2px)",
        "left": "calc(var(--app-shell-navbar-offset, 0rem) + 2px)",
    }
    if not visible:
        style["display"] = "none"
        return style
    return style


def _chrome_toggle_button(chrome_hidden: bool, visible: bool = True):
    icon = (
        "material-symbols:more-up-rounded"
        if chrome_hidden
        else "material-symbols:more-down-rounded"
    )
    label = "Show header and sidebar" if chrome_hidden else "Hide header and sidebar"
    style = _toggle_style(chrome_hidden, visible)

    return dmc.Box(
        dmc.Tooltip(
            id="appshell-chrome-tooltip",
            label=label,
            position="right",
            withArrow=True,
            children=dmc.ActionIcon(
                DashIconify(id="appshell-chrome-toggle-icon", icon=icon, width=18, rotate=1),
                id="appshell-chrome-toggle",
                variant="default",
                radius="xs",
                size="xs",
                style={"boxShadow": "var(--mantine-shadow-sm)"},
                attributes={"aria-label": label, "title": label},
            ),
        ),
        id="appshell-chrome-toggle-wrapper",
        style=style,
    )


def _page_content(children, chrome_hidden: bool, show_toggle: bool = True, constrained: bool = False):
    content_style = {"maxWidth": "1200px", "margin": "0 auto"} if constrained else None
    return dmc.Box(
        [
            _chrome_toggle_button(chrome_hidden, visible=show_toggle),
            dmc.Box(
                children,
                className="appshell-page-content",
                style=content_style,
            ),
        ],
        style={"position": "relative"},
    )


def _is_home_path(pathname: str) -> bool:
    return pathname in ("/", "") or pathname.endswith("/home")





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
                dcc.Store(id="appshell-chrome-hidden", data=False),
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
    hidden = bool(chrome_hidden) if chrome_hidden is not None else False
    is_home = _is_home_path(pathname)
    show_toggle = not is_home
    shell_class = "appshell-root chrome-hidden" if hidden else "appshell-root"

    # If at root path, show landing page without sidebar and no navbar config
    if pathname == "/" or pathname == "":
        return dmc.AppShell(
            id="main-appshell",
            className=shell_class,
            children=[
                dmc.AppShellHeader(header.layout(), h=HEADER_HEIGHT),
                dmc.AppShellMain(
                    children=_page_content(
                        page_container,
                        hidden,
                        show_toggle=False,
                        constrained=True,
                    ),
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
                        hidden,
                        show_toggle=show_toggle,
                        constrained=is_home,
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
                        hidden,
                        show_toggle=show_toggle,
                        constrained=is_home,
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
                children=_page_content(
                    page_container,
                    hidden,
                    show_toggle=show_toggle,
                    constrained=is_home,
                ),
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
def toggle_appshell_chrome(n_clicks, chrome_hidden):
    if not n_clicks:
        return chrome_hidden
    return not bool(chrome_hidden)


@callback(
    Output("main-appshell", "className"),
    Output("appshell-chrome-toggle-wrapper", "style"),
    Output("appshell-chrome-toggle-icon", "icon"),
    Output("appshell-chrome-toggle", "attributes"),
    Output("appshell-chrome-tooltip", "label"),
    Input("appshell-chrome-hidden", "data"),
    Input("url", "pathname"),
    prevent_initial_call=True,
)
def sync_chrome_visibility(chrome_hidden, pathname):
    show_toggle = not _is_home_path(pathname)
    hidden = bool(chrome_hidden) if chrome_hidden is not None else False
    shell_class = "appshell-root chrome-hidden" if hidden else "appshell-root"
    icon = (
        "material-symbols:more-up-rounded"
        if hidden
        else "material-symbols:more-down-rounded"
    )
    label = "Show header and sidebar" if hidden else "Hide header and sidebar"
    attributes = {"aria-label": label, "title": label}
    return shell_class, _toggle_style(hidden, visible=show_toggle), icon, attributes, label

