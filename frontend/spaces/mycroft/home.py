from dash_auth import protected
from dash import html, register_page
from services.backend_service import get_latest_data

register_page(__name__, path="/mycroft/home", title="Mycroft Space")

@protected(
    html.Div("Access denied", style={"color": "red", "padding": "2rem"}),
    groups=["IdM2BCD_holmes_pemely_user"]
)
def mycroft_layout():
    data = get_latest_data('tables/sample_overview')
    return html.Div(f"welcome to mycroft home, latest data: {data}")

layout = mycroft_layout