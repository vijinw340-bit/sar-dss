<#
.SYNOPSIS
SAR-DSS "connect a VPN via script" — multiple creative ways to get an exit node.

.DESCRIPTION
One CLI for several ways of establishing a VPN / tunnel exit for this
machine — and, when the exit is a SOCKS ball, for feeding it straight into the
SAR-DSS server via OUTBOUND_PROXIES.

Backends
    openvpn   run an OpenVPN profile (from scripts/configs) in the background
    docker    run the profile inside a dperson/openvpn-client container
    ssh       "poor man's VPN": a local `ssh -N -D` dynamic SOCKS tunnel
    ras       Windows-native VPN entry (SSTP/L2TP/IKEv2 - for servers that
              speak those protocols, NOT OpenVPN configs)

Creative extras
    -Roulette    pick a random server/profile in the chosen country
    -Fastest     latency-test candidate endpoints, connect to the quickest
    -Protocol    restrict to tcp / udp profiles
    -AutoReconnect  watchdog that reconnects on tunnel loss (-MaxReconnects)
    -KillSwitch  create a Windows Firewall "block everything unless it's the
                 VPN / DNS" set of rules (removed automatically on disconnect)
    -SplitTunnel keep a direct route to your LAN while tunnelling the rest

.USAGE
    .\vpn-init.ps1                                     # fetch profiles once
    .\vpn.ps1 countries
    .\vpn.ps1 list
    .\vpn.ps1 connect -Country India                   # openvpn backend
    .\vpn.ps1 connect -Country Germany -Roulette -Fastest
    .\vpn.ps1 connect -Backend ssh -JumpUser me -JumpHost gw.example -JumpKey ~\.ssh\id_ed25519
    .\vpn.ps1 connect -Backend docker -Country Italy -Protocol udp
    .\vpn.ps1 status
    .\vpn.ps1 ip
    .\vpn.ps1 export -SocksPort 1080                   # wire SAR-DSS to this tunnel
    .\vpn.ps1 disconnect
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("list", "countries", "connect", "disconnect", "status", "ip", "export", "help")]
    [string]$Action = "help",

    # --- connect ---
    [string]$Country,
    [ValidateSet("openvpn", "docker", "ssh", "ras")]
    [string]$Backend = "openvpn",
    [ValidateSet("tcp", "udp", "any")]
    [string]$Protocol = "any",
    [string]$Profile,
    [switch]$Roulette,
    [switch]$Fastest,
    [string]$AuthFile,
    [switch]$SplitTunnel,
    [switch]$KillSwitch,
    [switch]$AutoReconnect,
    [int]$MaxReconnects = 5,
    [int]$ReconnectDelay = 10,

    # --- ssh backend ---
    [string]$JumpUser,
    [string]$JumpHost,
    [int]$JumpPort = 22,
    [string]$JumpKey,
    [int]$SocksPort,

    # --- ras backend ---
    [string]$VpnName = "SAR-DSS",
    [ValidateSet("SSTP", "L2TP", "IKEv2", "PPTP")]
    [string]$TunnelType = "SSTP",

    # --- export ---
    [hashtable]$Socks
)

$ErrorActionPreference = "Stop"
$script:Root     = Split-Path $PSScriptRoot -Parent
$script:Scripts  = $PSScriptRoot
$script:Configs  = Join-Path $PSScriptRoot "configs"
$script:Secrets  = Join-Path $PSScriptRoot "secrets"
$script:State    = Join-Path $PSScriptRoot ".vpn-state.json"
$script:Logs     = Join-Path $PSScriptRoot "logs"

function Write-Step([string]$msg) { Write-Host "[vpn] $msg" -ForegroundColor Cyan }
function Write-Ok([string]$msg)   { Write-Host "[vpn] $msg" -ForegroundColor Green }
function Write-Warn([string]$msg) { Write-Host "[vpn] $msg" -ForegroundColor Yellow }
function Write-Fail([string]$msg) { Write-Host "[vpn] $msg" -ForegroundColor Red }

