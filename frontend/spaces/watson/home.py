from dash_auth import protected
from dash import html, register_page
from services.backend_service import get_latest_data

register_page(__name__, path="/watson/home", title="Watson Space")

@protected(
    html.Div("Access denied", style={"color": "red", "padding": "2rem"}),
    groups=["IdM2BCD_holmes_pemely_user"]
)
def watson_layout():
    data = get_latest_data('groups')
    return html.Div(f"welcome to watson home, latest data: {data}")

layout = watson_layout