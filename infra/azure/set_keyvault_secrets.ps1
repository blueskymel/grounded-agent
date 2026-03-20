param(
  [Parameter(Mandatory = $true)]
  [string]$VaultName,

  [string]$AzureOpenAiApiKey = $env:AZURE_OPENAI_API_KEY,
  [string]$AzureSearchApiKey = $env:AZURE_SEARCH_API_KEY,
  [string]$AppInsightsConnectionString = $env:APPLICATIONINSIGHTS_CONNECTION_STRING,

  [string]$AzureOpenAiApiKeySecretName = "azure-openai-api-key",
  [string]$AzureSearchApiKeySecretName = "azure-search-api-key",
  [string]$AppInsightsConnectionStringSecretName = "applicationinsights-connection-string"
)

$ErrorActionPreference = "Stop"

function Set-KeyVaultSecretIfPresent {
  param(
    [string]$Name,
    [string]$Value
  )

  if ([string]::IsNullOrWhiteSpace($Value)) {
    Write-Host "Skipping secret '$Name' because no value was provided."
    return
  }

  Write-Host "Setting secret '$Name' in vault '$VaultName'..."
  az keyvault secret set --vault-name $VaultName --name $Name --value $Value --output none
}

Write-Host "== GroundedAgent: Populating Key Vault secrets =="
Set-KeyVaultSecretIfPresent -Name $AzureOpenAiApiKeySecretName -Value $AzureOpenAiApiKey
Set-KeyVaultSecretIfPresent -Name $AzureSearchApiKeySecretName -Value $AzureSearchApiKey
Set-KeyVaultSecretIfPresent -Name $AppInsightsConnectionStringSecretName -Value $AppInsightsConnectionString
Write-Host "Done. Restart or redeploy the Container App after setting secrets."