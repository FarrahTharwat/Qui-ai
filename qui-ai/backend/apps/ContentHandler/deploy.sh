#!/bin/bash

# Set variables
RESOURCE_GROUP="Demo"
CONTAINER_APP_NAME="contenthandler-service"
ACR_NAME="contenthandleracr"
ACR_LOGIN_SERVER="${ACR_NAME}.azurecr.io"
IMAGE_NAME="${ACR_LOGIN_SERVER}/contenthandler:latest"
LOCATION="eastus2"
ENV_NAME="contenthandler-env"

# Log in to Azure
az login

# Log in to Azure Container Registry
az acr login --name $ACR_NAME

# Set your existing builder
docker buildx use farrahbuilder
docker buildx inspect farrahbuilder --bootstrap

# Build and push image for linux/amd64
docker buildx build --platform linux/amd64 \
  -t $IMAGE_NAME \
  --push .

# Update the Azure Container App with new image
az containerapp update \
  --name $CONTAINER_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --image $IMAGE_NAME \
  --revision-suffix $(date +%s)

echo "✅ Deployment to Azure Container Apps complete!"
