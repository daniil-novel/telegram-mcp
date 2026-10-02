param([switch]$NoPause)
$ErrorActionPreference = 'Stop'
$baseDir = Join-Path $env:LOCALAPPDATA 'TelegramReadOnlyMCP'
$pythonExe = Join-Path $baseDir 'runtime\Scripts\python.exe'
$envFile = Join-Path $baseDir 'config\.env'
$statusFile = Join-Path $baseDir 'auth-status.json'
$exitStatus = 1
try {
    $Host.UI.RawUI.WindowTitle = 'Telegram Read-only - local authorization'
    if (-not (Test-Path -LiteralPath $pythonExe) -or -not (Test-Path -LiteralPath $envFile)) {
        throw 'The local Telegram runtime or configuration is missing.'
    }
    @{ status = 'waiting_for_user'; started_at = (Get-Date).ToUniversalTime().ToString('o') } |
        ConvertTo-Json | Set-Content -LiteralPath $statusFile -Encoding UTF8
    Write-Host 'Enter your phone, Telegram code and 2FA password here. Input is hidden.'
    Write-Host 'These values are not sent to Codex. No messages will be read during login.'
    & $pythonExe -m telegram_readonly_mcp --env-file $envFile auth
    $exitStatus = $LASTEXITCODE
    $authState = if ($exitStatus -eq 0) { 'authorized' } else { 'authorization_failed' }
    @{ status = $authState; exit_code = $exitStatus; completed_at = (Get-Date).ToUniversalTime().ToString('o') } |
        ConvertTo-Json | Set-Content -LiteralPath $statusFile -Encoding UTF8
    if ($exitStatus -eq 0) {
        Write-Host 'Done. You can restart Codex and open a new chat.' -ForegroundColor Green
    } else {
        Write-Host 'Authorization did not complete. Run this script again to retry.' -ForegroundColor Yellow
    }
} catch {
    Write-Host 'Local authorization could not start. Check the runtime and file permissions.' -ForegroundColor Red
} finally {
    if (-not $NoPause) { [void](Read-Host 'Press Enter to close this window') }
}
exit $exitStatus
