from dash import html, register_page

register_page(__name__, path="/sherlock/management/test-rig-activity", title="HOLMES - Sherlock - Test Rig Activity")

def test_rig_activity_layout():
    return html.Div(f"welcome to test rig activity home, latest data:")

layout = test_rig_activity_layout