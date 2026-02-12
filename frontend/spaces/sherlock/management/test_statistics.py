from dash import html, register_page

register_page(__name__, path="/sherlock/management/test-statistics", title="Test Statistics Space")

def test_statistics_layout():
    return html.Div(f"welcome to test statistics home, latest data:")

layout = test_statistics_layout