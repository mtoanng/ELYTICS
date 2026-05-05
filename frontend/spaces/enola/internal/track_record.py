from dash import register_page
import dash_mantine_components as dmc

register_page(__name__, path="/enola/internal/track-record", title="HOLMES - Enola - Track Record")

def track_record_layout():    
    return dmc.Text("Placeholder content for Enola track record")
    
layout = track_record_layout