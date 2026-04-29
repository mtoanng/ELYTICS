from dash import html, register_page

register_page(__name__, path="/mycroft/data-exploration/soaking-overview", title="HOLMES - Mycroft - Soaking Overview")

def soaking_overview_layout():
    return html.Div(f"welcome to Soaking Overview page")

layout = soaking_overview_layout