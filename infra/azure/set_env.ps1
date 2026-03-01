param(
  [string]$ResourceGroup = "rg-roger-ai-102",
  [string]$SearchServiceName = "groundedagent-search",
  [string]$IndexName = "groundedagent-chunks",
  [string]$ApiEnvPath = "api\.env",
  [string]$RetrievalBackend = "azure_search"
)

$ErrorActionPreference = "Stop"

function Set-OrAddEnvVar {
  param(
    [string[]]$Lines,
    [string]$Key,
    [string]$Value
  )

  $pattern = "^\s*$([Regex]::Escape($Key))\s*="
  $newLine = "$Key=$Value"

  $found = $false
  for ($i = 0; $i -lt $Lines.Count; $i++) {
    if ($Lines[$i] -match $pattern) {
      $Lines[$i] = $newLine
      $found = $true
      break
    }
  }

  if (-not $found) {
    $Lines += $newLine
  }

  return ,$Lines
}

Write-Host "== GroundedAgent: Updating api/.env with Azure AI Search settings =="

# 1) Ensure env file exists
if (-not (Test-Path $ApiEnvPath)) {
  Write-Host "Env file not found at '$ApiEnvPath'. Creating it..."
  New-Item -ItemType File -Path $ApiEnvPath | Out-Null
}

# 2) Fetch Search endpoint + admin key via Azure CLI
$endpoint = "https://$SearchServiceName.search.windows.net"

Write-Host "Fetching Azure Search admin key for service '$SearchServiceName' in RG '$ResourceGroup'..."
$adminKey = az search admin-key show `
  --resource-group $ResourceGroup `
  --service-name $SearchServiceName `
  --query primaryKey -o tsv

if ([string]::IsNullOrWhiteSpace($adminKey)) {
  throw "Failed to fetch admin key. Check az login, RG/service name, and permissions."
}

# 3) Read existing env lines
$lines = Get-Content -Path $ApiEnvPath -ErrorAction Stop

# 4) Update/add values
$lines = Set-OrAddEnvVar -Lines $lines -Key "RETRIEVAL_BACKEND" -Value $RetrievalBackend
$lines = Set-OrAddEnvVar -Lines $lines -Key "AZURE_SEARCH_ENDPOINT" -Value $endpoint
$lines = Set-OrAddEnvVar -Lines $lines -Key "AZURE_SEARCH_API_KEY" -Value $adminKey
$lines = Set-OrAddEnvVar -Lines $lines -Key "AZURE_SEARCH_INDEX_NAME" -Value $IndexName

# 5) Write back (preserve UTF-8)
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllLines((Resolve-Path $ApiEnvPath), $lines, $utf8NoBom)

Write-Host "Done. Updated:"
Write-Host " - RETRIEVAL_BACKEND=$RetrievalBackend"
Write-Host " - AZURE_SEARCH_ENDPOINT=$endpoint"
Write-Host " - AZURE_SEARCH_INDEX_NAME=$IndexName"
Write-Host " - AZURE_SEARCH_API_KEY=<set in file>"
Write-Host ""
Write-Host "Reminder: api/.env should NOT be committed (it's in .gitignore)."