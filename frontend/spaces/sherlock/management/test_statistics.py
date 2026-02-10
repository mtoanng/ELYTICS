from dash_auth import protected
from dash import html, register_page

register_page(__name__, path="/sherlock/management/test-statistics", title="Test Statistics Space")

@protected(
    html.Div("Access denied", style={"color": "red", "padding": "2rem"}),
    groups=["IdM2BCD_holmes_pemely_user"]
)
def test_statistics_layout():
    return html.Div(f"welcome to test statistics home, latest data:")

layout = test_statistics_layout