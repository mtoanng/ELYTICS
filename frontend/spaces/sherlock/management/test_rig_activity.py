from dash import register_page
from spaces.shared.test_rig_activity import create_test_rig_activity_page

register_page(
    __name__,
    path="/sherlock/management/test-rig-activity",
    title="HOLMES - Sherlock - Test Rig Activity",
    name="HOLMES - Sherlock - Test Rig Activity",
)

layout = create_test_rig_activity_page(ns="sherlock")
