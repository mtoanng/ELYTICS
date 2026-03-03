from dash import html, register_page
from services.backend_service import get_table_as_df

register_page(__name__, path="/sherlock/data-analysis/charts", title="HOLMES - Sherlock - Charts")

def charts_layout():
    data = get_table_as_df('sherlock', 'order_overview')
    return html.Div(f"welcome to charts home, latest data: {data}")

layout = charts_layout