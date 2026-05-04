from dash import html, register_page

register_page(__name__, path="/mycroft/management/production-overview", title="HOLMES - Mycroft - Production Overview")

def production_overview_layout():
    return html.Div(f"welcome to Production Overview page")

layout = production_overview_layout