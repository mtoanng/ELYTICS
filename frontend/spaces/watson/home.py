from dash import register_page
import dash_mantine_components as dmc
from components.changelog import build_update_cards, load_changelog_json
from pathlib import Path

register_page(__name__, path="/watson/home", title="Watson Space")

def watson_layout():
    changelog_path = Path(__file__).resolve().parent / "changelog.json"
    changelog = load_changelog_json(changelog_path)
    
    return dmc.Container(
        size="md",
        children=[
            dmc.Title("Welcome to Watson Home", order=1, mt="lg"),
            dmc.Text(
                "Watson is your intelligent data processing and analysis workspace. "
                "Leverage advanced analytics and natural language processing for enhanced decision-making.",
                size="md",
                c="dimmed",
            ),
            dmc.Stack(
                [
                    dmc.Title("Latest Updates & Features", order=2),
                    dmc.Stack(
                        build_update_cards(changelog, "Watson", "cyan"),
                        gap="md",
                    ),
                ],
                gap="lg",
                mt="xl",
            ),
        ],
        py="xl",
    )

layout = watson_layout