from dash import html, register_page

register_page(__name__, path="/mycroft/data-analysis/eol-trend-analysis", title="HOLMES - Mycroft - EOL Trend Analysis")

def eol_trend_analysis_layout():
    return html.Div(f"welcome to EOL Trend Analysis page")

layout = eol_trend_analysis_layout