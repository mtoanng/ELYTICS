from dash import html, register_page

register_page(__name__, path="/sherlock/management/test-rig-statistics", title="HOLMES - Sherlock - Test Rig Statistics")

def test_statistics_layout():
    return html.Div(f"welcome to Test Rig Statistics home")

layout = test_statistics_layout