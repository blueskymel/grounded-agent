param(
  [string]$ResourceGroup = "rg-roger-ai-102",
  [string]$Location = "australiaeast",
  [string]$SearchServiceName = "groundedagent-search",
  [string]$Sku = "basic",
  [string]$IndexName = "groundedagent-chunks",
  [int]$EmbeddingDimensions = 1536
)

$ErrorActionPreference = "Stop"

Write-Host "== GroundedAgent: Creating Azure AI Search =="

# 1) Ensure resource group exists
Write-Host "Ensuring resource group exists: $ResourceGroup ($Location)"
az group create --name $ResourceGroup --location $Location | Out-Null

# 2) Create Search service
Write-Host "Creating Search service: $SearchServiceName (SKU=$Sku)"
az search service create `
  --name $SearchServiceName `
  --resource-group $ResourceGroup `
  --location $Location `
  --sku $Sku | Out-Null

# 3) Get admin key
Write-Host "Fetching admin key..."
$adminKey = az search admin-key show `
  --resource-group $ResourceGroup `
  --service-name $SearchServiceName `
  --query primaryKey -o tsv

$endpoint = "https://$SearchServiceName.search.windows.net"

Write-Host "Search endpoint: $endpoint"
Write-Host "Index name: $IndexName"

# 4) Create (or update) the index via REST API
# Note: Using REST ensures vector config + semantic config are created exactly as we want.
$apiVersion = "2023-11-01"
$headers = @{
  "Content-Type" = "application/json"
  "api-key" = $adminKey
}

$indexBody = @{
  name = $IndexName
  fields = @(
    @{ name="id"; type="Edm.String"; key=$true },
    @{ name="doc_id"; type="Edm.String"; filterable=$true; sortable=$true },
    @{ name="chunk_id"; type="Edm.String"; filterable=$true; sortable=$true },
    @{ name="title"; type="Edm.String"; searchable=$true; analyzer="en.lucene" },
    @{ name="source_uri"; type="Edm.String" },
    @{ name="content"; type="Edm.String"; searchable=$true; analyzer="en.lucene" },
    @{
      name="contentVector"
      type="Collection(Edm.Single)"
      searchable=$true
      vectorSearchDimensions=$EmbeddingDimensions
      vectorSearchProfile="vectorProfile"
    }
  )
  vectorSearch = @{
    algorithms = @(
      @{ name="hnsw"; kind="hnsw" }
    )
    profiles = @(
      @{ name="vectorProfile"; algorithm="hnsw" }
    )
  }
  semantic = @{
    configurations = @(
      @{
        name="semanticConfig"
        prioritizedFields = @{
          titleField = @{ fieldName="title" }
          contentFields = @(@{ fieldName="content" })
        }
      }
    )
  }
} | ConvertTo-Json -Depth 10

$indexUrl = "$endpoint/indexes/$IndexName?api-version=$apiVersion"

Write-Host "Creating/updating index: $IndexUrl"
Invoke-RestMethod -Method Put -Uri $indexUrl -Headers $headers -Body $indexBody | Out-Null

Write-Host "== Done =="
Write-Host "Search endpoint: $endpoint"
Write-Host "Admin key (store in api/.env): $adminKey"
Write-Host "AZURE_SEARCH_ENDPOINT=$endpoint"
Write-Host "AZURE_SEARCH_API_KEY=<use the printed key>"
Write-Host "AZURE_SEARCH_INDEX_NAME=$IndexName"