# Remote scraper node — setup & update

Runs a second QVault backend on another PC (pointed at the same remote SQL
Server) purely to spread scraping CPU load. Controlled entirely from your
dev PC after one-time setup — no need to log into the new PC for routine
updates.

## One-time setup (on the NEW PC)

1. Install prerequisites: Python 3.11+, Git, FFmpeg on PATH (same as the
   dev PC — see the root `CLAUDE.md`).
2. Clone the repo (default expected path: `E:\QVault`):
   ```powershell
   git clone <repo-url> E:\QVault
   cd E:\QVault\backend
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   ```
3. Copy `config/.env` from your dev PC (same DB credentials — it points at
   the shared remote SQL Server, so this node writes into the same database
   your dev PC's frontend already reads from).
4. In an **Administrator** PowerShell window, from the repo root:
   ```powershell
   .\deploy\setup_new_pc.ps1
   ```
   This enables PowerShell Remoting (WinRM), registers the backend as a
   Scheduled Task that starts at boot (survives logoff, auto-restarts up to
   3 times if it crashes), and starts it immediately.

## Routine updates (from your DEV PC, any time after)

```powershell
cd E:\QVault\deploy
.\remote_update.ps1 -ComputerName <new-pc-ip>
```

This stops the remote backend, `git pull`s + reinstalls Python deps on the
remote machine, restarts it, and confirms it's responding again — all
without touching the new PC directly.

If the two PCs aren't on the same Windows domain, run this **once** on your
dev PC first so it trusts the new PC for remoting:
```powershell
Set-Item WSMan:\localhost\Client\TrustedHosts -Value "<new-pc-ip>" -Concatenate -Force
Test-WSMan <new-pc-ip>
```

## Using the second node

There's no frontend running there — trigger scans directly against its API
(e.g. `POST http://<new-pc-ip>:8005/api/sources/gk-scraper/scan`) with a
site you're not already scanning from the dev PC, so the two nodes split
different sites rather than racing each other on the same one. Both write
into the same shared database, so the Sites Report grid on your dev PC's
frontend shows combined results from both machines automatically.
