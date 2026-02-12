from dash import html, register_page
    
register_page(__name__, path="/", title="Holmes Suite")

def home_layout():
    return html.Div("welcome to the holmes suite (show how to use spaces)")

layout = home_layout  # Dash expects a 'layout' variable or function