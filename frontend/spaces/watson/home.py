from dash import html, register_page

register_page(__name__, path="/watson/home", title="Watson Space")

def watson_layout():
    return html.Div(f"welcome to watson home, latest data:")

layout = watson_layout