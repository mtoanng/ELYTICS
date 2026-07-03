from dash import register_page

from ..co_energystacck_migration.reporting_dashboard import build_layout

register_page(
    __name__,
    path="/sherlock/data-exploration/co-reporting",
    title="Elytics - CO2 Energy Stack Analytics",
)

layout = build_layout
