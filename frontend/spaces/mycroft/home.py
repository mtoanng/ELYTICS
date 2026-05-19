from dash import register_page
import dash_mantine_components as dmc
from components.changelog import build_update_cards, load_changelog_json
from pathlib import Path

register_page(__name__, path="/mycroft/home", title="HOLMES - Mycroft")

def mycroft_layout():
    changelog_path = Path(__file__).resolve().parent / "changelog.json"
    changelog = load_changelog_json(changelog_path)
    
    return dmc.Container(
        size="md",
        pt="md",
        pb="xl",
        children=[
            dmc.Title("Welcome to PEMELY Mycroft", order=1),
            dmc.Text(
                "Explore ELY AsProduced Stack Data, everything related to manufacturing of ELY stacks.",
                size="md",
                c="dimmed",
            ),
            dmc.Title("What can you do here?", order=2, mt="xl"),
            dmc.List(
                [
                    dmc.ListItem([
                        dmc.Text("Management: ", fw=700, span=True),
                        "View production overview and status."
                    ]),
                    dmc.ListItem([
                        dmc.Text("Data Exploration: ", fw=700, span=True),
                        "Check stack overviews, soaking data, CVM measurements and EOL Polarization Curves."
                    ]),
                    dmc.ListItem([
                        dmc.Text("Data Analysis: ", fw=700, span=True),
                        "Analyse the trends in EOL data."
                    ]),
                ],
                spacing="md",
            ),
            dmc.Stack(
                [
                    dmc.Title("Latest Updates & Features", order=2),
                    dmc.Stack(
                        build_update_cards(changelog, "Mycroft", "grape"),
                        gap="md",
                    ),
                ],
                gap="lg",
                mt="xl",
            ),
        ],
    )

layout = mycroft_layout