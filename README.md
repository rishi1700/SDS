# SDS-WS

SDS-WS is a desktop app for creating, mounting, unmounting, and deleting storage volumes.

It supports:

- `NFS`
- `CIFS`
- `iSCSI-Chap`
- `iSCSI-NoChap`

This guide is written in simple language so a person with little technical knowledge can follow it.

## What This App Does

You can use this app to:

- connect to a storage node
- create a new volume
- mount a volume to your computer
- unmount a volume
- delete a volume

## Before You Start

Please make sure you know:

- the IP address of your storage node
- the protocol you want to use
- the username and password if your protocol needs credentials

## Supported Platforms

- `Windows`
- `Ubuntu / Linux`

## 1. Windows Setup

### What You Need

- Windows computer
- Python installed
- internet access for Python packages

### How To Check Python

Open `Command Prompt` or `PowerShell` and run:

```powershell
py --version
```

If that does not work, install Python first.

### Install Python Packages

In the project folder, run:

```powershell
py -m pip install requests flask zeroconf pyinstaller
```

### Run The App on Windows

In the project folder, run:

```powershell
py sds_gui.py
```

### Build a Windows Executable

In the project folder, run:

```powershell
py -m PyInstaller --noconsole --onefile --name SDS-WS sds_gui.py `
  --hidden-import computenode_service_client `
  --hidden-import flask `
  --hidden-import werkzeug.serving `
  --hidden-import zeroconf `
  --collect-all flask `
  --collect-all werkzeug `
  --collect-all zeroconf
```

After the build is complete, the executable will be in:

```text
dist\SDS-WS.exe
```

## 2. Ubuntu / Linux Setup

### What You Need

- Ubuntu or Linux system
- Python 3
- terminal access

### Install System Packages

Open a terminal and run:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip python3-tk iputils-ping open-iscsi cifs-utils nfs-common xdg-utils
```

### Run The App on Ubuntu / Linux

In the project folder, run:

```bash
chmod +x run_ubuntu.sh
./run_ubuntu.sh
```

This script:

- creates a Python virtual environment if needed
- installs Python packages
- starts the app

### Build a Linux Executable

In the project folder, run:

```bash
chmod +x build_linux.sh
./build_linux.sh
```

After the build is complete, the executable will be in:

```text
dist/SDS-WS
```

## 3. If You Are Using WSL2

If you are using WSL2, the app can run only if GUI display is available.

If you are on Windows 11 with WSLg, it usually works automatically.

If the app says there is no display, restart WSL and try again:

```bash
wsl --shutdown
```

Then reopen Ubuntu and run:

```bash
./run_ubuntu.sh
```

## 4. First Time App Use

When the app opens:

1. Add or discover a storage node
2. Select the storage node
3. Reload volumes if needed
4. Create or mount a volume

## 5. How To Add a Storage Node

You need the storage node IP address.

In the app:

1. enter the storage node IP
2. save it
3. select it from the list

Example:

```text
192.168.30.55
```

## 6. How To Create a Volume

In the app:

1. choose the storage node
2. enter a volume name
3. enter the size
4. choose the protocol
5. if needed, enter username and password
6. click create

### Protocol Notes

- `NFS`: usually no username/password
- `CIFS`: usually needs username/password
- `iSCSI-Chap`: needs username/password
- `iSCSI-NoChap`: usually no username/password

## 7. How To Mount a Volume

In the app:

1. reload volumes
2. select the volume
3. click mount
4. if asked, enter credentials

### Important iSCSI Note

For iSCSI, the connection may succeed before you see a usable drive/folder path.

This is normal in some cases, especially on Windows.

## 8. How To Unmount a Volume

In the app:

1. select the mounted volume
2. click unmount

## 9. How To Delete a Volume

In the app:

1. unmount the volume first
2. select the volume
3. click delete
4. confirm the deletion

## 10. Common Problems

### Windows: Python command does not work

Try:

```powershell
py --version
```

If it still fails, install Python.

### Ubuntu: `xdg-open` missing

Run:

```bash
sudo apt install -y xdg-utils
```

### Ubuntu: Tkinter display error

This means the Linux system cannot open GUI windows.

If using WSL2:

- make sure WSLg is working
- restart WSL

### iSCSI connected but no drive appears

This can happen if:

- the disk is connected but not initialized
- the drive letter is not assigned
- the target is visible but not login-ready

### CHAP volume fails to mount

This may happen if:

- the CHAP target is not published correctly on the storage side
- the username/password is wrong
- the IQN/target is not discoverable

## 11. Files In This Project

Main files:

- [sds_gui.py](/C:/Users/rishi/Documents/SDS/sds_gui.py)
- [sdsClient.py](/C:/Users/rishi/Documents/SDS/sdsClient.py)
- [computenode_service_client.py](/C:/Users/rishi/Documents/SDS/computenode_service_client.py)

Helper files:

- [run_ubuntu.sh](/C:/Users/rishi/Documents/SDS/run_ubuntu.sh)
- [build_linux.sh](/C:/Users/rishi/Documents/SDS/build_linux.sh)
- [requirements-ubuntu.txt](/C:/Users/rishi/Documents/SDS/requirements-ubuntu.txt)
- [SDS-WS.spec](/C:/Users/rishi/Documents/SDS/SDS-WS.spec)
- [SDS-WS-linux.spec](/C:/Users/rishi/Documents/SDS/SDS-WS-linux.spec)

## 12. Quick Commands

### Windows Run

```powershell
py sds_gui.py
```

### Windows Build

```powershell
py -m PyInstaller --noconsole --onefile --name SDS-WS sds_gui.py `
  --hidden-import computenode_service_client `
  --hidden-import flask `
  --hidden-import werkzeug.serving `
  --hidden-import zeroconf `
  --collect-all flask `
  --collect-all werkzeug `
  --collect-all zeroconf
```

### Ubuntu Run

```bash
./run_ubuntu.sh
```

### Ubuntu Build

```bash
./build_linux.sh
```

## 13. Final Advice

- Start with one storage node and one volume
- Test one protocol at a time
- Use simple volume names
- If something fails, note the exact message shown in the app or terminal

That makes troubleshooting much easier.
