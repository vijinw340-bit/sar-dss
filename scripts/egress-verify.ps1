<#
.SYNOPSIS
Check which public IP this machine is currently exiting from, and optionally
watch for changes (e.g. a VPN drop or a rotating tunnel).

.DESCRIPTION
Creative verification helpers:
  - queries several independent IP echo services so one blocked endpoint
    doesn't fool you
  - -Before <ip> compares against an earlier value (classic "did the VPN
    actually take effect?" check)
  - -Loop watches the egress and notifies on change (useful to confirm
    rotate / random modes in the SAR-DSS .env are rotating your exit)

.USAGE
    .\egress-verify.ps1                      # show current egress IP
    .\egress-verify.ps1 -Before 1.2.3.4     # did the exit change?
    .\egress-verify.ps1 -Loop -Interval 20  # watch for egress rotation
    .\egress-verify.ps1 -Raw                # machine-readable JSON
#>
param(
    [string]$Before,
    [switch]$Loop,
    [int]$Interval = 20,
    [switch]$Raw
)

$ErrorActionPreference = "Stop"

function Get-Ips {
    $endpoints = @(
        "https://api.ipify.org?format=json",
        "https://api.seeip.org/jsonip",
        "https://ipapi.co/json/",
        "http://ip-api.com/json/"
    )
    $out = @()
    foreach ($ep in $endpoints) {
        try {
            $r = Invoke-RestMethod -Uri $ep -TimeoutSec 6
            if ($r.ip)      { $out += [string]$r.ip }
            elseif ($r.query) { $out += [string]$r.query }
        } catch { }
    }
    $out | Select-Object -Unique
}

function Test-Current {
    $ips = Get-Ips
    if (-not $ips) { return $null }
    # prefer the majority vote
    $ip = $ips | Group-Object | Sort-Object Count -Descending | Select-Object -First 1 -ExpandProperty Name
    [pscustomobject]@{ ip = $ip; all = $ips }
}

if ($Raw) {
    $c = Test-Current
    $out = [ordered]@{
        ip       = $c.ip
        sources  = @($c.all)
        before   = $Before
        changed  = if ($Before) { $Before -ne $c.ip } else { $null }
        ts       = (Get-Date).ToString("o")
    }
    $out | ConvertTo-Json
    exit
}

if ($Loop) {
    Write-Host "[egress-verify] watching every ${Interval}s (Ctrl-C to stop)..." -ForegroundColor Cyan
    $previous = $null
    while ($true) {
        $c = Test-Current
        if (-not $c) { Write-Host "[egress-verify] no reachable IP echo — network/VPN down?" -ForegroundColor Red }
        elseif (-not $previous) { Write-Host ("[egress-verify] exit = {0}  ({1})" -f $c.ip, ($c.all -join ", ")) -ForegroundColor Green }
        elseif ($c.ip -ne $previous) { Write-Host ("[egress-verify] EXIT CHANGED: {0} -> {1}" -f $previous, $c.ip) -ForegroundColor Yellow }
        $previous = if ($c) { $c.ip } else { $previous }
        Start-Sleep -Seconds $Interval
    }
}

$c = Test-Current
if (-not $c) {
    Write-Host "[egress-verify] FAILED - could not reach any IP echo service (no internet / VPN down)." -ForegroundColor Red
    exit 1
}
Write-Host ("[egress-verify] exit IP = {0}" -f $c.ip) -ForegroundColor Green
if ($c.all.Count -gt 1) {
    Write-Host ("[egress-verify] sources   = {0}" -f ($c.all -join ", ")) -ForegroundColor DarkGray
}
if ($Before) {
    if ($c.ip -ne $Before) {
        Write-Host ("[egress-verify] CHANGED: {0} -> {1}  (tunnel is routing you elsewhere)" -f $Before, $c.ip) -ForegroundColor Yellow
    } else {
        Write-Host "[egress-verify] unchanged - you are still on $($c.ip). Tunnel may not be up." -ForegroundColor Yellow
    }
}