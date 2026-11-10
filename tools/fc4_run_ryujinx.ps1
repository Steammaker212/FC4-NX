# fc4-nx (2026-11-09): one run of the Switch NRO in the user's Ryubing (canary 1.3.272) with this port's own data folder
# (../ryu-data/fc4: keys and firmware stay there, never committed). tools/run_ryujinx.ps1 (katamari-nx's) with FC4's
# paths. Copies app/out/switch/renut.nro to sdcard/switch/fc4-nx/fc4-nx.nro, links sdcard/switch/fc4-nx/game_root to
# ../game (a directory junction: no copy of the 6.8 GB), optionally writes katamari.toml (the player's settings file the
# NRO reads next to itself) from -Toml, starts minimised, stops only the process it started after -Seconds, and moves the
# run's logs and PNG captures to out/emu_runs/<Name>.
#   powershell -File tools/fc4_run_ryujinx.ps1 -Seconds 300 -Name emu1 [-Toml out/emu_test.toml] [-Visible]
param([int]$Seconds = 240, [string]$Name = "emu", [string]$Toml = "", [switch]$Visible, [double]$MinCommitGB = 12)
$root = Split-Path -Parent $PSScriptRoot
$ryu = "C:\Users\Saif Khan\Documents\Emulation\Emulator's\ryujinx-canary-1.3.272-win_x64\publish\Ryujinx.exe"
$data = (Resolve-Path (Join-Path $root "..\ryu-data\fc4")).Path
$sd = Join-Path $data "sdcard\switch\fc4-nx"
$nro = Join-Path $sd "fc4-nx.nro"
$built = Join-Path $root "app\out\switch\renut.nro"
$out = Join-Path $root "out\emu_runs\$Name"
if (Get-Process -Name Ryujinx -ErrorAction SilentlyContinue) { Write-Output "a Ryujinx is running: not starting"; exit 2 }
$os = Get-CimInstance Win32_OperatingSystem
$freeCommit = $os.FreeVirtualMemory / 1MB
if ($freeCommit -lt $MinCommitGB) { Write-Output ("free commit memory {0:N1} GB < {1} GB: not starting" -f $freeCommit, $MinCommitGB); exit 3 }
if (-not (Test-Path $built)) { Write-Output "no NRO at $built (tools/fc4_build_switch.bat)"; exit 4 }
New-Item -ItemType Directory -Force $sd | Out-Null
Copy-Item $built $nro -Force
# Ryubing gives a command-line NRO no folder in argv[0], so GetExecutableFolder() is sdmc:/ there (a real Switch's
# hbmenu gives sdmc:/switch/fc4-nx/): game_root and katamari.toml go to both folders.
$sdRoot = Join-Path $data "sdcard"
$game = (Resolve-Path (Join-Path $root "..\game")).Path
foreach ($dir in @($sd, $sdRoot)) {
  $gameRoot = Join-Path $dir "game_root"
  if (-not (Test-Path $gameRoot)) {
    # $env:ComSpec, not cmd: from Git Bash's PATH "cmd" is devkitPro msys2's cmd script.
    & $env:ComSpec /c mklink /J "`"$gameRoot`"" "`"$game`"" | Out-Null
  }
  if (-not (Test-Path (Join-Path $gameRoot "default.xex"))) { Write-Output "no game files at $gameRoot"; exit 5 }
  if ($Toml) { Copy-Item $Toml (Join-Path $dir "katamari.toml") -Force }
}
$logs = Join-Path $sdRoot "logs"
New-Item -ItemType Directory -Force $out | Out-Null
if (Test-Path $logs) { Remove-Item -Recurse -Force $logs }
$started = Get-Date
$style = if ($Visible) { "Normal" } else { "Minimized" }
$p = Start-Process -FilePath $ryu -ArgumentList @("-r", "`"$data`"", "`"$nro`"") -PassThru -WindowStyle $style `
     -RedirectStandardOutput (Join-Path $out "ryujinx_stdout.txt") -RedirectStandardError (Join-Path $out "ryujinx_stderr.txt")
Write-Output ("started Ryujinx pid {0} (free commit {1:N1} GB)" -f $p.Id, $freeCommit)
$deadline = (Get-Date).AddSeconds($Seconds)
while ((Get-Date) -lt $deadline -and -not $p.HasExited) { Start-Sleep -Seconds 3 }
if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force; Write-Output "stopped pid $($p.Id) after $Seconds s" }
else { Write-Output "Ryujinx exited by itself (code $($p.ExitCode))" }
Start-Sleep -Seconds 2
if (Test-Path $logs) { Copy-Item -Recurse $logs (Join-Path $out "logs") -Force }
# Not -Recurse: it would walk the game through the junction.
@($sd, (Join-Path $sd "capturas"), $sdRoot, (Join-Path $sdRoot "capturas")) | ForEach-Object {
  Get-ChildItem $_ -Filter "*.png" -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -ge $started } |
      Move-Item -Destination $out -Force
}
$ryuLogs = Join-Path $data "Logs"
Get-ChildItem $ryuLogs -Filter "*.log" -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -ge $started } |
    Copy-Item -Destination $out -Force
Get-ChildItem $out | Select-Object Name, Length
