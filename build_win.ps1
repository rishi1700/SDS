Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

python -m pip install --upgrade pyinstaller requests flask werkzeug zeroconf

python -m PyInstaller `
  --noconfirm `
  --onefile `
  --noconsole `
  --name GS_VolumeManager `
  --add-data "mount_services.py;." `
  gs_volume_gui.py

Write-Output ""
Write-Output "Build complete."
Write-Output "Executable: dist\GS_VolumeManager.exe"
