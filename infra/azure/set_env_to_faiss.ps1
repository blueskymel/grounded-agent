# Auto-detect repo root (two levels up from infra\azure)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path "$ScriptDir\..\.."
$ApiEnvPath = Join-Path $RepoRoot "api\.env"

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

Write-Host "== Switching retrieval backend to FAISS =="

if (-not (Test-Path $ApiEnvPath)) {
  throw "Env file not found at $ApiEnvPath"
}

$lines = Get-Content -Path $ApiEnvPath -ErrorAction Stop

$lines = Set-OrAddEnvVar -Lines $lines -Key "RETRIEVAL_BACKEND" -Value "faiss"

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllLines((Resolve-Path $ApiEnvPath), $lines, $utf8NoBom)

Write-Host "Done."
Write-Host "RETRIEVAL_BACKEND=faiss"