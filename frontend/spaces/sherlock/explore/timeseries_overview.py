from dash import html, register_page
from services.backend_service import get_table_as_df

register_page(__name__, path="/sherlock/data-exploration/timeseries-overview", title="Timeseries Overview Space")

def timeseries_overview_layout():
    data = get_table_as_df('order_overview')
    return html.Div(f"welcome to timeseries-overview home, latest data: {data}")

layout = timeseries_overview_layout