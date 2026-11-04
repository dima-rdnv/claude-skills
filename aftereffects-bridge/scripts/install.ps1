<#  Installs the Claude Bridge CEP panel for After Effects, for the current user only.
    1. Self-signs ..\panel with ZXPSignCmd.exe from $SigningDir (Adobe-CEP/CEP-Resources,
       ZXPSignCMD/4.1.3/x64). CEP 12 refuses unsigned panels. The certificate and its password are
       created in $SigningDir on first use and stay there; never share them.
    2. Copies the signed panel to %APPDATA%\Adobe\CEP\extensions\com.claude.aebridge, and with
       -ShareTo also to that folder (the copy colleagues install: signed, so they need no signing tools).
    3. Removes the old ScriptUI panel (ClaudeBridge.jsx in any AE version's ScriptUI Panels folder),
       so two bridges never serve the same inbox.
    Then restart After Effects (it finds new extensions only at start-up) and open
    Window > Extensions > Claude Bridge. Re-run after editing the panel: an edited file breaks the
    signature. A new host.jsx loads when the panel is closed and reopened.
#>
param(
    [string]$SigningDir = "D:\WORK\Claude\premiere-bridge-signing",
    [string]$ShareTo = ""   # not "$Out": PowerShell names ignore case, and $out holds tool output below
)
$ErrorActionPreference = "Stop"

$src = Join-Path $PSScriptRoot "..\panel"
$dst = Join-Path $env:APPDATA "Adobe\CEP\extensions\com.claude.aebridge"

function Mirror($from, $to) {
    robocopy $from $to /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy $from -> $to failed with exit code $LASTEXITCODE" }
}

$zxpSign = Join-Path $SigningDir "ZXPSignCmd.exe"
if (-not (Test-Path $zxpSign)) { throw "No ZXPSignCmd.exe in $SigningDir; After Effects refuses unsigned CEP panels." }
$cert = Join-Path $SigningDir "claude-bridge.p12"
$pwFile = Join-Path $SigningDir "claude-bridge.p12.password"
if (-not (Test-Path $cert)) {
    Set-Content -Path $pwFile -Value ([guid]::NewGuid().ToString("N")) -NoNewline -Encoding ASCII
    $out = & $zxpSign -selfSignedCert US NA "Claude Bridge" "Claude Bridge local signing" (Get-Content $pwFile -Raw) $cert -validityDays 3650
    if ($LASTEXITCODE -ne 0) { throw "ZXPSignCmd -selfSignedCert failed: $out" }
    "Created self-signed certificate $cert"
}
$stage = Join-Path $SigningDir "stage-ae"
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Path $stage | Out-Null
Mirror $src "$stage\panel"
$out = & $zxpSign -sign "$stage\panel" "$stage\panel.zxp" $cert (Get-Content $pwFile -Raw)
if ($LASTEXITCODE -ne 0) { throw "ZXPSignCmd -sign failed: $out" }
# a .zxp is a zip; Expand-Archive only accepts the .zip extension
Copy-Item "$stage\panel.zxp" "$stage\panel.zip"
Expand-Archive -Path "$stage\panel.zip" -DestinationPath "$stage\signed"
Mirror "$stage\signed" $dst
$out = & $zxpSign -verify $dst
"Signed panel installed to $dst ($out)"
if ($ShareTo) { Mirror "$stage\signed" $ShareTo; "Signed copy for sharing: $ShareTo" }

Get-ChildItem (Join-Path $env:APPDATA "Adobe\After Effects\*\Scripts\ScriptUI Panels\ClaudeBridge.jsx") -ErrorAction SilentlyContinue |
    ForEach-Object { Remove-Item $_.FullName; "Removed old ScriptUI panel $($_.FullName)" }
exit 0
