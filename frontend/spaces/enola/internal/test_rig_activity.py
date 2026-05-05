from dash import register_page
import dash_mantine_components as dmc

register_page(__name__, path="/enola/internal/test-rig-activity", title="HOLMES - Enola - Test Rig Activity")

def test_rig_activity_layout():    
    return dmc.Text("Placeholder content for Enola test rig activity")
    
layout = test_rig_activity_layout