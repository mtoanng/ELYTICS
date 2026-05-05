from dash import register_page
import dash_mantine_components as dmc

register_page(__name__, path="/enola/customer/customer-overview", title="HOLMES - Enola - Customer Overview")

def customer_overview_layout():    
    return dmc.Text("Placeholder content for Enola customer overview")
    
layout = customer_overview_layout