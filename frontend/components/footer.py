from dash import html

def footer_layout():
    return html.Footer(
        html.Img(
            src="/assets/Bosch-Supergraphic_Cut5.png",
            className="footer-img"
        )
    )

layout = footer_layout