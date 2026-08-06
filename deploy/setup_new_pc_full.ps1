<#
.SYNOPSIS
  ONE-TIME setup for a full QVault node (backend + frontend), run ON THAT PC
  in an elevated (Administrator) PowerShell window, after cloning the repo
  there and installing Python/Node prerequisites (see CLAUDE.md).

  Registers both the backend and the frontend dev server as Windows
  Scheduled Tasks that run at system startup, with no user logged in, and
  auto-restart on crash. After this one run, the app comes up on its own
  every time the machine boots -- nothing to re-run.

.PARAMETER RepoPath
  Where the QVault repo lives on this PC. Defaults to E:\QVault.

.PARAMETER BackendPort
  Defaults to 8005 (see backend/app/config/settings.py).

.PARAMETER FrontendPort
  Defaults to 5174 (see frontend/vite.config.ts).
#>
param(
    [string]$RepoPath = "E:\QVault",
    [int]$BackendPort = 8005,
    [int]$FrontendPort = 5174
)

$ErrorActionPreference = "Stop"

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this script as Administrator (right-click PowerShell -> Run as Administrator)."
}

# --- Backend ---------------------------------------------------------------
$backendDir = Join-Path $RepoPath "backend"
$venvPython = Join-Path $backendDir ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    throw "Python venv not found at $venvPython -- create it first: cd $backendDir; python -m venv .venv; .venv\Scripts\pip install -r requirements.txt"
}

$backendAction = New-ScheduledTaskAction -Execute $venvPython `
    -Argument "-m uvicorn app.main:app --host 0.0.0.0 --port $BackendPort" `
    -WorkingDirectory $backendDir
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

Write-Host "Registering QVaultBackend scheduled task..." -ForegroundColor Cyan
Unregister-ScheduledTask -TaskName "QVaultBackend" -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName "QVaultBackend" -Action $backendAction -Trigger $trigger -Principal $principal -Settings $settings | Out-Null

# --- Frontend ----------------------------------------------------------------
$frontendDir = Join-Path $RepoPath "frontend"
$npmCmd = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
if (-not $npmCmd) {
    throw "npm.cmd not found on PATH -- install Node.js on this machine first."
}
if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
    throw "frontend\node_modules not found -- run 'npm install' in $frontendDir first."
}

$frontendAction = New-ScheduledTaskAction -Execute $npmCmd `
    -Argument "run dev -- --host 0.0.0.0 --port $FrontendPort" `
    -WorkingDirectory $frontendDir

Write-Host "Registering QVaultFrontend scheduled task..." -ForegroundColor Cyan
Unregister-ScheduledTask -TaskName "QVaultFrontend" -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName "QVaultFrontend" -Action $frontendAction -Trigger $trigger -Principal $principal -Settings $settings | Out-Null

# --- Start both now ----------------------------------------------------------
Write-Host "Starting QVaultBackend and QVaultFrontend now..." -ForegroundColor Cyan
Start-ScheduledTask -TaskName "QVaultBackend"
Start-ScheduledTask -TaskName "QVaultFrontend"
Start-Sleep -Seconds 5

Get-ScheduledTask -TaskName "QVaultBackend", "QVaultFrontend" | ForEach-Object {
    Write-Host ("Task '{0}' state: {1}" -f $_.TaskName, $_.State) -ForegroundColor Green
}

Write-Host ""
Write-Host "Backend  -> http://<this-pc-ip>:$BackendPort/api/system/branding"
Write-Host "Frontend -> http://<this-pc-ip>:$FrontendPort"
Write-Host "Both tasks are set to 'At startup', run as SYSTEM, and auto-restart up to 3 times on failure -- no need to run this script again unless you rebuild the venv/node_modules from scratch."
