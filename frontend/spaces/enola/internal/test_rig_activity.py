from dash import register_page
from spaces.shared.test_rig_activity import create_test_rig_activity_page

register_page(
    __name__,
    path="/enola/internal/test-rig-activity",
    title="HOLMES - Enola - Test Rig Activity",
    name="HOLMES - Enola - Test Rig Activity",
)

layout = create_test_rig_activity_page(ns="enola")