<#
.SYNOPSIS
  Run this FROM YOUR DEV PC to update and restart the QVault backend on a
  remote scraper node over PowerShell Remoting -- no need to physically
  touch that machine. Stops the service, pulls the latest code, reinstalls
  any changed Python deps, restarts it, then checks it came back up.

.PARAMETER ComputerName
  IP or hostname of the remote scraper node (run setup_new_pc.ps1 there first).

.PARAMETER RepoPath
  Where the repo lives on the REMOTE machine. Defaults to E:\QVault.

.PARAMETER Port
  Backend port on the remote machine. Defaults to 8005.

.EXAMPLE
  .\remote_update.ps1 -ComputerName 192.168.10.50
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$ComputerName,
    [string]$RepoPath = "E:\QVault",
    [int]$Port = 8005,
    [PSCredential]$Credential
)

$ErrorActionPreference = "Stop"
$taskName = "QVaultBackend"

if (-not $Credential) {
    $Credential = Get-Credential -Message "Administrator credentials for $ComputerName"
}

Write-Host "Stopping QVaultBackend on $ComputerName..." -ForegroundColor Cyan
Invoke-Command -ComputerName $ComputerName -Credential $Credential -ScriptBlock {
    param($TaskName)
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
} -ArgumentList $taskName

Write-Host "Pulling latest code and syncing dependencies on $ComputerName..." -ForegroundColor Cyan
Invoke-Command -ComputerName $ComputerName -Credential $Credential -ScriptBlock {
    param($RepoPath)
    Set-Location $RepoPath
    git pull
    & "$RepoPath\backend\.venv\Scripts\pip.exe" install -q -r "$RepoPath\backend\requirements.txt"
} -ArgumentList $RepoPath

Write-Host "Starting QVaultBackend on $ComputerName..." -ForegroundColor Cyan
Invoke-Command -ComputerName $ComputerName -Credential $Credential -ScriptBlock {
    param($TaskName)
    Start-ScheduledTask -TaskName $TaskName
} -ArgumentList $taskName

Write-Host "Waiting for backend to come back up..." -ForegroundColor Cyan
$healthy = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 3
    try {
        $resp = Invoke-WebRequest -Uri "http://${ComputerName}:${Port}/api/system/branding" -UseBasicParsing -TimeoutSec 5
        if ($resp.StatusCode -eq 200) { $healthy = $true; break }
    } catch {}
}

if ($healthy) {
    Write-Host "QVaultBackend on $ComputerName is back up and responding." -ForegroundColor Green
} else {
    Write-Warning "Backend did not respond within 60s -- check it manually: Invoke-Command -ComputerName $ComputerName -Credential `$cred { Get-ScheduledTask -TaskName $taskName }"
}