function Get-State {
    if (Test-Path -LiteralPath $script:State) {
        try { return (Get-Content -LiteralPath $script:State -Raw | ConvertFrom-Json) } catch { return $null }
    }
    return $null
}
function Save-State([hashtable]$table) {
    $table | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $script:State -Encoding UTF8
}
function Clear-State { if (Test-Path -LiteralPath $script:State) { Remove-Item -LiteralPath $script:State -Force } }

# ------------------------------------------------------------ public ip ----
function Get-PublicIp {
    $endpoints = @(
        "https://api.ipify.org?format=json",
        "https://ipapi.co/json/",
        "https://api.seeip.org/jsonip"
    )
    foreach ($ep in $endpoints) {
        try {
            $r = Invoke-RestMethod -Uri $ep -TimeoutSec 6
            if ($r.ip) { return [string]$r.ip }
            if ($r.query) { return [string]$r.query }
        } catch { }
    }
    throw "could not determine public IP (no network?)"
}
function Show-Ip {
    $ip = Get-PublicIp
    Write-Host "[vpn] public egress IP:  $ip" -ForegroundColor Green
    try {
        $geo = Invoke-RestMethod -Uri "http://ip-api.com/json/$ip" -TimeoutSec 6
        Write-Host "[vpn] geo:               $($geo.city), $($geo.countryCode) — ISP: $($geo.isp)" -ForegroundColor Green
    } catch { }
}

# ------------------------------------------------------------- profiles -----
function Get-Countries {
    if (-not (Test-Path -LiteralPath $script:Configs)) {
        throw "no configs directory. Run .\vpn-init.ps1 first."
    }
    Get-ChildItem -LiteralPath $script:Configs -Directory | Sort-Object Name
}
function Get-ProfileFiles([string]$country, [string]$proto = "any") {
    $dirs = Get-Countries
    if ($country) {
        $dir = $dirs | Where-Object { $_.Name -match $country }
        if (-not $dir) { throw "no country matching '$country'. Try: .\vpn.ps1 countries" }
        $dirs = @($dir)
    } else {
        $dirs = @($dirs)
    }
    $files = foreach ($d in $dirs) { Get-ChildItem -LiteralPath $d.FullName -Filter *.ovpn -File }
    if ($proto -ne "any") { $files = $files | Where-Object { $_.Name -match "\-$proto\.ovpn$" } }
    $files | Sort-Object FullName
}

function Read-RemoteLines([string]$ovpnPath) {
    # returns list of {host,port,proto} parsed from `remote host [port] [proto]`
    $out = @()
    foreach ($line in Get-Content -LiteralPath $ovpnPath) {
        $t = $line.Trim()
        if ($t -match "^remote\s+(\S+)(?:\s+(\d+))?(?:\s+(udp|tcp))?") {
            $out += [pscustomobject]@{ host = $Matches[1]; port = if ($Matches[2]) { [int]$Matches[2] } else { 443 }; proto = if ($Matches[3]) { $Matches[3] } else { "udp" } }
        }
    }
    if (-not $out) { throw "profile $ovpnPath has no 'remote' directive" }
    $out
}

function Test-TcpLatency([string]$Host, [int]$Port, [int]$TimeoutMs = 3500) {
    $client = New-Object System.Net.Sockets.TcpClient
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        $task = $client.ConnectAsync($Host, $Port)
        if (-not $task.Wait($TimeoutMs)) { return [double]::PositiveInfinity }
        if ($client.Connected) { return $sw.Elapsed.TotalMilliseconds }
        return [double]::PositiveInfinity
    } catch { return [double]::PositiveInfinity }
    finally { $client.Dispose() }
}

function Pick-Profile([string]$country, [string]$proto, [switch]$roulette, [switch]$fastest) {
    $files = Get-ProfileFiles $country $proto
    if (-not $files) { throw "no profiles match country='$country' protocol='$proto'" }
    if ($roulette) {
        $pick = $files | Get-Random
        Write-Ok "roulette: picked $($pick.Name)"
        return $pick
    }
    if ($fastest) {
        Write-Step "latency-testing $($files.Count) candidate endpoint(s)..."
        $best = $null; $bestLat = [double]::PositiveInfinity
        foreach ($f in $files) {
            $remote = (Read-RemoteLines $f.FullName)[0]
            $lat = Test-TcpLatency $remote.host $remote.port
            Write-Host ("    {0,-34} {1,8:N0} ms" -f $f.Name, $lat)
            if ($lat -lt $bestLat) { $bestLat = $lat; $best = $f }
        }
        Write-Ok "fastest: $($best.Name) @ $([math]::Round($bestLat,0)) ms"
        return $best
    }
    return $files[0]
}

