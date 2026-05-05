from dash import register_page
import dash_mantine_components as dmc
from components.changelog import build_update_cards, load_changelog_json
import json
from pathlib import Path

register_page(__name__, path="/sherlock/home", title="Sherlock Space")

def sherlock_layout():
    changelog_path = Path(__file__).resolve().parent / "changelog.json"
    changelog = load_changelog_json(changelog_path)

    return dmc.Container(
        size="md",
        pt="md",
        pb="xl",
        children=[
            dmc.Title("Welcome to Sherlock Home", order=1),
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
            dmc.Stack(
                [
                    dmc.Title("Latest Updates & Features", order=2),
                    dmc.Stack(
                        build_update_cards(changelog, "Sherlock", "blue"),
                        gap="md",
                    ),
                ],
                gap="lg",
                mt="xl",
            ),
        ],
    )

layout = sherlock_layout