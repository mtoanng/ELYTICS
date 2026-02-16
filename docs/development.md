# TBP-HOLMES Developer Guide

## Getting Started (Recommended: Dev Container)

**We strongly recommend all developers use Docker and the provided Dev Container for a consistent, hassle-free development environment.**

### Prerequisites

Docker and Visual Studio Code can be ordered [here](https://service-management.bosch.tech/sp?id=sc_cat_item&sys_id=b08ed16c1b83c91078087403dd4bcbb1)

- [Docker - Docupedia](https://inside-docupedia.bosch.com/confluence/spaces/AABDO/pages/6400935502/Docker+Desktop) (required)
- [Visual Studio Code](https://code.visualstudio.com/) (recommended)
- [Dev Containers extension for VS Code](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) (recommended)

### Quick Start with Dev Container

1. **Clone the repository:**
	```sh
	git clone https://BoschTransmissionTechnology@dev.azure.com/BoschTransmissionTechnology/ELY%20Analytics%20Solution/_git/TBP-HOLMES
	cd TBP-HOLMES
	```
2. **Open in VS Code.**
3. **Reopen in Container:**
	- When prompted, click "Reopen in Container". If not prompted, open the Command Palette (`Ctrl+Shift+P`), search for `Dev Containers: Reopen in Container` and select it.
4. **Wait for the container to build and dependencies to install.**
5. **Setup your environment:**
    - Please use the setup script to generate the necessary environment files
    ```sh
    az login
    generate-env.sh
    ```
6. **Run the application:**
	```sh
	# Inside the dev container terminal
	python app.py
	```

---

# TODO:
- add most popular forms of contribution to the repo
    - new page -> add page, add query to backend, create backend route, create filters if needed etc
    - new component -> find n occurances where component can be used, create and update all code, more modular 