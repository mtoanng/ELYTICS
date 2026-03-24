from dash import html, register_page
from services.backend_service import get_table_as_df

register_page(__name__, path="/sherlock/management/track-record", title="HOLMES - Sherlock - Track Record")

def track_record_layout():
    return html.Div(f"welcome to Track Record home - disabled")

layout = track_record_layout