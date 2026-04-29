from dash import html, register_page

register_page(__name__, path="/mycroft/data-exploration/stack-overview", title="HOLMES - Mycroft - Stack Overview")

def stack_overview_layout():
    return html.Div(f"welcome to Stack Overview page")

layout = stack_overview_layout