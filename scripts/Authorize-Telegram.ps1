param(
    [ValidateSet('menu', 'qr', 'code')][string]$Method = 'menu',
    [ValidateSet('ru', 'en')][string]$Language = 'ru',
    [switch]$NoPause
)
$ErrorActionPreference = 'Stop'
$baseDir = Join-Path $env:LOCALAPPDATA 'TelegramReadOnlyMCP'
$pythonExe = Join-Path $baseDir 'runtime\Scripts\python.exe'
$envFile = Join-Path $baseDir 'config\.env'
$statusFile = Join-Path $baseDir 'auth-status.json'
$keepaliveScript = Join-Path $baseDir 'Keepalive-Telegram.ps1'
$exitStatus = 1
$preflightMessage = $null

function Message([string]$English, [string]$Russian) {
    if ($Language -eq 'ru') { return $Russian }
    return $English
}

try {
    $Host.UI.RawUI.WindowTitle = Message 'Sign in to Telegram MCP' 'Вход в Telegram MCP'
    if (-not (Test-Path -LiteralPath $pythonExe) -or -not (Test-Path -LiteralPath $envFile)) {
        $preflightMessage = Message 'Local Telegram MCP setup is missing.' 'Не найдена локальная настройка Telegram MCP.'
        throw 'Failed preflight'
    }
    & $keepaliveScript -Action Ready
    if ($LASTEXITCODE -eq 5) {
        $preflightMessage = Message 'Close the previous login and restart old Codex windows before retrying.' 'Закрой старое окно входа через Ctrl+C и перезапусти Codex. Затем открой «Войти в Telegram» снова.'
        throw 'Failed preflight'
    }
    if ($LASTEXITCODE -ne 0) {
        $preflightMessage = Message 'Could not check the local Telegram runtime.' 'Не удалось проверить локальную установку Telegram MCP.'
        throw 'Failed preflight'
    }
    @{ status = 'waiting_for_user'; started_at = (Get-Date).ToUniversalTime().ToString('o') } |
        ConvertTo-Json | Set-Content -LiteralPath $statusFile -Encoding UTF8
    Write-Host (Message 'Checking the saved Telegram session…' 'Проверяю сохранённую сессию Telegram…')
    & $pythonExe -m telegram_readonly_mcp --env-file $envFile auth --remember-phone --method $Method --lang $Language
    $exitStatus = $LASTEXITCODE
    $authState = if ($exitStatus -eq 0) { 'authorized' } else { 'authorization_failed' }
    @{ status = $authState; exit_code = $exitStatus; completed_at = (Get-Date).ToUniversalTime().ToString('o') } |
        ConvertTo-Json | Set-Content -LiteralPath $statusFile -Encoding UTF8
    if ($exitStatus -eq 0) {
        Write-Host (Message 'You can use Telegram MCP in Codex.' 'Теперь можно использовать Telegram MCP в Codex.') -ForegroundColor Green
    } else {
        Write-Host (Message 'Sign-in did not finish. Open this launcher again to retry.' 'Вход не завершён. Открой «Войти в Telegram» снова, чтобы повторить.') -ForegroundColor Yellow
    }
} catch {
    if (-not $preflightMessage) {
        $preflightMessage = Message 'Sign-in could not start. Check the local setup.' 'Не удалось начать вход. Проверь локальную установку.'
    }
    Write-Host $preflightMessage -ForegroundColor Red
} finally {
    if (-not $NoPause) { [void](Read-Host (Message 'Press Enter to close this window' 'Нажми Enter, чтобы закрыть окно')) }
}
exit $exitStatus
