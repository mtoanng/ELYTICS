from dash_auth import protected
from dash import html, register_page

register_page(__name__, path="/enola/home", title="Enola Space")

@protected(
    html.Div("Access denied", style={"color": "red", "padding": "2rem"}),
    groups=["IdM2BCD_holmes_pemely_management"]
)
def enola_layout():
    return html.Div("welcome to enola home")

layout = enola_layout