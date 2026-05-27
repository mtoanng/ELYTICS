from dash import register_page

from spaces.shared.production_overview import create_production_overview_page

register_page(
    __name__,
    path="/mycroft/management/production-overview",
    title="HOLMES - Mycroft - Production Overview",
    name="HOLMES - Mycroft - Production Overview",
)

layout = create_production_overview_page(ns="myc-prod")
