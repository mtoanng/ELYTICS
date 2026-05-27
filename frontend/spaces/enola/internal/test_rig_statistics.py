from dash import register_page
from spaces.shared.test_rig_statistics import create_test_rig_statistics_page

register_page(
    __name__,
    path="/enola/internal/test-rig-statistics",
    title="HOLMES - Enola - Test Rig Statistics",
    name="HOLMES - Enola - Test Rig Statistics",
)

layout = create_test_rig_statistics_page(ns="enola")
