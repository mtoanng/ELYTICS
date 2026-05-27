from dash import register_page
from spaces.shared.test_rig_statistics import create_test_rig_statistics_page

register_page(
    __name__,
    path="/sherlock/management/test-rig-statistics",
    title="HOLMES - Sherlock - Test Rig Statistics",
    name="HOLMES - Sherlock - Test Rig Statistics",
)

layout = create_test_rig_statistics_page(ns="sherlock")
