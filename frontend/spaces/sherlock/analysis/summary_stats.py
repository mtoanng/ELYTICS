from dash_auth import protected
from dash import html, register_page
from services.backend_service import get_table_as_df

register_page(__name__, path="/sherlock/data-analysis/summary-stats", title="Summary Stats Space")

@protected(
    html.Div("Access denied", style={"color": "red", "padding": "2rem"}),
    groups=["IdM2BCD_holmes_pemely_user"]
)
def summary_stats_layout():
    data = get_table_as_df('order_overview')
    return html.Div(f"welcome to summary-stats home, latest data: {data}")

layout = summary_stats_layout