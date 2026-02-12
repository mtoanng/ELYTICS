from dash import html, register_page
from services.backend_service import get_table_as_df

register_page(__name__, path="/sherlock/data-exploration/sample-overview", title="Sample Overview Space")

def sample_overview_layout():
    data = get_table_as_df('order_overview')
    return html.Div(f"welcome to sample-overview home, latest data: {data}")

layout = sample_overview_layout