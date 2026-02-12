# Spaces Directory Structure & Page Registration Guide

## Directory Structure

Organize this directory as follows:

```
spaces/
├── watson/      # Pages for Watson
├── enola/       # Pages for Enola
├── mycroft/     # Pages for Mycroft
└── sherlock/    # Pages for Sherlock
```

Each subdirectory contains pages relevant to that section.

---

## Page Registration Standard

Each page **must** follow a standard registration pattern.

**Example:**  
For the route `/sherlock/ai/polarization`, create the file:

```
spaces/sherlock/ai/polarization.py
```

With the following content:

```python
from services.auth import protected
from dash import html, register_page

register_page(__name__, path="/sherlock/ai/polarization")

@protected(
    html.Div("Access denied", style={"color": "red", "padding": "2rem"}),
    groups=["IdM2BCD_holmes_pemely_user"]  # 'user' group grants access to Sherlock
)
def polarization_layout():
    return html.Div("polarization content")

layout = polarization_layout
```

---

## Authentication Decorators

**All layout functions or callbacks must use the appropriate auth decorators.**

### Protected Layout Example

```python
from services.auth import protected

@protected(
    html.Div("Access denied", style={"color": "red", "padding": "2rem"}),
    groups=["IdM2BCD_holmes_pemely_management"]
)
def management_layout():
    return html.Div("Management content")
```

### Protected Callback Example

*Unsupported by our custom protected decorator in auth service*

```python
from dash_auth import protected_callback
from dash import Output, Input

@protected_callback(
    Output("some-output", "children"),
    Input("some-input", "value"),
    groups=["IdM2BCD_holmes_pemely_management"]
)
def update_output(value):
    return f"Value: {value}"
```

---

## Checking User Groups

To see which groups a user belongs to, use:

```python
from dash_auth import list_groups

groups = list_groups()
```

This returns a list of all groups associated with the current user session, including OneIDM roles.

---

## Group Access Policy

- **IdM2BCD_holmes_pemely_user**  
  Should grant access to: `sherlock`, `watson`, `mycroft`

- **IdM2BCD_holmes_pemely_management**  
  Should grant access to: `enola`

Additional OneIDM roles can be created and customized as needed.

---

## Automated Enforcement

**These group access policies are automatically enforced via Pytest.**

A test in `tests/test_authorization.py` statically analyzes all page files in the `spaces/` directory to ensure that each page is protected with the correct group(s) according to the policy above.  
If a page is missing the required authorization decorator or group, the test will fail, helping maintain security and consistency across the app.

---