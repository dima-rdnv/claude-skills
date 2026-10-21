<#  Installs the Claude Bridge CEP panel for Premiere Pro, for the current user only.
    1. Sets HKCU\Software\Adobe\CSXS.<n>\PlayerDebugMode = "1". This lets every unsigned CEP panel
       load in every Adobe app using that CEP version.
    2. If $SigningDir holds ZXPSignCmd.exe (Adobe-CEP/CEP-Resources, ZXPSignCMD/4.1.3/x64), self-signs
       the panel. Premiere 26.5 (CEP 12.0.1) ignores PlayerDebugMode and logs "Signature verification
       failed" for unsigned panels. The certificate and its password are created in $SigningDir on
       first use and stay there.
    3. Copies the (signed) panel to %APPDATA%\Adobe\CEP\extensions\com.claude.premierebridge.
    Then restart Premiere and open Window > Extensions > Claude Bridge.
    Re-run after editing the panel: any edited file invalidates the signature. A changed host.jsx then
    only needs the panel's "Reload host"; index.html needs the panel closed and reopened.
    Premiere 2024-2026 use CEP 12 (CSXS.12); pass -CsxsVersions for older versions.
#>
param(
    [string[]]$CsxsVersions = @("12"),
    [string]$SigningDir = "D:\WORK\Claude\premiere-bridge-signing"
)
$ErrorActionPreference = "Stop"

$src = Join-Path $PSScriptRoot "..\panel"
$dst = Join-Path $env:APPDATA "Adobe\CEP\extensions\com.claude.premierebridge"

function Mirror($from, $to) {
    robocopy $from $to /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy $from -> $to failed with exit code $LASTEXITCODE" }
}

foreach ($v in $CsxsVersions) {
    $key = "HKCU:\Software\Adobe\CSXS.$v"
    # never New-Item -Force here: on an existing registry key it wipes the key's other values
    if (-not (Test-Path $key)) { New-Item -Path $key | Out-Null }
    Set-ItemProperty -Path $key -Name PlayerDebugMode -Value "1" -Type String
    "PlayerDebugMode = 1 under CSXS.$v"
}

$zxpSign = Join-Path $SigningDir "ZXPSignCmd.exe"
if (Test-Path $zxpSign) {
    $cert = Join-Path $SigningDir "claude-bridge.p12"
    $pwFile = Join-Path $SigningDir "claude-bridge.p12.password"
    if (-not (Test-Path $cert)) {
        Set-Content -Path $pwFile -Value ([guid]::NewGuid().ToString("N")) -NoNewline -Encoding ASCII
        $out = & $zxpSign -selfSignedCert US NA "Claude Bridge" "Claude Bridge local signing" (Get-Content $pwFile -Raw) $cert -validityDays 3650
        if ($LASTEXITCODE -ne 0) { throw "ZXPSignCmd -selfSignedCert failed: $out" }
        "Created self-signed certificate $cert"
    }
    $stage = Join-Path $SigningDir "stage"
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
} else {
    Mirror $src $dst
    Write-Warning "No ZXPSignCmd.exe in $SigningDir, so the panel is unsigned. Premiere 26.5 refuses unsigned panels."
    "Panel installed to $dst"
}
exit 0
