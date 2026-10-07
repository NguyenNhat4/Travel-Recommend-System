# PowerShell script tat SSH tunnel tren Windows
$ErrorActionPreference = "SilentlyContinue"

$procs = Get-CimInstance Win32_Process -Filter "Name = 'ssh.exe'" | Where-Object {
    $_.CommandLine -match "15432" -or $_.CommandLine -match "35\.197\.148\.180"
}

if ($procs) {
    foreach ($p in $procs) {
        Stop-Process -Id $p.ProcessId -Force
        Write-Host "Da dung tien trinh SSH tunnel (PID $($p.ProcessId))" -ForegroundColor Yellow
    }
} else {
    Write-Host "Khong co SSH tunnel nao dang chay tren cong 15432." -ForegroundColor Cyan
}
