from dash import html, register_page

register_page(__name__, path="/enola/home", title="HOLMES - Enola")

def enola_layout():
    return html.Div("welcome to enola home")

layout = enola_layout