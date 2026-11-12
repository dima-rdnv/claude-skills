# Cinema 4D MCP - Windows setup for Claude Desktop
# Run in PowerShell:
#   powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\Documents\Maxon\cinema4d-mcp\install-windows.ps1"
#
# 1. copies the socket-server plugin into every Cinema 4D 2026 prefs\plugins folder
# 2. installs uv if missing, builds the server env in %LOCALAPPDATA%\cinema4d-mcp\.venv
#    with mcp pinned below 2 (mcp 2.x removed FastMCP, which this server needs)
# 3. waits for you to quit Claude Desktop, backs up claude_desktop_config.json,
#    adds the "cinema4d" MCP server, and reopens Claude
# Log: install.log next to this script.

$ErrorActionPreference = 'Stop'
$root   = $PSScriptRoot
$venv   = Join-Path $env:LOCALAPPDATA 'cinema4d-mcp\.venv'
$py     = Join-Path $venv 'Scripts\python.exe'
$helper = Join-Path $root '_claude_setup.py'
$log    = Join-Path $root 'install.log'

Set-Content -Path $log -Value ("Cinema 4D MCP install " + (Get-Date -Format s)) -Encoding UTF8
function Log([string]$m) { Write-Host $m; Add-Content -Path $log -Value $m -Encoding UTF8 }
function Run([string]$exe, [string[]]$argv) {
    $old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    & $exe @argv 2>&1 | ForEach-Object { Log ("  " + "$_") }
    $code = $LASTEXITCODE
    $ErrorActionPreference = $old
    if ($code -ne 0) { throw "failed (exit $code): $exe $($argv -join ' ')" }
}

try {
    Log "Server folder: $root"

    # 1) C4D plugin
    $pyp = Join-Path $root 'c4d_plugin\mcp_server_plugin.pyp'
    $prefs = Get-ChildItem (Join-Path $env:APPDATA 'Maxon') -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '^Maxon Cinema 4D 2026_[0-9A-F]{8}$' }
    if (-not $prefs) { throw "No Cinema 4D 2026 prefs folder in $env:APPDATA\Maxon - start Cinema 4D 2026 once, then rerun." }
    foreach ($p in $prefs) {
        $dst = Join-Path $p.FullName 'plugins'
        New-Item -ItemType Directory -Force -Path $dst | Out-Null
        Copy-Item -Path $pyp -Destination $dst -Force
        Log "[1/4] plugin -> $dst"
    }

    # 2) uv
    $uv = $null
    $cmd = Get-Command uv -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cmd) { $uv = $cmd.Source }
    if (-not $uv) {
        $cand = Join-Path $env:USERPROFILE '.local\bin\uv.exe'
        if (Test-Path $cand) { $uv = $cand }
    }
    if (-not $uv) {
        Log "[2/4] uv not found - installing it from astral.sh ..."
        Run 'powershell' @('-NoProfile', '-ExecutionPolicy', 'ByPass', '-Command', 'irm https://astral.sh/uv/install.ps1 | iex')
        $uv = Join-Path $env:USERPROFILE '.local\bin\uv.exe'
        if (-not (Test-Path $uv)) { throw "uv install finished but $uv is missing" }
    }
    Log "[2/4] uv: $uv"

    # 3) Python env (deps only; main.py puts src\ on sys.path itself)
    Log "[3/4] Building the server env in $venv ..."
    $env:UV_NO_PROGRESS = '1'
    if (-not (Test-Path $py)) { Run $uv @('venv', '--python', '3.12', $venv) }
    Run $uv @('pip', 'install', '--python', $py, 'mcp>=1.2,<2', 'starlette')
    Run $py @($helper, 'check')

    # 4) Claude Desktop config - edit only while Claude is closed (it rewrites the file on quit)
    $cands = @()
    Get-ChildItem (Join-Path $env:LOCALAPPDATA 'Packages') -Directory -Filter 'Claude_*' -ErrorAction SilentlyContinue |
        ForEach-Object { $cands += (Join-Path $_.FullName 'LocalCache\Roaming\Claude\claude_desktop_config.json') }
    $cands += (Join-Path $env:APPDATA 'Claude\claude_desktop_config.json')
    $cfg = $cands | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $cfg) { $cfg = $cands[-1] }
    Log "[4/4] Claude config: $cfg"

    function Get-ClaudeDesktop {
        Get-Process -Name 'claude' -ErrorAction SilentlyContinue | Where-Object {
            $p = $null; try { $p = $_.Path } catch {}
            -not ($p -and ($p -like "$env:USERPROFILE\.local\*"))   # ignore the Claude Code CLI
        }
    }
    if (Get-ClaudeDesktop) {
        Write-Host ""
        Write-Host ">>> Now QUIT Claude Desktop: tray icon (bottom-right) > Quit. Closing the window is not enough." -ForegroundColor Yellow
        Write-Host ">>> This window waits, adds the Cinema 4D server, then reopens Claude." -ForegroundColor Yellow
        $deadline = (Get-Date).AddMinutes(20)
        while (Get-ClaudeDesktop) {
            if ((Get-Date) -gt $deadline) { throw "Timed out waiting for Claude to quit - run the script again." }
            Start-Sleep -Seconds 2
        }
        Start-Sleep -Seconds 3
        Log "Claude has quit."
    }
    Run $py @($helper, 'config', $cfg)

    $app = Get-StartApps | Where-Object { $_.Name -eq 'Claude' } | Select-Object -First 1
    if ($app) {
        Start-Process "shell:AppsFolder\$($app.AppID)"
        Log "Reopened Claude."
    } else {
        Log "Open Claude again from the Start menu."
    }

    Log ""
    Log "DONE. Restart Cinema 4D 2026, then Extensions > Socket Server Plugin > Start Server (localhost:5555)."
} catch {
    Log ("ERROR: " + $_.Exception.Message)
    Write-Host "Setup stopped - see $log" -ForegroundColor Red
}
Read-Host "Press Enter to close"
