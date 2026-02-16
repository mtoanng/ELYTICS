#!/bin/bash
# Template for now, waiting on azure keyvault request to be approved and secrets to be added

KEYVAULT_NAME="my-project-kv"

echo "Fetching secrets from Azure Key Vault..."

DB_URL=$(az keyvault secret show \
  --vault-name $KEYVAULT_NAME \
  --name backend-db-url \
  --query value -o tsv)

JWT_SECRET=$(az keyvault secret show \
  --vault-name $KEYVAULT_NAME \
  --name backend-jwt-secret \
  --query value -o tsv)

cat > backend/.env <<EOL
DATABASE_URL=$DB_URL
JWT_SECRET=$JWT_SECRET
EOL

echo ".env file generated successfully."
