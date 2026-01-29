from dash import html, register_page
from dash_auth import list_groups

register_page(__name__, path="/test-groups")

def layout():
    groups = list_groups()
    return html.Div([
        html.H3("Your groups:"),
        html.Pre(str(groups))
    ])

layout = layout