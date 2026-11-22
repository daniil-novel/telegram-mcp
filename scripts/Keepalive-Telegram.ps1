param([ValidateSet('Check', 'Enable', 'Disable', 'Ready')][string]$Action = 'Check')
$ErrorActionPreference = 'Stop'
$baseDir = Join-Path $env:LOCALAPPDATA 'TelegramReadOnlyMCP'
$runtimeDir = Join-Path $baseDir 'runtime'
$pythonExe = Join-Path $runtimeDir 'Scripts\python.exe'
$envFile = Join-Path $baseDir 'config\.env'
$taskName = 'Telegram MCP - Session Check'
$installedScript = Join-Path $baseDir 'Keepalive-Telegram.ps1'

if ($Action -eq 'Disable') {
    Disable-ScheduledTask -TaskName $taskName -TaskPath '\' | Out-Null
    Write-Host 'Telegram MCP session checks disabled.'
    exit 0
}
if ($Action -eq 'Enable') {
    if (-not (Test-Path -LiteralPath $installedScript) -or -not (Test-Path -LiteralPath $pythonExe)) {
        throw 'Install the local Telegram MCP runtime first.'
    }
    $powershellExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $arguments = '-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}"' -f $installedScript
    $taskAction = New-ScheduledTaskAction -Execute $powershellExe -Argument $arguments
    $trigger = New-ScheduledTaskTrigger -Daily -At ([DateTime]::Today.AddHours(13))
    $principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 1)
    Register-ScheduledTask -TaskName $taskName -TaskPath '\' -Action $taskAction -Trigger $trigger -Principal $principal -Settings $settings -Description 'Check the current Windows user Telegram MCP session once per day, without accessing chats.' -Force | Out-Null
    Write-Host 'Telegram MCP session check enabled daily at 13:00 local time.'
    exit 0
}

# Clients started before this version may still be connected without the new session lock.
# Skip until those workers have exited. Never echo their command lines.
$probeModule = Join-Path $runtimeDir 'Lib\site-packages\telegram_readonly_mcp\session_health.py'
if (-not (Test-Path -LiteralPath $probeModule -PathType Leaf)) { exit 1 }
$installedAt = (Get-Item -LiteralPath $probeModule).LastWriteTimeUtc
$oldClient = Get-CimInstance -ClassName Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe' OR Name = 'telegram-mcp.exe' OR Name = 'telegram-readonly-mcp.exe'" |
    Where-Object {
        $_.CreationDate.ToUniversalTime() -lt $installedAt -and
        $_.CommandLine -match '(?i)(-m\s+telegram_readonly_mcp(?:\s|$)|telegram(?:-readonly)?-mcp\.exe)' -and
        $_.CommandLine -match '(?i)(?:^|\s)(?:serve|auth)(?:\s|$)'
    } | Select-Object -First 1
if ($oldClient) {
    if ($Action -ne 'Ready') { Write-Host 'Close the old Telegram login window and restart old Telegram MCP clients.' }
    exit 5
}
if ($Action -eq 'Ready') { exit 0 }
& $pythonExe -m telegram_readonly_mcp --env-file $envFile session-check --lang ru
exit $LASTEXITCODE
