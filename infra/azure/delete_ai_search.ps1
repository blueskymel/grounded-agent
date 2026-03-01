    param(
  [string]$ResourceGroup = "rg-roger-ai-102",
  [string]$SearchServiceName = "groundedagent-search"
)

$ErrorActionPreference = "Stop"

Write-Host "== GroundedAgent: Deleting Azure AI Search =="
Write-Host "Deleting Search service: $SearchServiceName in RG: $ResourceGroup"

az search service delete `
  --name $SearchServiceName `
  --resource-group $ResourceGroup `
  --yes | Out-Null

Write-Host "Deleted. Billing stops when the service is gone."