# --------------------------------------------------------- auth helpers -----
function Resolve-AuthFile([string]$profile) {
    $needAuth = Get-Content -LiteralPath $profile | Where-Object { $_.Trim() -eq "auth-user-pass" }
    if (-not $needAuth) { return $null }        # profile has no auth line
    if ($AuthFile -and (Test-Path -LiteralPath $AuthFile)) { return (Resolve-Path $AuthFile).Path }
    $candidate = Join-Path $script:Secrets "vpn.auth"
    if (Test-Path -LiteralPath $candidate) { return $candidate }
    if (-not (Test-Path -LiteralPath $script:Secrets)) { New-Item -ItemType Directory -Path $script:Secrets -Force | Out-Null }
    $u = Read-Host "OpenVPN username"
    if (-not $u) { return $null }
    $sec = Read-Host "OpenVPN password" -AsSecureString
    $p = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
    "$u`n$p" | Set-Content -LiteralPath $candidate -Encoding UTF8
    Write-Step "saved credentials to $candidate (git-ignored)"
    return $candidate
}

# --------------------------------------------------------------- openvpn ----
function Find-Openvpn {
    $cmd = Get-Command openvpn -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    foreach ($p in @("C:\Program Files\OpenVPN\bin\openvpn.exe",
                     "C:\Program Files (x86)\OpenVPN\bin\openvpn.exe",
                     "C:\Program Files\OpenVPN Connect\openvpn\openvpn.exe")) {
        if (Test-Path -LiteralPath $p) { return $p }
    }
    $linux = (Get-Command openvpn -ErrorAction SilentlyContinue).Source
    if ($linux) { return $linux }
    throw "openvpn binary not found. Run .\vpn-init.ps1 (choco/winget) or set PATH."
}

function Connect-Openvpn([string]$profile) {
    if (-not (Test-Path -LiteralPath $Logs)) { New-Item -ItemType Directory -Path $Logs -Force | Out-Null }
    $exe   = Find-Openvpn
    $auth  = Resolve-AuthFile $profile
    $pidf  = Join-Path $Logs ("openvpn-{0}.pid" -f [IO.Path]::GetFileNameWithoutExtension($profile.FullName))
    $logf  = Join-Path $Logs ("openvpn-{0}.log" -f [IO.Path]::GetFileNameWithoutExtension($profile.FullName))
    $ovArgs = @("--config", $profile.FullName, "--writepid", $pidf, "--log", $logf, "--verb", "3")
    if ($auth) { $ovArgs += @("--auth-user-pass", $auth, "--auth-nocache") }
    if ($SplitTunnel) { $ovArgs += @("--route-metric", "600") }
    Write-Step "launching: openvpn --config $($profile.Name)$(if($auth){' (auth-secured)'})"
    $proc = Start-Process -FilePath $exe -ArgumentList $ovArgs -WindowStyle Hidden -PassThru
    Start-Sleep -Seconds 2
    if ($proc.HasExited) { throw "openvpn exited immediately (code $($proc.ExitCode)) — check $logf" }
    return [pscustomobject]@{
        backend   = "openvpn"
        name      = $profile.Name
        country   = (Split-Path (Split-Path $profile.FullName) -Leaf)
        profile   = $profile.FullName
        pid       = $proc.Id
        pidfile   = $pidf
        logfile   = $logf
        started   = (Get-Date).ToString("o")
        killed    = $false
    }
}

function Disconnect-Openvpn($state) {
    if ($state.pid) {
        Stop-Process -Id $state.pid -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 500
    }
    if ($state.pidfile -and (Test-Path -LiteralPath $state.pidfile)) {
        $stale = Get-Content -LiteralPath $state.pidfile -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($stale -match "^\d+$") { Stop-Process -Id ([int]$stale) -Force -ErrorAction SilentlyContinue }
        Remove-Item -LiteralPath $state.pidfile -Force -ErrorAction SilentlyContinue
    }
}

