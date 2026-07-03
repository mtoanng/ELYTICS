from dash import dcc, register_page

register_page(
    __name__,
    path="/",
    title="Elytics - CO2 Energy Stack Analytics",
)

layout = dcc.Location(href="/elytics/co-reporting", id="elytics-root-redirect")
