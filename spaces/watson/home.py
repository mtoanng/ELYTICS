from dash_auth import protected
from dash import html, register_page

register_page(__name__, path="/watson/home", title="Watson Space")

@protected(
    html.Div("Access denied", style={"color": "red", "padding": "2rem"}),
    groups=["IdM2BCD_holmes_pemely_user"]
)
def watson_layout():
    return html.Div("welcome to watson home")

layout = watson_layout