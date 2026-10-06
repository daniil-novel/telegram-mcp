param(
    [string]$Python = 'python',
    [switch]$SkipPlugin
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$baseDir = Join-Path $env:LOCALAPPDATA 'TelegramReadOnlyMCP'
$runtimeDir = Join-Path $baseDir 'runtime'
$pythonExe = Join-Path $runtimeDir 'Scripts\python.exe'
$configDir = Join-Path $baseDir 'config'
$envFile = Join-Path $configDir '.env'

function Assert-LastExit([string]$Operation) {
    if ($LASTEXITCODE -ne 0) { throw "$Operation failed (exit $LASTEXITCODE)." }
}

if (-not (Test-Path -LiteralPath $pythonExe)) {
    & $Python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)"
    Assert-LastExit 'Python 3.11+ check'
    & $Python -m venv $runtimeDir
    Assert-LastExit 'Runtime creation'
}
& $pythonExe -m ensurepip --upgrade
Assert-LastExit 'pip bootstrap'
& $pythonExe -m pip install --require-hashes -r (Join-Path $repoRoot 'requirements.lock.txt')
Assert-LastExit 'Pinned dependency installation'

# Build first: a build/download failure must not remove an existing working server.
# Keep this small local wheel so an interrupted migration has an offline recovery path.
$stagingDir = Join-Path (Join-Path $baseDir 'install-staging') ([Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $stagingDir | Out-Null
& $pythonExe -m pip wheel --no-deps --wheel-dir $stagingDir $repoRoot
Assert-LastExit 'Telegram MCP wheel preparation'
$stagedWheels = @(Get-ChildItem -LiteralPath $stagingDir -Filter 'telegram_mcp-*.whl' -File)
if ($stagedWheels.Count -ne 1) { throw 'Expected exactly one prepared Telegram MCP wheel.' }
$wheelPath = $stagedWheels[0].FullName

# The old and new distributions own the SAME Python module and legacy entry point.
# Remove only the old distribution BEFORE installing the new one; retain dependencies.
# Distribution metadata does not import the MCP or read its configuration/session.
$legacyProbe = @'
import importlib.metadata as metadata
try:
    metadata.version("telegram-readonly-mcp")
except metadata.PackageNotFoundError:
    raise SystemExit(3)
'@
& $pythonExe -c $legacyProbe
$legacyStatus = $LASTEXITCODE
if ($legacyStatus -notin @(0, 3)) { throw 'Could not inspect legacy Telegram MCP package metadata.' }
try {
    if ($legacyStatus -eq 0) {
        & $pythonExe -m pip uninstall --yes telegram-readonly-mcp
        Assert-LastExit 'Legacy Telegram MCP package removal'
    }
    & $pythonExe -m pip install --no-deps --no-index $wheelPath
    Assert-LastExit 'Telegram MCP package installation'
} catch {
    Write-Warning 'The package upgrade did not finish. Dependencies and local configuration were retained.'
    Write-Warning 'If the old server was removed, reinstall the prepared wheel with this command:'
    Write-Host ('& "{0}" -m pip install --no-deps --no-index "{1}"' -f $pythonExe, $wheelPath)
    throw
}
New-Item -ItemType Directory -Force -Path $configDir | Out-Null
& $pythonExe -c "import sys; from pathlib import Path; from telegram_readonly_mcp.security import protect_path; [protect_path(Path(p)) for p in sys.argv[1:]]" $baseDir $configDir
Assert-LastExit 'Private directory permissions'
if (-not (Test-Path -LiteralPath $envFile)) {
    Copy-Item -LiteralPath (Join-Path $repoRoot '.env.example') -Destination $envFile
    & $pythonExe -m telegram_readonly_mcp --env-file $envFile protect-env
    Assert-LastExit 'Private configuration permissions'
}
# Existing .env files are never opened, rewritten or re-protected by this installer.

# Only file paths are global. Telegram secrets remain in the protected .env.
[Environment]::SetEnvironmentVariable('TELEGRAM_READONLY_MCP_HOME', $baseDir, 'User')
[Environment]::SetEnvironmentVariable('TELEGRAM_READONLY_MCP_ENV_FILE', $envFile, 'User')
[Environment]::SetEnvironmentVariable('TELEGRAM_READONLY_MCP_PYTHON', $pythonExe, 'User')
if (-not $SkipPlugin) {
    & codex plugin marketplace add $repoRoot
    Assert-LastExit 'Marketplace registration'
    & codex plugin add telegram-readonly-mcp@telegram-readonly-mcp
    Assert-LastExit 'Plugin installation'
}
Write-Host 'Installed. Existing configuration and Telegram session have been preserved.'
Write-Host 'Fill api_id/api_hash locally if missing, then run scripts/Authorize-Telegram.ps1.'
Write-Host 'Restart Codex and open a new chat after successful authorization.'
