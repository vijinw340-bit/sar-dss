<#
.SYNOPSIS
Bootstrap the SAR-DSS VPN script suite.

.DESCRIPTION
Downloads the OpenVPN profile collection (Zoult/.ovpn - FreeVPN4You free
servers, ~20 countries / ~268 profiles) into scripts/configs and optionally
installs the OpenVPN Community client so the openvpn backend can run.

Run with -SkipInstall to skip the OpenVPN binary install (e.g. when using
the docker backend only).

.USAGE
    .\vpn-init.ps1                 # fetch configs + install OpenVPN
    .\vpn-init.ps1 -SkipInstall    # fetch configs only
    .\vpn-init.ps1 -Repo git@github.com:you/your-ovpn      # your own profile repo
#>
param(
    [string]$Repo     = "https://github.com/Zoult/.ovpn",
    [string]$Dest     = (Join-Path $PSScriptRoot "configs"),
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$msg) { Write-Host "[vpn-init] $msg" -ForegroundColor Cyan }

# ---------------------------------------------------------------- configs ---
if (Test-Path -LiteralPath $Dest) {
    $count = (Get-ChildItem -LiteralPath $Dest -Recurse -Filter *.ovpn -File -ErrorAction SilentlyContinue | Measure-Object).Count
    if ($count -gt 0) {
        Write-Step "configs already present: $count profiles -> $Dest"
        if (-not $SkipInstall) { & (Join-Path $PSScriptRoot "vpn-init.ps1") @($MyInvocation.BoundParameters.WasChanged) -SkipInstall }
    }
}

if (-not (Test-Path -LiteralPath $Dest) -or (Get-ChildItem -LiteralPath $Dest -Recurse -Filter *.ovpn -File -ErrorAction SilentlyContinue | Measure-Object).Count -eq 0) {
    git --version | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "git is required to fetch the profile repo." }
    $tmp = Join-Path $env:TEMP "sar-vpn-profiles"
    if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Recurse -Force }
    Write-Step "cloning $Repo ..."
    git clone --depth 1 $Repo $tmp 2>$null
    if ($LASTEXITCODE -ne 0) { throw "clone of $Repo failed." }
    New-Item -ItemType Directory -Path $Dest -Force | Out-Null
    Get-ChildItem -LiteralPath $tmp -Directory | Copy-Item -Destination $Dest -Recurse -Force
    Remove-Item -LiteralPath $tmp -Recurse -Force
    $count = (Get-ChildItem -LiteralPath $Dest -Recurse -Filter *.ovpn -File | Measure-Object).Count
    Write-Step "fetched $count profiles into $Dest"
    foreach ($d in Get-ChildItem -LiteralPath $Dest -Directory | Sort-Object Name) {
        Write-Host ("  {0,-14} {1} profile(s)" -f $d.Name, (Get-ChildItem -LiteralPath $d.FullName -Filter *.ovpn -File).Count)
    }
}

# ------------------------------------------------------- OpenVPN install -----
if ($SkipInstall) {
    Write-Step "skipping OpenVPN client install (-SkipInstall)"
    return
}

if ($IsWindows -or $env:OS -eq "Windows_NT") {
    $openvpn = Get-Command openvpn -ErrorAction SilentlyContinue
    if (-not $openvpn) {
        if (Get-Command choco -ErrorAction SilentlyContinue) {
            Write-Step "installing OpenVPN via chocolatey (silent)..."
            choco install openvpn -y --params '"/SELECT_OPENVPN_GUI=0"' | Out-Host
        }
        elseif (Get-Command winget -ErrorAction SilentlyContinue) {
            Write-Step "installing OpenVPN via winget (silent)..."
            winget install --id OpenVPNTechnologies.OpenVPN -e --accept-package-agreements --accept-source-agreements | Out-Host
        }
        else {
            Write-Host "[warn] no choco/winget found - install OpenVPN manually from https://openvpn.net/community-downloads" -ForegroundColor Yellow
        }
    }
    else {
        Write-Step "OpenVPN already available: $($openvpn.Source)"
    }
} else {
    # Linux/macOS runners
    if (Get-Command openvpn -ErrorAction SilentlyContinue) {
        Write-Step "OpenVPN already available on PATH"
    } else {
        Write-Host "[warn] openvpn binary missing - apt/yum/brew install it, or use the docker backend" -ForegroundColor Yellow
    }
}

# ------------------------------------------------------------------ auth -----
$auth = Join-Path $PSScriptRoot "secrets\vpn.auth"
if (-not (Test-Path -LiteralPath $auth)) {
    $authDir = Split-Path $auth
    if (-not (Test-Path -LiteralPath $authDir)) { New-Item -ItemType Directory -Path $authDir -Force | Out-Null }
    if (Test-Path -LiteralPath "$auth.example") {
        Copy-Item "$auth.example" $auth -Force
        Write-Step "created $auth from template (edit with your OpenVPN credentials)"
    }
}
Write-Host "[vpn-init] done. Next:  .\vpn.ps1 countries   then   .\vpn.ps1 connect -Country India -Backend openvpn" -ForegroundColor Green