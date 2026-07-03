from dash import register_page

from spaces.elytics.reporting.dashboard import build_layout

register_page(
    __name__,
    path="/elytics/co-reporting",
    title="Elytics - CO2 Energy Stack Analytics",
)

layout = build_layout
