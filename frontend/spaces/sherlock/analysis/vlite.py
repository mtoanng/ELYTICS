from dash import html, register_page
from services.backend_service import get_table_as_df

register_page(__name__, path="/sherlock/data-analysis/vlite", title="HOLMES - Sherlock - V-Lite")

def vlite_layout():
    return html.Div(f"welcome to V-Lite home")

layout = vlite_layout