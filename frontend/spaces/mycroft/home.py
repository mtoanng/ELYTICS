from dash_auth import protected
from dash import html, register_page

register_page(__name__, path="/mycroft/home", title="Mycroft Space")

@protected(
    html.Div("Access denied", style={"color": "red", "padding": "2rem"}),
    groups=["IdM2BCD_holmes_pemely_user"]
)
def mycroft_layout():
    return html.Div(f"welcome to mycroft home, latest data:")

layout = mycroft_layout