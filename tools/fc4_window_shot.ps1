# fc4-nx (2026-11-09): PNG captures of the game window only (Win32 PrintWindow, PW_RENDERFULLCONTENT), for runs whose
# renderer has no capture of its own (Renut on PC). Captures the main window of the newest renut.exe every -Every
# seconds, -Count times, into -OutDir. Nothing else on the desktop is captured.
#   powershell -File tools/fc4_window_shot.ps1 -OutDir out/pc_runs/x -Every 20 -Count 6 [-Delay 10]
param([string]$OutDir, [int]$Every = 20, [int]$Count = 6, [int]$Delay = 10)
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class Fc4Win {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
}
"@
New-Item -ItemType Directory -Force $OutDir | Out-Null
Start-Sleep -Seconds $Delay
for ($i = 1; $i -le $Count; $i++) {
  $p = Get-Process -Name renut -ErrorAction SilentlyContinue | Sort-Object StartTime -Descending | Select-Object -First 1
  if (-not $p -or $p.MainWindowHandle -eq [IntPtr]::Zero) { Write-Output "no renut window"; Start-Sleep -Seconds $Every; continue }
  $r = New-Object Fc4Win+RECT
  [void][Fc4Win]::GetClientRect($p.MainWindowHandle, [ref]$r)
  $w = [Math]::Max(1, $r.R - $r.L); $h = [Math]::Max(1, $r.B - $r.T)
  $bmp = New-Object System.Drawing.Bitmap $w, $h
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $hdc = $g.GetHdc()
  [void][Fc4Win]::PrintWindow($p.MainWindowHandle, $hdc, 3)  # PW_CLIENTONLY | PW_RENDERFULLCONTENT
  $g.ReleaseHdc($hdc); $g.Dispose()
  $file = Join-Path $OutDir ("shot_{0:D2}.png" -f $i)
  $bmp.Save($file, [System.Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose()
  Write-Output "saved $file ($w x $h)"
  Start-Sleep -Seconds $Every
}
