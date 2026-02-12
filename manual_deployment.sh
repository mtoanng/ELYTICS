#!/bin/bash

# Login
az acr login --name acrxplatformprodwesteu01

# Build and push frontend image
docker build -t holmes-frontend:develop frontend/

docker tag holmes-frontend:develop acrxplatformprodwesteu01.azurecr.io/holmes-frontend:develop

docker push acrxplatformprodwesteu01.azurecr.io/holmes-frontend:develop

# Build and push backend image
docker build -t holmes-backend:develop backend/

docker tag holmes-backend:develop acrxplatformprodwesteu01.azurecr.io/holmes-backend:develop

docker push acrxplatformprodwesteu01.azurecr.io/holmes-backend:develop