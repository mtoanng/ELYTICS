# Infrastructure Overview

This document describes the infrastructure, hosting, access rights, and CI/CD pipeline design for the TBP-HOLMES project.

---

## Pipeline Design Choice

We use a branch-based pipeline strategy to ensure code quality and traceability. All feature and bugfix work is merged into `develop` via pull requests (PRs). Production releases are merged into `main` after passing additional checks. This approach enables clear separation between development and production-ready code, and enforces changelog discipline.

---

## Hosting

### Azure App Service

- **DEV Environment:**  
  - Runs the latest code from the `develop` branch.
  - Used for integration testing and QA.
  - Requires OneIDM role `IdM2BCD_holmes_pemely_development` to access.

- **PROD Environment:**  
  - Runs code from the `main` branch.
  - Serves end users and connects to production data sources.

### Azure Container Registry (ACR)

- All container images (frontend, backend, redis) are built and pushed to a dedicated ACR.
- Images are tagged by branch and commit for traceability.

### Containers

- **Frontend:**  
  - Serves the user interface.
  - Built as a stateless container.

- **Backend:**  
  - Handles API requests, business logic, and data polling.
  - Connects to Databricks and Redis.

- **Redis:**  
  - Used as a cache and message broker.
  - Runs as a managed container for simplicity.

### Scalability

- All containers are deployed as scalable services in Azure App Service.
- Horizontal scaling is supported for frontend and backend containers.
- Redis can be scaled vertically as needed.

---

## Access Rights

### OneIDM - IT Application

- Access to the application is managed via OneIDM, ensuring only authorized users can interact with the system.

### Azure App Registration

- The application is registered in Azure AD for secure authentication and authorization.
- Service principals are used for backend-to-backend communication.

### OIDC Implementation

- **Frontend:**  
  - Integrates with Azure AD using OIDC for user authentication.
  - Passes tokens to the backend for API authorization.

- **Backend:**  
  - Validates OIDC tokens on each request.
  - Enforces role-based access control as needed.

---

## Pipelines

*To be updated -> want to start using changeset and automate changelogs based on branches/commits history*

- **PR into `develop`:**
  - Changelog must be updated.
  - If no changelog entry is present, the PR is automatically denied.

- **PR into `main`:**
  - Changelog must not contain any WIP versions.
  - If WIP entries are present, the PR is automatically denied.

This ensures that all changes are documented and that only production-ready changes are merged into `main`.

---