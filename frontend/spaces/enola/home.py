from dash import register_page
import dash_mantine_components as dmc
from components.changelog import build_update_cards
import json
from pathlib import Path

register_page(__name__, path="/enola/home", title="HOLMES - Enola")

def _load_changelog_json(changelog_path: Path) -> dict:
    if not changelog_path.exists():
        return {}
    with changelog_path.open(encoding="utf-8") as handle:
        return json.load(handle)

def enola_layout():
    changelog_path = Path(__file__).resolve().parent / "changelog.json"
    changelog = _load_changelog_json(changelog_path)
    
    return dmc.Container(
        size="md",
        children=[
            dmc.Title("Welcome to Enola Home", order=1, mt="lg"),
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
        py="xl",
    )

layout = enola_layout