# TBP-HOLMES Developer Guide

This developer guide will set you up with a development environment, from which you can run the application and start contributing to the codebase from. Roles and prerequisites can be done simultaniously, you can move to quickstart once you have been provisioned with the key vault roles and Docker has been installed.

## Roles

Before we begin setting up our development environment there are some roles which are needed to develop and use the application. Please request the following roles via OneIDM:

| Role | Description |
| --- | --- |
| IdM2BCD_holmes_pemely_user | End user access to Sherlock, Watson, Mycroft space |
| IdM2BCD_holmes_pemely_management | End user access to Enola space |
| IdM2BCD_holmes_pemely_development | End user access to development environment |
| IdM2BCD_xPlatform_az_kv_holmesprod_read | Read access to Holmes PROD Key Vault |
| IdM2BCD_xPlatform_az_kv_holmesdev_read | Read access to Holmes DEV Key Vault |

A note about `IdM2BCD_holmes_pemely_development`, this is designed to be the only role used in the development hosting environment on Azure App Service. This way we can easily test fixes/features, and also invite stakeholders who are close to development to view the DEV version throughout sprints. 

## Getting Started (Recommended: Dev Container)

**We strongly recommend all developers use Docker and the provided Dev Container for a consistent, hassle-free development environment.**

### Prerequisites

Docker and Visual Studio Code can be ordered [here](https://service-management.bosch.tech/sp?id=sc_cat_item&sys_id=b08ed16c1b83c91078087403dd4bcbb1).

- [Docker - Docupedia](https://inside-docupedia.bosch.com/confluence/spaces/AABDO/pages/6400935502/Docker+Desktop) (required)
- [Visual Studio Code](https://code.visualstudio.com/) (required)
- [GoNTLM](https://inside-docupedia.bosch.com/confluence/spaces/DEVCORNER/pages/2431652890/GoNTLM) (recommended - preferred alternative to RB Local Proxy Manager)
- [Azure CLI - Docupedia](https://inside-docupedia.bosch.com/confluence/spaces/AzureIMG/pages/1179022413/Azure+CLI) (recommended - automates `.env` file creation)
- [Dev Containers extension for VS Code](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) (recommended)

Once Docker is installed and running, you need to add these proxies to the docker config file, located at `C:\Users\<NT-USER>\.docker\config.json`. This is required for the dev container to have access to the internet.

```json
{
	// Other settings
	"proxies": {
		"default": {
			"httpProxy": "http://host.docker.internal:3128",
			"httpsProxy": "http://host.docker.internal:3128",
			"noProxy": "host.docker.internal,localhost,127.0.0.1,.bosch.com"
		}
	}
}
```

---

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
5. **Set up environment variables:**
	- After obtaining Azure Key Vault access, run:
		```sh
		./generate-env.ps1
		```
	- Select the `PS-BDO-DX-2-Prod` subscription when prompted. The script generates a `.env` file for frontend and backend. **Do not share these variables—always reference the Key Vault for access.**
	- Alternatively, manually retrieve secrets from the Azure dashboard (slower method).
6. **Run the application:**
	- In separate terminals inside the dev container, run the following:
	```sh
	cd backend
	python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
	```

	```sh
	cd frontend
	python app.py
	```
---

# TODO:
- add most popular forms of contribution to the repo
    - new page -> add page, add query to backend, create backend route, create filters if needed etc
    - new component -> find n occurances where component can be used, create and update all code, more modular 