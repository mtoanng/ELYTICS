$ACR="acrxplatformprodwesteu01.azurecr.io"
$TAG="develop"

az acr login --name acrxplatformprodwesteu01

docker build -t "$ACR/holmes-backend:$TAG" backend/
docker push "$ACR/holmes-backend:$TAG"

docker build -t "$ACR/holmes-frontend:$TAG" frontend/
docker push "$ACR/holmes-frontend:$TAG"