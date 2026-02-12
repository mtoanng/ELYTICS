from dash import html, register_page
from services.backend_service import get_table_as_df

register_page(__name__, path="/sherlock/data-exploration/polarization-curves", title="Polarization Curves Space")

def polarization_curves_layout():
    data = get_table_as_df('order_overview')
    return html.Div(f"welcome to polarization-curves home, latest data: {data}")

layout = polarization_curves_layout