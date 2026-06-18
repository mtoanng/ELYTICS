# Prompt the user for environment input (loops until a valid option is provided)
do {
    $choice = (Read-Host "Select environment, deploy to [p]rod or [d]ev:").ToLower()
} while ($choice -notin @('p', 'd'))

# Dynamically set variables based on selection
if ($choice -eq 'p') {
    $TAG="release"
    $RESOURCE_GROUP="rg-holmes-suite-prod-westeu"
    $APP="app-holmes-suite-prod"
    Write-Host "`nConfiguring script for PRODUCTION environment..." -ForegroundColor Green
} else {
    $TAG="develop"
    $RESOURCE_GROUP="rg-holmes-suite-dev-westeu"
    $APP="app-holmes-suite-dev"
    Write-Host "`nConfiguring script for DEVELOPMENT environment..." -ForegroundColor Blue
}


# Login to Azure Container Registry ('acr' part of the command)
$ACR="acrxplatformprodwesteu01.azurecr.io"
az acr login --name acrxplatformprodwesteu01
Write-Host " - Logged into Azure Container Registry." -ForegroundColor Yellow

# Build and push backend image to Azure Container Registry
docker build -t "$ACR/holmes-backend:$TAG" backend/
docker push "$ACR/holmes-backend:$TAG"
Write-Host " - Backend build and pushed." -ForegroundColor Yellow

# Build and push frontend image to Azure Container Registry
docker build -t "$ACR/holmes-frontend:$TAG" frontend/
docker push "$ACR/holmes-frontend:$TAG"
Write-Host " - Frontend build and pushed." -ForegroundColor Yellow

# Trigger restart on Azure App Service -> this results in pulling the new images
Write-Host " - App restart triggered." -ForegroundColor Yellow
az webapp restart --name $APP --resource-group $RESOURCE_GROUP

# App restart is really quick, typically under a minute from executing this script
Write-Host "`nDeployment of '$TAG' branch completed and restarted $APP on $RESOURCE_GROUP`n" -ForegroundColor Cyan