## Frontend Overview

This document provides guidance on the structure, standards, and best practices for developing the TBP-HOLMES frontend.

### Dash Mantine Usage

We use [Dash Mantine Components](https://www.dash-mantine-components.com/) as our primary UI toolkit.  
**All developers are encouraged to use Dash Mantine components** for building new UI features to ensure a consistent look and feel across the application.  
Refer to the [Dash Mantine documentation](https://www.dash-mantine-components.com/docs/getting-started/) for usage examples and available components.

---

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

def polarization_layout():
    return html.Div("polarization content")

layout = polarization_layout
```

---

## Authentication

This is handled by `components/appshell.py`, along with some functions from `services/auth.py`. Access rights are applied at the base of the application, therefore developers do not need to worry about auth within their spaces. If we ever wish to add/change spaces and permissions, then `config/access_config.py` needs to be updated, the rest is applied based on the dictionary in there.

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

## Project Structure

- `app.py` — Main application entry point
- `components/` — UI components
- `config/` — Configuration for spaces (Like access permissions)
- `services/` — Service layer (e.g., Databricks integration)
- `spaces/` — App spaces/pages (Additional documentation can be found in here)
- `assets/` — Static assets (CSS, icons)
- `tests/` — Test suite