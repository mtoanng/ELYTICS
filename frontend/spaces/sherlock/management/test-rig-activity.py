from dash_auth import protected
from dash import html, register_page
from services.backend_service import get_latest_data

register_page(__name__, path="/sherlock/management/test-rig-activity", title="Test Rig Activity Space")

@protected(
    html.Div("Access denied", style={"color": "red", "padding": "2rem"}),
    groups=["IdM2BCD_holmes_pemely_user"]
)
def test_rig_activity_layout():
    data = get_latest_data('tables/order_overview')
    return html.Div(f"welcome to test rig activity home, latest data: {data}")

layout = test_rig_activity_layout