import dash_mantine_components as dmc
from dash import html
from config.access_config import PAGE_ACCESS_MAP

def create_access_warning(space_name: str = None):
    """
    Create a custom access warning component.
    
    Args:
        space_name: The name of the space the user is trying to access.
                   If provided, shows the specific role needed for that space.
    """
    
    # Get the required role from the space mapping
    required_role = None
    if space_name:
        required_groups = PAGE_ACCESS_MAP.get(f"/{space_name}")
        required_role = required_groups[0] if required_groups else "appropriate OneIDM role"
    else:
        required_role = "appropriate OneIDM role"
    
    oneidm_url = "https://oneidm.bosch.com/oneidm/html/rbwebshop/#/start/new-request"
    
    return dmc.Container(
        [
            dmc.Stack(
                [
                    # Header section
                    dmc.Group(
                        [
                            dmc.ThemeIcon(
                                html.Span("⚠️"),
                                size="xl",
                                radius="md",
                                color="yellow",
                                variant="light",
                            ),
                            dmc.Stack(
                                [
                                    dmc.Title(
                                        "Access Restricted",
                                        order=2,
                                        size="h2",
                                    ),
                                    dmc.Text(
                                        f"You don't have access to {'the ' + space_name.capitalize() + ' space' if space_name else 'this space'}.",
                                        c="dimmed",
                                        size="sm",
                                    ),
                                ],
                                gap=0,
                            ),
                        ],
                        gap="lg",
                        align="flex-start",
                    ),
                    
                    # Required role card
                    dmc.Card(
                        [
                            dmc.Stack(
                                [
                                    dmc.Group(
                                        [
                                            dmc.Badge(
                                                "Required Role",
                                                color="blue",
                                                variant="dot",
                                                size="lg",
                                            ),
                                        ],
                                    ),
                                    dmc.Code(
                                        required_role,
                                        block=True,
                                        style={
                                            "padding": "12px",
                                            "borderRadius": "4px",
                                        },
                                    ),
                                ],
                                gap="sm",
                            )
                        ],
                        withBorder=True,
                        shadow="sm",
                        radius="md",
                        p="md",
                        mb="lg",
                    ),
                    
                    # Steps section with Stepper
                    dmc.Stack(
                        [
                            dmc.Group(
                                [
                                    dmc.Badge(
                                        "Steps to Request Access",
                                        color="green",
                                        variant="dot",
                                        size="lg",
                                    ),
                                ],
                            ),
                            dmc.Stepper(
                                active=0,
                                color="blue",
                                orientation="vertical",
                                children=[
                                    dmc.StepperStep(
                                        label="Open OneIDM",
                                        description=html.Span([
                                            "Click ",
                                            html.A(
                                                "here",
                                                href=oneidm_url,
                                                target="_blank",
                                                rel="noopener noreferrer",
                                                style={"color": "inherit", "textDecoration": "underline"}
                                            ),
                                            " to create a new request in OneIDM.",
                                        ]),
                                    ),
                                    dmc.StepperStep(
                                        label="Search for Role",
                                        description=f"Search for and select the OneIDM role: {required_role}",
                                    ),
                                    dmc.StepperStep(
                                        label="Add to Cart",
                                        description="Click 'add to shopping cart' in the bottom right.",
                                    ),
                                    dmc.StepperStep(
                                        label="Review Cart",
                                        description="Click 'shopping cart' in the top right.",
                                    ),
                                    dmc.StepperStep(
                                        label="Add Justification",
                                        description="Click 'enter justification' in the bottom right.",
                                    ),
                                    dmc.StepperStep(
                                        label="Fill Reason",
                                        description="Fill in a necessary reason for gaining access and click 'save'.",
                                    ),
                                    dmc.StepperStep(
                                        label="Submit Request",
                                        description="Click 'order' in the bottom right to submit your request.",
                                    ),
                                ],
                            ),
                        ],
                        gap="md",
                    ),
                    
                    # Info box
                    dmc.Alert(
                        "Once you've submitted your request, it may take some time for the role to be assigned. Please contact the Access Right Owner if you have questions.",
                        title="Information",
                        color="blue",
                        icon="ℹ️",
                    ),
                ],
                gap="lg",
                style={"paddingTop": "40px", "paddingBottom": "40px"},
            )
        ],
        size="sm",
        py="xl",
    )