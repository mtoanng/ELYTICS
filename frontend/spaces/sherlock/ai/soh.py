from dash import html, register_page
from services.backend_service import get_table_as_df

register_page(__name__, path="/sherlock/ai-ml/soh", title="HOLMES - Sherlock - State of Health")

def soh_layout():
    return html.Div(f"welcome to State of Health analysis page")

layout = soh_layout