# ----------------------------------------------------------------- docker ---
function Find-Docker {
    $cmd = Get-Command docker -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw "docker CLI not found — install Docker Desktop or use -Backend openvpn."
}

function Connect-Docker([string]$profile) {
    $docker = Find-Docker
    $name = "sar-vpn-$([Guid]::NewGuid().ToString("N").Substring(0,6))"
    $auth  = Resolve-AuthFile $profile
    $envargs = @()
    if ($auth) {
        $lines = Get-Content -LiteralPath $auth
        if ($lines.Count -ge 2) { $envargs = @("-e", "username=$($lines[0])", "-e", "password=$($lines[1])") }
    }
    if (-not $SplitTunnel) { $envargs += @("-e", "ALLOWED_SUBNETS=0.0.0.0/0") }
    $run = @("run", "-d", "--name", $name, "--cap-add", "NET_ADMIN", "--device", "/dev/net/tun", "--rm",
             "-v", "$($profile.FullName):/config/config:ro") + $envargs + @("dperson/openvpn-client")
    Write-Step "docker: pulling/starting dperson/openvpn-client ..."
    & $docker $run 2>&1 | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "docker run failed (need Docker Desktop + WSL2 with /dev/net/tun)." }
    Write-Ok "VPN container running: $name"
    Write-Host "    point the SAR-DSS backend at it:" -ForegroundColor DarkGray
    Write-Host "        $docker run --network container:$name -e OUTBOUND_MODE=direct sar-dss-backend" -ForegroundColor DarkGray
    return [pscustomobject]@{
        backend = "docker"
        name    = $name
        profile = $profile.FullName
        country = (Split-Path (Split-Path $profile.FullName) -Leaf)
        started = (Get-Date).ToString("o")
        container = $name
    }
}

function Disconnect-Docker($state) {
    if ($state.container) {
        $docker = (Get-Command docker -ErrorAction SilentlyContinue).Source
        if ($docker) {
            & $docker stop $state.container 2>$null | Out-Null
            & $docker rm $state.container 2>$null | Out-Null
        }
    }
}

# ------------------------------------------------------------------- ssh ----
function Resolve-SshTarget {
    if (-not $JumpHost) { throw "ssh backend needs -JumpHost (and -JumpUser)." }
    $user = if ($JumpUser) { "$JumpUser@" } else { "" }
    "$user$JumpHost"
}
function Connect-Ssh {
    $ssh = (Get-Command ssh -ErrorAction SilentlyContinue).Source
    if (-not $ssh) {
        $ssh = Join-Path $env:SystemRoot "System32\OpenSSH\ssh.exe"
        if (-not (Test-Path -LiteralPath $ssh)) { throw "OpenSSH client not found." }
    }
    $port = if ($SocksPort) { $SocksPort } else { 1080 }
    $target = Resolve-SshTarget
    $sshArgs = @("-N", "-D", "127.0.0.1:$port", "-o", "StrictHostKeyChecking=accept-new",
                 "-o", "ExitOnForwardFailure=yes", "-o", "ServerAliveInterval=30",
                 "-p", "$JumpPort")
    if ($JumpKey) { $sshArgs += @("-i", $JumpKey) }
    $sshArgs += $target
    Write-Step "ssh tunnel: $($sshArgs -join ' ')  (socks5://127.0.0.1:$port)"
    $proc = Start-Process -FilePath $ssh -ArgumentList $sshArgs -WindowStyle Hidden -PassThru
    Start-Sleep -Seconds 3
    if ($proc.HasExited) { throw "ssh tunnel exited (code $($proc.ExitCode))" }
    Write-Ok "SOCKS tunnel live at 127.0.0.1:$port — export it to SAR-DSS with:"
    Write-Host "    .\vpn.ps1 export -SocksPort $port" -ForegroundColor Green
    return [pscustomobject]@{
        backend = "ssh"
        name    = "ssh-$target"
        pid     = $proc.Id
        port    = $port
        target  = $target
        started = (Get-Date).ToString("o")
    }
}
function Disconnect-Ssh($state) {
    if ($state.pid) { Stop-Process -Id $state.pid -Force -ErrorAction SilentlyContinue }
}

