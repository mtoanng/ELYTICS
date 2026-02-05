from dash_auth import protected
from dash import register_page
import dash_mantine_components as dmc

register_page(__name__, path="/sherlock/home", title="Sherlock Space")

example_updates = [
    "🔹 New: AI/ML Predictions page now available for advanced forecasting.",
    "🔹 Improved: Timeseries Overview supports larger datasets.",
    "🔹 Update: Enhanced visualization in Polarization Curves.",
]

def get_latest_updates():
    return dmc.List(
        [dmc.ListItem(update) for update in example_updates],
        icon=None,
    )

@protected(
    dmc.Alert(
        title="Access Denied",
        color="red",
        children="You do not have permission to access this space.",
    ),
    groups=["IdM2BCD_holmes_pemely_user"]
)
def sherlock_layout():
    return dmc.Container(
        size="md",
        children=[
            dmc.Title("Welcome to Sherlock Home", order=1, mt="lg"),
            dmc.Text(
                "Sherlock is your unified workspace for battery test data management, "
                "exploration, and advanced analytics. Here you can monitor test rigs, "
                "explore datasets, and leverage AI/ML tools for deeper insights.",
                size="md",
                c="dimmed",
            ),
            dmc.Title("What can you do here?", order=2, mt="xl"),
            dmc.List(
                [
                    dmc.ListItem([
                        dmc.Text("Management: ", fw=700, span=True),
                        "View Test Statistics and monitor Test Rig Activity."
                    ]),
                    dmc.ListItem([
                        dmc.Text("Data Exploration: ", fw=700, span=True),
                        "Dive into Order, Sample, CCM, and Timeseries Overviews. Analyze Polarization Curves."
                    ]),
                    dmc.ListItem([
                        dmc.Text("Data Analysis: ", fw=700, span=True),
                        "Generate Summary Stats and custom Charts."
                    ]),
                    dmc.ListItem([
                        dmc.Text("AI/ML: ", fw=700, span=True),
                        "Access Model Overview and generate Predictions."
                    ]),
                ],
                spacing="md",
            ),
            dmc.Title("Latest Updates & Features", order=2, mt="xl"),
            get_latest_updates(),
        ],
        py="xl",
    )

layout = sherlock_layout