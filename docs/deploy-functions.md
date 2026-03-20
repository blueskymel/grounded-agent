# Deploy GroundedAgent to Azure Functions

This guide adds an Azure Functions hosting option for the existing FastAPI app by using `azure.functions.AsgiFunctionApp`.

## What this scaffold includes

- Bicep module: `infra/azure/function-app.bicep`
- Hosting switch: `infra/main.bicep` with `hostingModel=functions`
- Function entrypoint: `functionapp/function_app.py`
- Function runtime config: `functionapp/host.json`

## Prerequisites

- Azure CLI logged in (`az login`)
- Azure Functions Core Tools (for local test, optional)
- Python 3.11

## 1. Provision Azure resources

Use the same top-level Bicep but switch hosting model:

```powershell
$ENV_NAME = "grounded-dev"
$LOCATION = "australiaeast"

az deployment sub create `
  --name "grounded-agent-func-infra" `
  --location $LOCATION `
  --template-file infra/main.bicep `
  --parameters `
      environmentName=$ENV_NAME `
      location=$LOCATION `
      hostingModel=functions `
      azureOpenAiEndpoint=$env:AZURE_OPENAI_ENDPOINT `
      azureOpenAiApiKey=$env:AZURE_OPENAI_API_KEY `
      azureOpenAiChatDeployment=$env:AZURE_OPENAI_CHAT_DEPLOYMENT `
      azureOpenAiEmbeddingsDeployment=$env:AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT `
      azureSearchEndpoint=$env:AZURE_SEARCH_ENDPOINT `
      azureSearchApiKey=$env:AZURE_SEARCH_API_KEY `
      azureSearchIndexName=$env:AZURE_SEARCH_INDEX_NAME
```

Get outputs:

```powershell
$RG = az deployment sub show --name grounded-agent-func-infra --query "properties.outputs.RESOURCE_GROUP_NAME.value" -o tsv
$FUNC = az deployment sub show --name grounded-agent-func-infra --query "properties.outputs.SERVICE_API_FUNCTION_APP_NAME.value" -o tsv
```

## 2. Build a deployment package

Create a zip where `host.json` and `function_app.py` are at package root and `api/` is included for imports.

```powershell
$pkgRoot = Join-Path $PWD ".funcpkg"
if (Test-Path $pkgRoot) { Remove-Item $pkgRoot -Recurse -Force }
New-Item -ItemType Directory -Path $pkgRoot | Out-Null

Copy-Item functionapp\host.json $pkgRoot
Copy-Item functionapp\function_app.py $pkgRoot
Copy-Item functionapp\requirements.txt $pkgRoot
Copy-Item api (Join-Path $pkgRoot "api") -Recurse

Compress-Archive -Path "$pkgRoot\*" -DestinationPath "$pkgRoot\grounded-agent-function.zip" -Force
```

## 3. Deploy code to the Function App

```powershell
az functionapp deployment source config-zip `
  --resource-group $RG `
  --name $FUNC `
  --src "$pkgRoot\grounded-agent-function.zip"
```

## 4. Verify

```powershell
$base = "https://$FUNC.azurewebsites.net"
curl "$base/api/health"
curl "$base/api/kb"
```

## Notes

- Default function auth level is `FUNCTION`; calls require a function key unless changed.
- This scaffold preserves the existing FastAPI app and endpoints under the Functions `/api` route prefix.
- The current `azd` service in `azure.yaml` still targets Container Apps. Functions deployment is provided through this Bicep + zip path.

## GitHub Actions deployment workflow

This repo now includes `.github/workflows/functions-deploy.yml` for manual (workflow_dispatch) Function App deployment.

Inputs:

- `resource_group`
- `function_app_name`
- `run_smoke_test` (default `true`)
- `evidence_label` (default `functions-cutover`)

Required repository secrets for Azure OIDC login:

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`

The workflow:

1. Runs a quality gate (`ruff`, `pytest`, `eval.run_eval`, `eval.gate`) before deployment.
2. Packages `functionapp/` plus `api/` into a zip.
3. Logs into Azure via `azure/login@v2` using OIDC.
4. Runs `az functionapp deployment source config-zip`.
5. Optionally verifies `GET /api/health`.
6. Runs retry-based post-deploy health verification (`/api/health`) to reduce transient startup false negatives.
7. Collects deployment diagnostics on failure (`az functionapp` deployment logs and app settings metadata).
8. Uploads a deployment evidence artifact containing metadata and health-check output.