# ------------------------------------------------------------------- ras ----
function Connect-Ras([string]$profile) {
    $remote = (Read-RemoteLines $profile.FullName)[0].host
    if (-not $profile -and -not $JumpHost) { throw "ras backend needs a server. Use -Profile or -JumpHost." }
    Write-Warn "ras backend only works with servers supporting $TunnelType (FreeVPN4You configs are OpenVPN-only)."
    if (Get-VpnConnection -Name $VpnName -ErrorAction SilentlyContinue) { Remove-VpnConnection -Name $VpnName -Force }
    Add-VpnConnection -Name $VpnName -ServerAddress $remote.Split(":")[0] -TunnelType $TunnelType -RememberCredential -ErrorAction Stop
    Write-Step "dialling $VpnName -> $remote ..."
    if ($JumpUser -and $JumpHost) {
        # split server from credentials host: reuse user as login
        rasdial $VpnName "$JumpUser" "$($JumpHost)" | Out-Host
    } else {
        rasdial $VpnName | Out-Host
    }
    return [pscustomobject]@{
        backend = "ras"
        name    = $VpnName
        server  = $remote
        started = (Get-Date).ToString("o")
    }
}
function Disconnect-Ras($state) {
    rasdial ("{0} /disconnect" -f $state.name) 2>$null | Out-Null
    Remove-VpnConnection -Name $state.name -Force -ErrorAction SilentlyContinue
}

# ------------------------------------------------------------- killswitch ----
function Add-KillSwitch([string]$remoteHost) {
    if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "-KillSwitch needs an elevated shell."
    }
    Write-Warn "adding firewall rules: allow DNS/VPN + block rest. Internet dies if the tunnel drops."
    New-NetFirewallRule -DisplayName "SAR-VPN-ALLOW-DNS" -Direction Outbound -Action Allow -Protocol UDP -RemotePort 53 -ErrorAction SilentlyContinue | Out-Null
    New-NetFirewallRule -DisplayName "SAR-VPN-ALLOW-DNS-TCP" -Direction Outbound -Action Allow -Protocol TCP -RemotePort 53 -ErrorAction SilentlyContinue | Out-Null
    New-NetFirewallRule -DisplayName "SAR-VPN-ALLOW-DHCP" -Direction Outbound -Action Allow -RemotePort 67,68 -ErrorAction SilentlyContinue | Out-Null
    if ($remoteHost) {
        New-NetFirewallRule -DisplayName "SAR-VPN-ALLOW-REMOTE" -Direction Outbound -Action Allow -RemoteAddress $remoteHost -ErrorAction SilentlyContinue | Out-Null
    }
    New-NetFirewallRule -DisplayName "SAR-VPN-BLOCK-ALL" -Direction Outbound -Action Block -Profile Any -ErrorAction SilentlyContinue | Out-Null
}
function Remove-KillSwitch {
    Get-NetFirewallRule -DisplayName "SAR-VPN-*" -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
}

# ----------------------------------------------------------- tunnel check ----
function Test-TunUp($backend) {
    if ($backend -in @("openvpn", "docker")) {
        return @(Get-NetAdapter -ErrorAction SilentlyContinue |
            Where-Object { $_.Status -eq "Up" -and $_.InterfaceDescription -match "TAP|TUN|WireGuard|OpenVPN" }).Count -gt 0
    }
    return $true
}
function Test-Probe($backend, $port) {
    if ($backend -eq "ssh" -and $port) {
        try { $c = New-Object Net.Sockets.TcpClient; $t = $c.ConnectAsync("127.0.0.1", $port); $ok = $t.Wait(1500) -and $c.Connected; $c.Dispose(); return $ok } catch { return $false }
    }
    if ($backend -eq "ras") { return (Get-VpnConnection -Name $VpnName -ErrorAction SilentlyContinue).ConnectionStatus -eq "Connected" }
    return $true
}

