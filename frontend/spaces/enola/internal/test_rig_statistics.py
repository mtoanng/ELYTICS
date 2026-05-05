from dash import register_page
import dash_mantine_components as dmc

register_page(__name__, path="/enola/internal/test-rig-statistics", title="HOLMES - Enola - Test Rig Statistics")

def test_rig_statistics_layout():    
    return dmc.Text("Placeholder content for Enola test rig statistics")
    
layout = test_rig_statistics_layout