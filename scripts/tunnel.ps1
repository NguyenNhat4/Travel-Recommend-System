# PowerShell script mo SSH tunnel toi DB staging tren Windows
param(
    [string]$TunnelPrimary = "127.0.0.1:15432:10.148.0.2:5432",
    [string]$SshHost = "vota-dev@35.197.148.180"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$envTunnelPath = Join-Path $repoRoot ".env.tunnel"

# Kiem tra cong 15432 da mo chua
$conn = Test-NetConnection -ComputerName 127.0.0.1 -Port 15432 -WarningAction SilentlyContinue
if ($conn.TcpTestSucceeded) {
    Write-Host "[OK] Port 15432 da mo, tunnel dang hoat dong." -ForegroundColor Green
    exit 0
}

if (-not (Test-Path $envTunnelPath)) {
    Write-Error "Khong tim thay file .env.tunnel tai $envTunnelPath"
    exit 1
}

$pwLine = Get-Content $envTunnelPath | Where-Object { $_ -match "^SSH_PRIMARY_PASSWORD=" } | Select-Object -Last 1
if (-not $pwLine) {
    Write-Error "Thieu SSH_PRIMARY_PASSWORD trong .env.tunnel"
    exit 1
}
$sshPw = $pwLine -replace "^SSH_PRIMARY_PASSWORD=", ""

# Tao file askpass tam thoi
$askpassPath = Join-Path $env:TEMP "vota_askpass_$PID.cmd"
Set-Content -Path $askpassPath -Value "@echo $sshPw" -Encoding Ascii

try {
    $env:SSH_ASKPASS = $askpassPath
    $env:SSH_ASKPASS_REQUIRE = "force"

    $logDir = Join-Path $repoRoot ".logs"
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
    $logOut = Join-Path $logDir "tunnel.out.log"
    $logErr = Join-Path $logDir "tunnel.err.log"

    Write-Host "Dang ket noi SSH tunnel toi $SshHost..." -ForegroundColor Cyan
    $sshArgs = @(
        "-N",
        "-o", "ExitOnForwardFailure=yes",
        "-o", "PreferredAuthentications=password",
        "-o", "PubkeyAuthentication=no",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "ServerAliveInterval=30",
        "-L", $TunnelPrimary,
        $SshHost
    )

    $proc = Start-Process -FilePath "ssh.exe" -ArgumentList $sshArgs -PassThru -WindowStyle Hidden -RedirectStandardError $logErr -RedirectStandardOutput $logOut
    
    $opened = $false
    for ($i = 0; $i -lt 10; $i++) {
        Start-Sleep -Seconds 1
        if ($proc.HasExited) { break }
        $check = Test-NetConnection -ComputerName 127.0.0.1 -Port 15432 -WarningAction SilentlyContinue
        if ($check.TcpTestSucceeded) {
            $opened = $true
            break
        }
    }

    if (-not $opened -or $proc.HasExited) {
        $errContent = if (Test-Path $logErr) { Get-Content $logErr -Raw } else { "" }
        Write-Error "Ket noi SSH that bai (exit code $($proc.ExitCode)). Chi tiet:`n$errContent"
        exit 1
    }

    Write-Host "[OK] SSH Tunnel da chay ngam (PID: $($proc.Id)) tren 127.0.0.1:15432" -ForegroundColor Green
}
finally {
    Start-Sleep -Seconds 1
    if (Test-Path $askpassPath) {
        Remove-Item $askpassPath -Force -ErrorAction SilentlyContinue
    }
}
