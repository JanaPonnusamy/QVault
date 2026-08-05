<#
.SYNOPSIS
  One-time setup for a new QVault scraper node. Run this ON THE NEW PC,
  in an elevated (Administrator) PowerShell window, after cloning the repo
  there and installing Python/Node prerequisites (see CLAUDE.md).

  Registers the backend as a Scheduled Task that runs at system startup
  (even with no user logged in) and starts it immediately. From then on,
  your dev PC controls it remotely over PowerShell Remoting (WinRM) using
  remote_update.ps1 in this same folder -- no need to physically touch
  this machine again for routine updates.

.PARAMETER RepoPath
  Where the QVault repo lives on this PC. Defaults to E:\QVault to match
  the dev PC convention (CLAUDE.md), override if this machine differs.

.PARAMETER Port
  Backend port. Defaults to 8005 (this repo's current convention --
  see backend/app/config/settings.py and frontend/vite.config.ts).
#>
param(
    [string]$RepoPath = "E:\QVault",
    [int]$Port = 8005
)

$ErrorActionPreference = "Stop"

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this script as Administrator (right-click PowerShell -> Run as Administrator)."
}

# 1) Enable PowerShell Remoting so the dev PC can control this node.
Write-Host "Enabling PowerShell Remoting (WinRM)..." -ForegroundColor Cyan
Enable-PSRemoting -Force -SkipNetworkProfileCheck | Out-Null

# 2) Register the backend as a Scheduled Task -- runs at startup, survives
#    logoff, and is stoppable/startable remotely via Stop-ScheduledTask /
#    Start-ScheduledTask over WinRM. No extra tooling (e.g. NSSM) needed.
$taskName = "QVaultBackend"
$backendDir = Join-Path $RepoPath "backend"
$venvPython = Join-Path $backendDir ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    throw "Python venv not found at $venvPython -- create it first: cd $backendDir; python -m venv .venv; .venv\Scripts\pip install -r requirements.txt"
}

$action = New-ScheduledTaskAction -Execute $venvPython `
    -Argument "-m uvicorn app.main:app --host 0.0.0.0 --port $Port" `
    -WorkingDirectory $backendDir
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings | Out-Null

Write-Host "Starting QVaultBackend now..." -ForegroundColor Cyan
Start-ScheduledTask -TaskName $taskName
Start-Sleep -Seconds 5

$state = (Get-ScheduledTask -TaskName $taskName).State
Write-Host "Task '$taskName' state: $state" -ForegroundColor Green
Write-Host "Backend should be reachable at http://<this-pc-ip>:$Port/api/system/branding"
Write-Host ""
Write-Host "From your dev PC, add this PC to TrustedHosts (if not domain-joined) and test:" -ForegroundColor Yellow
Write-Host '  Set-Item WSMan:\localhost\Client\TrustedHosts -Value "<this-pc-ip>" -Concatenate -Force'
Write-Host '  Test-WSMan <this-pc-ip>'