# --------------------------------------------------------------- connect ----
function Connect-Vpn {
    if ($Backend -eq "ssh") {
        $state = Connect-Ssh
        Save-State @{ ssh_stamp = (Get-Date).ToString("o") }
        if ($state.port) { Show-Ip; Write-Ok "tunnel pid=$($state.pid). Now run: .\vpn.ps1 export -SocksPort $($state.port)" }
        return $state
    }
    if (-not $Profile) {
        $profile = Pick-Profile $Country $Protocol -roulette:$Roulette -fastest:$Fastest
    } else {
        $profile = Get-ChildItem -LiteralPath $script:Configs -Recurse -Filter *.ovpn -File |
            Where-Object { $_.Name -match $Profile } | Select-Object -First 1
        if (-not $profile) { throw "no profile matching -Profile '$Profile'." }
    }
    $ipBefore = (Get-PublicIp) -as [string]
    Write-Step "current exit: $ipBefore ; profile: $($profile.Name)"
    switch ($Backend) {
        "openvpn" { $state = Connect-Openvpn $profile }
        "docker"  { $state = Connect-Docker $profile }
        "ras"     { $state = Connect-Ras $profile }
        default   { throw "backend $Backend not implemented" }
    }
    if ($KillSwitch) { Add-KillSwitch $profile.FullName }
    $table = @{ backend = $state.backend; name = $state.name; profile = $state.profile;
                country = $state.country; pid = $state.pid; started = $state.started;
                ip_before = $ipBefore }
    if ($state.pidfile) { $table.pidfile = $state.pidfile }
    if ($state.logfile) { $table.logfile = $state.logfile }
    if ($state.port)    { $table.port = $state.port }
    if ($state.container){ $table.container = $state.container }
    Save-State $table

    Write-Step "waiting for tunnel to come up..."
    $up = $false
    for ($i = 0; $i -lt 30; $i++) {
        if (Test-TunUp $table.backend -and (Test-Probe $table.backend $table.port)) { $up = $true; break }
        Start-Sleep -Seconds 1
    }
    $ipAfter = $null
    try { $ipAfter = (Get-PublicIp) -as [string] } catch { }
    if ($up -and $ipAfter -and $ipAfter -ne $ipBefore) {
        Write-Ok "connected:  $ipBefore -> $ipAfter"
        $table.ip_after = $ipAfter; Save-State $table
    } else {
        Write-Warn "tunnel state uncertain (before=$ipBefore after=$ipAfter). Check status."
    }
    if ($AutoReconnect) { Watch-Vpn $table }
    return $table
}

function Watch-Vpn($state) {
    Write-Step "watchdog armed (every $ReconnectDelay s, max $MaxReconnects reconnects)..."
    $ipBefore = if ($state.ip_before) { $state.ip_before } else { "" }
    $reconnects = 0
    while ($true) {
        Start-Sleep -Seconds $ReconnectDelay
        $alive = $false
        try {
            $ip = Get-PublicIp
            $alive = ($null -ne $ip) -and ($ip -ne $ipBefore)
        } catch { $alive = $false }
        if (-not $alive) {
            $reconnects++
            Write-Warn "tunnel down (probe #$reconnects) — reconnecting..."
            Disconnect-ByBackend $state
            Start-Sleep -Seconds 2
            if ($reconnects -gt $MaxReconnects) { Write-Fail "giving up after $MaxReconnects reconnects."; break }
            switch ($state.backend) {
                "openvpn" { $new = Connect-Openvpn ([IO.FileInfo]$state.profile) }
                "docker"  { $new = Connect-Docker ([IO.FileInfo]$state.profile) }
                default   { $new = Connect-Ssh }
            }
            $new | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $script:State -Encoding UTF8
            $state = $new
        }
    }
}

function Disconnect-ByBackend($state) {
    if (-not $state) { return }
    Write-Step "disconnecting backend=$($state.backend) ..."
    switch ($state.backend) {
        "openvpn"  { Disconnect-Openvpn $state }
        "docker"   { if ($state.container) { Disconnect-Docker $state } }
        "ssh"      { Disconnect-Ssh $state }
        "ras"      { Disconnect-Ras $state }
    }
    Remove-KillSwitch
}

