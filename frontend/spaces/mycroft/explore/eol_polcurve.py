from dash import html, register_page

register_page(__name__, path="/mycroft/data-exploration/eol-polcurve", title="HOLMES - Mycroft - EOL Polarization Curve")

def eol_polcurve_layout():
    return html.Div(f"welcome to EOL Polarization Curve page")

layout = eol_polcurve_layout