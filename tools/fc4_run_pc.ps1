# fc4-nx: one PC test run of app/out/pc/renut.exe (tools/run_pc.ps1 with this port's paths): its own log folder
# (out/pc_runs/<Name>), muted, PNG captures every -Every seconds, stopped after -Seconds. Stops only the process it
# started.
#   powershell -File tools/fc4_run_pc.ps1 -Seconds 90 -Name boot1 [-Every 15] [-Extra "--gpu_plugin=xenos"] [-Visible]
param([int]$Seconds = 90, [string]$Name = "run", [int]$Every = 15, [string]$Extra = "", [switch]$Visible, [string]$Build = "pc")
$root = Split-Path -Parent $PSScriptRoot
$dir = Join-Path $root ("app\out\" + $Build)  # -Build pc_renut: the Renut renderer build
$exe = Join-Path $dir "renut.exe"
$game = (Resolve-Path (Join-Path $root "..\game")).Path -replace '\\', '/'
$logs = Join-Path $root "out\pc_runs\$Name"
New-Item -ItemType Directory -Force $logs | Out-Null
$log = Join-Path $logs "$Name.log"
Remove-Item $log -ErrorAction SilentlyContinue
$min = if ($Visible) { "false" } else { "true" }
$userRoot = (Join-Path $root "out\pc_user") -replace '\\', '/'
$argv = @("--log_file=`"$log`"", "--audio_mute=true", "--window_start_minimized=$min", "--fullscreen=false",
          "--game_data_root=`"$game`"", "--user_data_root=`"$userRoot`"",
          "--nfsmw_captura_cada_s=$Every", "--nfsmw_captura_max=60", "--log_file_writer=false") +
        @($Extra -split ' ' | Where-Object { $_ })
$style = if ($Visible) { "Normal" } else { "Minimized" }
$p = Start-Process -FilePath $exe -ArgumentList $argv -WorkingDirectory $dir -PassThru -WindowStyle $style `
     -RedirectStandardError (Join-Path $logs "stderr.txt") -RedirectStandardOutput (Join-Path $logs "stdout.txt")
Write-Output "started pid $($p.Id)"
$deadline = (Get-Date).AddSeconds($Seconds)
while ((Get-Date) -lt $deadline -and -not $p.HasExited) { Start-Sleep -Seconds 2 }
if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force; Write-Output "stopped pid $($p.Id) after $Seconds s" }
else { Write-Output "exited by itself with code $($p.ExitCode)" }
Start-Sleep -Seconds 1
Get-ChildItem $dir -Filter "*.png" -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -gt $p.StartTime } |
    Move-Item -Destination $logs -Force -ErrorAction SilentlyContinue
Get-ChildItem (Join-Path $dir "capturas") -Filter "*.png" -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -gt $p.StartTime } | Move-Item -Destination $logs -Force -ErrorAction SilentlyContinue
if (Test-Path $log) { Get-Content $log -Tail 40 }
