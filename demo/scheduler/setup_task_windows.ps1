# setup_task_windows.ps1 — Install a Windows Task Scheduler task for daily trading.
# Run as Administrator in PowerShell from repo root:
#   .\demo\scheduler\setup_task_windows.ps1

$DemoDir = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
$RepoRoot = Split-Path -Parent $DemoDir
$PythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$RunScript = Join-Path $DemoDir "scripts\run_daily.py"
$LogDir = Join-Path $DemoDir "logs"
$LogFile = Join-Path $LogDir "task_daily.log"

if (-not (Test-Path $PythonExe)) {
    $PythonExe = (Get-Command python).Source
    Write-Warning "Could not find .venv\Scripts\python.exe, using: $PythonExe"
}

# Create log directory
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }

$TaskName = "TradingAgentsDemo"
$Action = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument $RunScript `
    -WorkingDirectory $DemoDir

# Trigger: weekdays at 09:31 AM
$Trigger = New-ScheduledTaskTrigger `
    -Weekly `
    -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday `
    -At "09:31AM"

$Settings = New-ScheduledTaskSettingsSet `
    -RunOnlyIfNetworkAvailable `
    -StartWhenAvailable

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -RunLevel Highest `
    -Force | Out-Null

Write-Host "Task '$TaskName' registered successfully."
Write-Host "It will run at 09:31 AM on weekdays."
Write-Host "Verify with: Get-ScheduledTask -TaskName '$TaskName'"
