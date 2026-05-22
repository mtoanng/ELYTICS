$ACR="acrxplatformprodwesteu01.azurecr.io"
$TAG="release"
$RESOURCE_GROUP="rg-holmes-suite-prod-westeu"
$APP="app-holmes-suite-prod"

az acr login --name acrxplatformprodwesteu01

docker build -t "$ACR/holmes-backend:$TAG" backend/
docker push "$ACR/holmes-backend:$TAG"

docker build -t "$ACR/holmes-frontend:$TAG" frontend/
docker push "$ACR/holmes-frontend:$TAG"

az webapp restart --name $APP --resource-group $RESOURCE_GROUP
