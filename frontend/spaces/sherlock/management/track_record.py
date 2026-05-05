from dash import register_page
from spaces.shared.track_record import create_track_record_page

register_page(
    __name__,
    path="/sherlock/management/track-record",
    title="HOLMES - Sherlock - Track Record",
    name="HOLMES - Sherlock - Track Record",
)

layout = create_track_record_page(ns="sherlock")
