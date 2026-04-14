Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

python -m pip install --upgrade pyinstaller requests flask werkzeug zeroconf

python -m PyInstaller `
  --noconfirm `
  --onefile `
  --noconsole `
  --name SDS-WS `
  --add-data "computenode_service_client.py;." `
  --add-data "sdsClient.py;." `
  --hidden-import computenode_service_client `
  --hidden-import flask `
  --hidden-import werkzeug.serving `
  --hidden-import zeroconf `
  --collect-all flask `
  --collect-all werkzeug `
  --collect-all zeroconf `
  sds_gui.py

Write-Output ""
Write-Output "Build complete."
Write-Output "Executable: dist\SDS-WS.exe"
