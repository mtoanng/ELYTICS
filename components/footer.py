from dash import html

def get_footer():
    return html.Footer(
        html.Img(
            src="/assets/Bosch-Supergraphic_Cut5.png",
            className="footer-img"
        )
    )
