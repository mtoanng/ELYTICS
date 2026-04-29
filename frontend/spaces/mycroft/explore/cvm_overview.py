from dash import html, register_page

register_page(__name__, path="/mycroft/data-exploration/cvm-overview", title="HOLMES - Mycroft - CVM Overview")

def cvm_overview_layout():
    return html.Div(f"welcome to CVM Overview page")

layout = cvm_overview_layout