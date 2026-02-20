from dash import html, register_page
from services.backend_service import get_table_as_df

register_page(__name__, path="/sherlock/data-analysis/summary-stats", title="HOLMES - Sherlock - Summary Stats")

def summary_stats_layout():
    data = get_table_as_df('order_overview')
    return html.Div(f"welcome to summary-stats home, latest data: {data}")

layout = summary_stats_layout