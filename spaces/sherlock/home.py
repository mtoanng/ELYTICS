from dash_auth import protected
from dash import html, register_page

register_page(__name__, path="/sherlock/home", title="Sherlock Space")

@protected(
    html.Div("Access denied", style={"color": "red", "padding": "2rem"}),
    groups=["IdM2BCD_holmes_pemely_user"]
)
def sherlock_layout():
    return html.Div("welcome to sherlock home")

layout = sherlock_layout