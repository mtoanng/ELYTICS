$ACR="acrxplatformprodwesteu01.azurecr.io"
$TAG="develop"
$RESOURCE_GROUP="rg-holmes-suite-dev-westeu"
$APP="app-holmes-suite-dev"

az acr login --name acrxplatformprodwesteu01

docker build -t "$ACR/holmes-backend:$TAG" backend/
docker push "$ACR/holmes-backend:$TAG"

docker build -t "$ACR/holmes-frontend:$TAG" frontend/
docker push "$ACR/holmes-frontend:$TAG"

az webapp restart --name $APP --resource-group $RESOURCE_GROUP
