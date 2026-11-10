# fc4-nx (2026-11-09): one run of the Switch NRO in the user's Eden (yuzu fork; its own data folder %APPDATA%\Eden,
# keys and firmware there). Stock Ryubing rejects svcMapProcessCodeMemory with the current-process pseudo-handle
# (no hbloader, so no real handle: guest memory cannot be mapped); yuzu's handle table accepts it.
# Copies app/out/switch/renut.nro to sdmc/switch/fc4-nx/fc4-nx.nro, links sdmc/switch/fc4-nx/game_root to ../game
# (a directory junction, no copy), optionally writes katamari.toml from -Toml, stops only the process it started
# after -Seconds, and copies the run's logs and PNG captures to out/emu_runs/<Name>.
#   powershell -File tools/fc4_run_eden.ps1 -Seconds 300 -Name eden1 [-Toml out/emu_test.toml] [-Visible]
param([int]$Seconds = 240, [string]$Name = "eden", [string]$Toml = "", [switch]$Visible)
$root = Split-Path -Parent $PSScriptRoot
$eden = "C:\Users\Saif Khan\Documents\Emulation\Emulator's\Eden\eden.exe"
$data = Join-Path $env:APPDATA "Eden"
$sdRoot = Join-Path $data "sdmc"
$sd = Join-Path $sdRoot "switch\fc4-nx"
$nro = Join-Path $sd "fc4-nx.nro"
$built = Join-Path $root "app\out\switch\renut.nro"
$out = Join-Path $root "out\emu_runs\$Name"
if (Get-Process -Name eden -ErrorAction SilentlyContinue) { Write-Output "an Eden is running: not starting"; exit 2 }
if (-not (Test-Path $built)) { Write-Output "no NRO at $built (tools/fc4_build_switch.bat)"; exit 4 }
New-Item -ItemType Directory -Force $sd | Out-Null
Copy-Item $built $nro -Force
$gameRoot = Join-Path $sd "game_root"
if (-not (Test-Path $gameRoot)) {
  $game = (Resolve-Path (Join-Path $root "..\game")).Path
  # $env:ComSpec, not cmd: from Git Bash's PATH "cmd" is devkitPro msys2's cmd script.
  & $env:ComSpec /c mklink /J "`"$gameRoot`"" "`"$game`"" | Out-Null
}
if (-not (Test-Path (Join-Path $gameRoot "default.xex"))) { Write-Output "no game files at $gameRoot"; exit 5 }
if ($Toml) { Copy-Item $Toml (Join-Path $sd "katamari.toml") -Force }
New-Item -ItemType Directory -Force $out | Out-Null
$appLog = Join-Path $sdRoot "fc4_emu.log"
Remove-Item -Force $appLog -ErrorAction SilentlyContinue
$started = Get-Date
$style = if ($Visible) { "Normal" } else { "Minimized" }
$p = Start-Process -FilePath $eden -ArgumentList @("-g", "`"$nro`"") -PassThru -WindowStyle $style
Write-Output ("started Eden pid {0}" -f $p.Id)
$deadline = (Get-Date).AddSeconds($Seconds)
while ((Get-Date) -lt $deadline -and -not $p.HasExited) { Start-Sleep -Seconds 3 }
if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force; Write-Output "stopped pid $($p.Id) after $Seconds s" }
else { Write-Output "Eden exited by itself (code $($p.ExitCode))" }
Start-Sleep -Seconds 2
if (Test-Path $appLog) { Copy-Item $appLog $out -Force }
foreach ($f in @("deko3d.log", "switch\rex_stderr.log", "switch\fc4-nx\logs\rex\rex_stderr.log", "switch\fc4-nx\logs\rex\rex_crash.log")) {
  $path = Join-Path $sdRoot $f
  if ((Test-Path $path) -and (Get-Item $path).LastWriteTime -ge $started) { Copy-Item $path $out -Force }
}
# Not -Recurse: it would walk the game through the junction.
@($sd, (Join-Path $sd "capturas"), $sdRoot, (Join-Path $sdRoot "capturas")) | ForEach-Object {
  Get-ChildItem $_ -Filter "*.png" -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -ge $started } |
      Move-Item -Destination $out -Force
}
Copy-Item (Join-Path $data "log\eden_log.txt") $out -Force -ErrorAction SilentlyContinue
Get-ChildItem $out | Select-Object Name, Length
