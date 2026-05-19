from dash import register_page
import dash_mantine_components as dmc
from components.changelog import build_update_cards, load_changelog_json
from pathlib import Path

register_page(__name__, path="/enola/home", title="HOLMES - Enola")

def enola_layout():
    changelog_path = Path(__file__).resolve().parent / "changelog.json"
    changelog = load_changelog_json(changelog_path)
    
    return dmc.Container(
        size="md",
        pt="md",
        pb="xl",
        children=[
            dmc.Title("Welcome to PEMELY Enola", order=1),
            dmc.Text(
                "Explore ELY Management Overview and get a strategic, bird's-EYE view of PEM Electrolyzer activities.",
                size="md",
                c="dimmed",
            ),
            dmc.Title("What can you do here?", order=2, mt="xl"),
            dmc.List(
                [
                    dmc.ListItem([
                        dmc.Text("Internal: ", fw=700, span=True),
                        "View Stack details, Test Statistics and monitor Test (Rig) Activity."
                    ]),
                    dmc.ListItem([
                        dmc.Text("Customers: ", fw=700, span=True),
                        "Get customer overview."
                    ]),
                ],
                spacing="md",
            ),
            dmc.Stack(
                [
                    dmc.Title("Latest Updates & Features", order=2),
                    dmc.Stack(
                        build_update_cards(changelog, "Enola", "red"),
                        gap="md",
                    ),
                ],
                gap="lg",
                mt="xl",
            ),
        ],
    )

layout = enola_layout