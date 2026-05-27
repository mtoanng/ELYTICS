from dash import register_page

from spaces.shared.production_overview import create_production_overview_page

register_page(
    __name__,
    path="/enola/internal/production-overview",
    title="HOLMES - Enola - Production Overview",
    name="HOLMES - Enola - Production Overview",
)

layout = create_production_overview_page(ns="enola-prod")
