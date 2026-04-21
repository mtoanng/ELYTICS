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
            dmc.Title("Welcome to Mycroft Home", order=1),
            dmc.Text(
                "Mycroft provides comprehensive data visualization and reporting tools "
                "for business intelligence and insights.",
                size="md",
                c="dimmed",
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