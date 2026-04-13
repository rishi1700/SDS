Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

python -m pip install --upgrade pyinstaller requests flask zeroconf

python -m PyInstaller `
  --noconfirm `
  --windowed `
  --name SDS-WS `
  --add-data "computenode_service_client.py;." `
  sds_gui.py

Write-Output "Built: dist\SDS-WS\SDS-WS.exe"
