from dash import html, register_page

register_page(__name__, path="/mycroft/home", title="Mycroft Space")

def mycroft_layout():
    return html.Div(f"welcome to mycroft home, latest data:")

layout = mycroft_layout