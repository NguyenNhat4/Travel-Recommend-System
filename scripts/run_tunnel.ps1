$repoRoot = $PSScriptRoot | Split-Path -Parent
$askpass = Join-Path $repoRoot "askpass.cmd"
"@echo 6ns5QvT]H1`"~60~" | Set-Content -Path $askpass -Encoding Ascii
$env:SSH_ASKPASS = $askpass
$env:SSH_ASKPASS_REQUIRE = "force"

ssh -v -N -o ExitOnForwardFailure=yes -o StrictHostKeyChecking=accept-new -o PreferredAuthentications=password -o PubkeyAuthentication=no -o ServerAliveInterval=30 -o ServerAliveCountMax=10 -L 127.0.0.1:15432:10.148.0.2:5432 vota-dev@35.197.148.180
