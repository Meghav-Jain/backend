# deploy.ps1
# Deploys the FastAPI backend to Cloudflare Workers (Python) with a D1 database.
#
# Usage (from anywhere):
#   powershell -ExecutionPolicy Bypass -File .\backend\deploy.ps1
#
# Options:
#   -SkipMigrations   Do not apply D1 migrations
#   -DatabaseName     D1 database name (default: todo-db, must match wrangler.jsonc)

param(
    [string]$DatabaseName = "todo-db",
    [switch]$SkipMigrations
)

# Native commands are checked via $LASTEXITCODE; "Stop" would make PS 5.1 abort on any stderr output.
$ErrorActionPreference = "Continue"
$Wrangler = "wrangler@4"

function Step($msg) { Write-Host ""; Write-Host "==> $msg" -ForegroundColor Cyan }
function Fail($msg) { Write-Host "ERROR: $msg" -ForegroundColor Red; exit 1 }

# Runs a native command, echoes it, and fails the script on a non-zero exit code.
function Invoke-Checked {
    param([string]$Exe, [string[]]$Arguments)
    Write-Host "   > $Exe $($Arguments -join ' ')" -ForegroundColor DarkGray
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { Fail "'$Exe $($Arguments -join ' ')' exited with code $LASTEXITCODE" }
}

# Returns the uuid of the named D1 database, or $null if it doesn't exist.
function Get-D1DatabaseId([string]$Name) {
    $raw = (& npx --yes $Wrangler d1 list --json 2>$null) -join "`n"
    if ($LASTEXITCODE -ne 0) { Fail "Could not list D1 databases." }
    $start = $raw.IndexOf("[")
    if ($start -lt 0) { Fail "Unexpected output from 'wrangler d1 list':`n$raw" }
    $dbs = $raw.Substring($start) | ConvertFrom-Json
    $match = $dbs | Where-Object { $_.name -eq $Name } | Select-Object -First 1
    if ($match) { return $match.uuid }
    return $null
}

# Always run from the backend folder (where wrangler.jsonc lives).
Set-Location -Path $PSScriptRoot
$ConfigPath = Join-Path $PSScriptRoot "wrangler.jsonc"
if (-not (Test-Path $ConfigPath)) { Fail "wrangler.jsonc not found in $PSScriptRoot" }

# 1. Prerequisites ---------------------------------------------------------
Step "Checking prerequisites"
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Fail "Node.js is required (for wrangler). Install it from https://nodejs.org and re-run."
}
Write-Host "   node $(node --version)"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "   uv not found - installing it (needed for Python Workers)..."
    powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    if ($LASTEXITCODE -ne 0) { Fail "uv install failed. See https://docs.astral.sh/uv/" }
    # Make the freshly installed uv visible to this session.
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Fail "uv was installed but isn't on PATH. Open a new terminal and re-run."
    }
}
Write-Host "   $(uv --version)"

# 2. Cloudflare login ------------------------------------------------------
Step "Checking Cloudflare login"
$who = (& npx --yes $Wrangler whoami 2>&1) -join "`n"
if ($LASTEXITCODE -ne 0 -or $who -match "not authenticated|You are not logged in") {
    Write-Host "   Not logged in - opening the browser..."
    Invoke-Checked "npx" @("--yes", $Wrangler, "login")
} else {
    Write-Host "   Already logged in."
}

# 3. D1 database -----------------------------------------------------------
Step "Ensuring D1 database '$DatabaseName' exists"
$dbId = Get-D1DatabaseId $DatabaseName
if ($dbId) {
    Write-Host "   Found existing database: $dbId"
} else {
    Write-Host "   Creating database..."
    Invoke-Checked "npx" @("--yes", $Wrangler, "d1", "create", $DatabaseName)
    $dbId = Get-D1DatabaseId $DatabaseName
    if (-not $dbId) { Fail "Database was created but its ID could not be found." }
    Write-Host "   Created database: $dbId"
}

# Write the ID into wrangler.jsonc (replaces the placeholder or a stale ID).
$config = Get-Content -Raw -Path $ConfigPath
$updated = [regex]::Replace($config, '("database_id"\s*:\s*")[^"]*(")', "`${1}$dbId`${2}")
if ($updated -ne $config) {
    [System.IO.File]::WriteAllText($ConfigPath, $updated, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "   Updated database_id in wrangler.jsonc"
}

# 4. Migrations ------------------------------------------------------------
if ($SkipMigrations) {
    Step "Skipping migrations"
} else {
    Step "Applying D1 migrations (remote)"
    Invoke-Checked "npx" @("--yes", $Wrangler, "d1", "migrations", "apply", $DatabaseName, "--remote")
}

# 5. Deploy ----------------------------------------------------------------
Step "Deploying Worker (pywrangler)"
Invoke-Checked "uv" @("run", "pywrangler", "deploy")

Write-Host ""
Write-Host "Deploy complete." -ForegroundColor Green
Write-Host "Test it:      curl https://todo-api.<your-subdomain>.workers.dev/tasks"
Write-Host "Frontend:     set VITE_API_URL to the Worker URL above and redeploy the frontend."
Write-Host "Live logs:    npx $Wrangler tail todo-api"
