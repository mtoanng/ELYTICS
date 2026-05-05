from dash import register_page
from spaces.shared.track_record import create_track_record_page

register_page(
    __name__,
    path="/enola/internal/track-record",
    title="HOLMES - Enola - Track Record",
    name="HOLMES - Enola - Track Record",
)

layout = create_track_record_page(ns="enola")
