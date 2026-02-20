from dash import html, register_page
from services.backend_service import get_table_as_df

register_page(__name__, path="/sherlock/ai-ml/model-overview", title="HOLMES - Sherlock - Model Overview")

def model_overview_layout():
    data = get_table_as_df('order_overview')
    return html.Div(f"welcome to model-overview home, latest data: {data}")

layout = model_overview_layout