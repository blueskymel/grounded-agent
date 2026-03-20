# Deploy GroundedAgent to Azure Container Apps

This guide covers deploying the API to Azure Container Apps using either the Azure Developer CLI (`azd`, recommended) or manual Azure CLI steps.

## Architecture

```
ACR (Basic)
  └─ grounded-agent-api image
       └─ Container App (0.5 vCPU / 1 GiB, 1–3 replicas)
            ├─ Container Apps Environment
            │    └─ Log Analytics Workspace
            └─ User-Assigned Managed Identity (AcrPull role)
```

All secrets (API keys) are stored as Container App secrets and injected as environment variables. No secrets appear in Bicep parameters or deployment state output.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Azure subscription | Contributor + User Access Administrator on the target subscription |
| Azure CLI (`az`) | `az login` completed |
| Docker | Local Docker Desktop (for manual path) |
| Azure Developer CLI (`azd`) | `winget install Microsoft.Azd` — for the azd path |
| Existing Azure AI Search | See `infra/azure/create_ai_search.ps1` |
| Existing Azure OpenAI deployments | `gpt-4o` + `text-embedding-3-small` (or adjust parameter names) |

---

## Option A — azd (recommended)

`azd up` provisions infrastructure, builds the image, pushes to ACR, and deploys the Container App in one command.

### 1. Set environment variables

```powershell
# Required — your existing Azure resources
$env:AZURE_OPENAI_ENDPOINT              = "https://<your-aoai>.openai.azure.com/"
$env:AZURE_OPENAI_API_KEY               = "<key>"
$env:AZURE_OPENAI_CHAT_DEPLOYMENT       = "gpt-4o"
$env:AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT = "text-embedding-3-small"
$env:AZURE_SEARCH_ENDPOINT              = "https://<your-search>.search.windows.net"
$env:AZURE_SEARCH_API_KEY               = "<key>"
$env:AZURE_SEARCH_INDEX_NAME            = "groundedagent-chunks"

# Optional — Application Insights
$env:APPLICATIONINSIGHTS_CONNECTION_STRING = "InstrumentationKey=..."
```

### 2. Initialise and deploy

```powershell
# From the repo root
azd auth login
azd env new grounded-dev          # pick a short environment name
azd env set AZURE_LOCATION australiaeast

# Provision infra + build + push + deploy
azd up
```

`azd up` will ask for your Azure subscription the first time. When complete it prints the Container App URL.

### 3. Verify

```powershell
$url = azd env get-value SERVICE_API_URI
curl "$url/health"
```

### Subsequent deploys

```powershell
azd deploy   # rebuild image and update Container App only (skips infra)
```

### Tear down

```powershell
azd down --purge   # removes the resource group and all resources
```

---

## Option B — Manual Azure CLI steps

Use this path if you prefer full visibility or are integrating into an existing pipeline.

### 1. Set variables

```powershell
$ENV_NAME    = "grounded-dev"
$LOCATION    = "australiaeast"
$RG          = "rg-grounded-agent-$ENV_NAME"
$SUBSCRIPTION = az account show --query id -o tsv
```

### 2. Deploy infrastructure

```powershell
az deployment sub create `
  --name "grounded-agent-infra" `
  --location $LOCATION `
  --template-file infra/main.bicep `
  --parameters `
      environmentName=$ENV_NAME `
      location=$LOCATION `
      azureOpenAiEndpoint=$env:AZURE_OPENAI_ENDPOINT `
      azureOpenAiApiKey=$env:AZURE_OPENAI_API_KEY `
      azureOpenAiChatDeployment=$env:AZURE_OPENAI_CHAT_DEPLOYMENT `
      azureOpenAiEmbeddingsDeployment=$env:AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT `
      azureSearchEndpoint=$env:AZURE_SEARCH_ENDPOINT `
      azureSearchApiKey=$env:AZURE_SEARCH_API_KEY `
      azureSearchIndexName=$env:AZURE_SEARCH_INDEX_NAME
```

### 3. Build and push the image

```powershell
# Get the ACR name from the deployment output
$ACR = az deployment sub show `
  --name "grounded-agent-infra" `
  --query "properties.outputs.AZURE_CONTAINER_REGISTRY_NAME.value" -o tsv

# az acr build runs the build in the cloud — no local Docker required
az acr build `
  --registry $ACR `
  --image grounded-agent-api:latest `
  --file docker/api.Dockerfile `
  .
```

### 4. Update the Container App to use the new image

```powershell
$CA_NAME  = az deployment sub show `
  --name "grounded-agent-infra" `
  --query "properties.outputs.SERVICE_API_CONTAINER_APP_NAME.value" -o tsv

az containerapp update `
  --name $CA_NAME `
  --resource-group $RG `
  --image "$ACR.azurecr.io/grounded-agent-api:latest"
```

### 5. Get the URL

```powershell
az containerapp show `
  --name $CA_NAME `
  --resource-group $RG `
  --query "properties.configuration.ingress.fqdn" -o tsv
```

---

## Environment Variable Reference

| Variable | Required | Notes |
|---|---|---|
| `AZURE_OPENAI_ENDPOINT` | Yes | `https://<name>.openai.azure.com/` |
| `AZURE_OPENAI_API_KEY` | Yes | Stored as Container App secret |
| `AZURE_OPENAI_API_VERSION` | No | Defaults to `2024-10-21` |
| `AZURE_OPENAI_CHAT_DEPLOYMENT` | Yes | Name of your `gpt-4o` deployment |
| `AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT` | Yes | Name of your embeddings deployment |
| `AZURE_SEARCH_ENDPOINT` | Yes | `https://<name>.search.windows.net` |
| `AZURE_SEARCH_API_KEY` | Yes | Stored as Container App secret |
| `AZURE_SEARCH_INDEX_NAME` | No | Defaults to `groundedagent-chunks` |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | No | Enables App Insights telemetry export |

---

## Post-Deploy Checks

```powershell
# Health check
curl https://<fqdn>/health

# KB introspection
curl https://<fqdn>/kb/stats

# Chat
curl -X POST https://<fqdn>/chat `
  -H "Content-Type: application/json" `
  -d '{"message": "What is the P1 runbook process?"}'
```

---

## Scaling and Cost Notes

- Default: **1 replica minimum**, scales to 3 at 20 concurrent requests.
- Set `minReplicas: 0` in `container-app.bicep` to scale to zero for demo/dev environments (accept cold-start latency).
- ACR Basic SKU costs ~$0.17/day. Upgrade to Standard for geo-replication or content trust.
- Container Apps are billed per vCPU-second and GiB-second when active, plus per request at scale-to-zero.
