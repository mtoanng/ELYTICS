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
            dmc.Title("Welcome to Enola Home", order=1),
            dmc.Text(
                "Enola provides comprehensive management and administration tools for system "
                "configuration and user access control.",
                size="md",
                c="dimmed",
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