# ---------------------------------------------------------------- actions ---
try {
    switch ($Action) {
        "help" {
            Get-Content -LiteralPath $PSCommandPath | Select-String -Pattern '^#' | ForEach-Object { $_.Line }
        }
        "countries" {
            Get-Countries | ForEach-Object {
                $n = (Get-ChildItem -LiteralPath $_.FullName -Filter *.ovpn -File).Count
                $prots = (Get-ChildItem -LiteralPath $_.FullName -Filter *.ovpn -File).Name -join ", "
                Write-Host ("{0,-14} {1,3}   {2}" -f $_.Name, $n, $prots)
            }
        }
        "list" {
            $files = Get-ProfileFiles $Country $Protocol
            $files | ForEach-Object {
                $r = (Read-RemoteLines $_.FullName)[0]
                Write-Host ("{0,-40}  {1}:{2} [{3}]" -f $_.FullName.Replace("$script:Configs\", ""), $r.host, $r.port, $r.proto)
            }
            Write-Host ("[{0} profiles]" -f $files.Count)
        }
        "connect" { Connect-Vpn }
        "status" {
            $s = Get-State
            if (-not $s) { Write-Warn "no active VPN recorded."; show-ip; return }
            Write-Step "last connection: backend=$($s.backend) name=$($s.name) started=$($s.started)"
            if ($s.backend -eq "ssh") { Show-Ip; Write-Ok "SOCKS: 127.0.0.1:$($s.port)  (pid $($s.pid))"; return }
            $tun = Test-TunUp $s.backend
            Write-Host ("[vpn] tunnel adapter up : {0}" -f $tun)
            if ($s.logfile -and (Test-Path -LiteralPath $s.logfile)) {
                Write-Host "[vpn] last log lines:" -ForegroundColor DarkGray
                Get-Content -LiteralPath $s.logfile -Tail 6 | ForEach-Object { Write-Host "      $_" -ForegroundColor DarkGray }
            }
            try { Show-Ip } catch { Write-Warn $_.Exception.Message }
        }
        "ip" { Show-Ip }
        "export" {
            $s = Get-State
            $port = if ($SocksPort) { $SocksPort } elseif ($s.port) { $s.port } else { 0 }
            if (-not $port) {
                Write-Warn "no tunnel with a SOCKS port recorded and -SocksPort not given."
                return
            }
            $envFile = Join-Path $script:Root ".env"
            if (Test-Path -LiteralPath $envFile) {
                $envContent = Get-Content -LiteralPath $envFile
                $updated = $false
                for ($i = 0; $i -lt $envContent.Count; $i++) {
                    if ($envContent[$i] -match "^OUTBOUND_PROXIES=.*") {
                        $envContent[$i] = "OUTBOUND_PROXIES=socks5://127.0.0.1:$port"
                        $updated = $true
                    }
                    if ($envContent[$i] -match "^OUTBOUND_MODE=.*" -and $envContent[$i] -notmatch "^#") {
                        # leave mode as-is so users keep rotate/failover/... over the local ball
                        if ($envContent[$i] -match "direct") {
                            $envContent[$i] = "OUTBOUND_MODE=rotate  # (over local socks5 -> tunnel)"
                        }
                    }
                }
                if (-not $updated) { $envContent += "OUTBOUND_PROXIES=socks5://127.0.0.1:$port" }
                $envContent | Set-Content -LiteralPath $envFile -Encoding UTF8
                Write-Ok ".env OUTBOUND_PROXIES set to socks5://127.0.0.1:$port (restart the backend to pick it up)."
            } else {
                Write-Warn "no .env found at $envFile - set OUTBOUND_PROXIES=socks5://127.0.0.1:$port manually."
            }
            if ($s) {
                Write-Host "    active tunnel  : $($s.backend) ($($s.name))"
                Write-Host "    verify egress  : .\egress-verify.ps1 -Before $($s.ip_before)"
            }
        }
        "disconnect" {
            $s = Get-State
            if (-not $s) { Write-Warn "nothing recorded as active."; return }
            Disconnect-ByBackend $s
            Clear-State
            Write-Ok "disconnected & state cleared."
        }
    }
} catch {
    Write-Fail "$($_.Exception.Message)"
}