# SDS-WS — Getting Started Guide

SDS-WS is a desktop app that lets you manage storage volumes.
You can use it to create, mount, unmount, and delete storage volumes on a storage node.

This guide walks you through everything from installing the app to using it for the first time.
No technical knowledge is required. Every step is explained in plain language.

---

## Table of Contents

1. [What the App Does](#what-the-app-does)
2. [What You Need Before You Start](#what-you-need-before-you-start)
3. [Install on Windows](#install-on-windows)
4. [Install on Ubuntu / Linux](#install-on-ubuntu--linux)
5. [Run the App](#run-the-app)
6. [How to Use the App](#how-to-use-the-app)
   - [Add a Storage Node](#add-a-storage-node)
   - [Create a Volume](#create-a-volume)
   - [Mount a Volume](#mount-a-volume)
   - [Unmount a Volume](#unmount-a-volume)
   - [Delete a Volume](#delete-a-volume)
7. [Protocol Guide](#protocol-guide)
8. [Build a Standalone Executable (Optional)](#build-a-standalone-executable-optional)
9. [Common Messages and What They Mean](#common-messages-and-what-they-mean)
10. [Troubleshooting](#troubleshooting)

---

## What the App Does

With SDS-WS you can:

- Add a storage node (a server that holds your storage)
- Create a volume (a storage space on that node)
- Mount a volume (connect the volume to your computer so you can use it)
- Unmount a volume (disconnect it when you are done)
- Delete a volume (remove it permanently when you no longer need it)

---

## What You Need Before You Start

Please have these ready before you begin:

- The **IP address** of your storage node (example: `192.168.30.55`)
- The **protocol** you want to use: `NFS`, `CIFS`, `iSCSI-Chap`, or `iSCSI-NoChap`
- A **username and password** — only needed for `CIFS` and `iSCSI-Chap`

You also need **Python 3** installed on your computer.
The sections below explain how to check and install it.

---

## Install on Windows

Follow every step in order.

### Step 1 — Check if Python is already installed

1. Press the **Windows key**, type `cmd`, and press **Enter**.
   A black window called the Command Prompt will open.
2. Type the following and press **Enter**:
   ```
   python --version
   ```
3. If you see something like `Python 3.x.x`, Python is installed. Skip to **Step 3**.
4. If you see an error or nothing, continue to **Step 2**.

### Step 2 — Install Python

1. Open your web browser and go to **https://www.python.org/downloads/**
2. Click the big yellow **Download Python** button.
3. Open the downloaded file.
4. On the installer screen:
   - **Tick the box** that says **"Add Python to PATH"** (this is important — do not skip it)
   - Click **Install Now**
5. Wait for the installation to finish, then close the installer.
6. Close and reopen the Command Prompt, then repeat Step 1 to confirm Python is installed.

### Step 3 — Download the SDS-WS code

If you received the code as a ZIP file:

1. Right-click the ZIP file and choose **Extract All**.
2. Choose a folder you can easily find, such as `C:\Users\YourName\Desktop\SDS`.
3. Click **Extract**.

If you are using Git:

1. In the Command Prompt, type:
   ```
   git clone https://github.com/rishi1700/sds.git
   cd sds
   ```

### Step 4 — Install the required packages

1. In the Command Prompt, navigate to the SDS-WS folder.
   Replace the path below with wherever you extracted the files:
   ```
   cd C:\Users\YourName\Desktop\SDS
   ```
2. Install the required packages by typing:
   ```
   pip install requests flask zeroconf
   ```
3. Wait for the installation to finish. You will see progress messages.
   When it says `Successfully installed`, you are done.

### Step 5 — Run the app

In the Command Prompt, type:

```
python sds_gui.py
```

The SDS-WS window will open. You are ready to use the app.

---

## Install on Ubuntu / Linux

Follow every step in order.

### Step 1 — Open the Terminal

Press **Ctrl + Alt + T** on your keyboard.
A Terminal window will open.

### Step 2 — Check if Python is installed

Type this and press **Enter**:

```
python3 --version
```

If you see `Python 3.x.x`, Python is installed. Skip to **Step 4**.

If you see an error, continue to **Step 3**.

### Step 3 — Install Python and Tkinter

Type this and press **Enter**:

```
sudo apt update && sudo apt install python3 python3-pip python3-tk python3-venv -y
```

You may be asked for your password. Type it and press **Enter**.
(The password will not show on screen — that is normal.)

Wait for everything to install, then continue to **Step 4**.

### Step 4 — Install support tools for storage protocols

These tools are needed for mounting volumes.

```
sudo apt install nfs-common cifs-utils open-iscsi iputils-ping -y
```

### Step 5 — Download the SDS-WS code

If you received the code as a ZIP file:

1. Open the Files app, find the ZIP, right-click it and choose **Extract Here**.

If you are using Git:

```
git clone https://github.com/rishi1700/sds.git
cd sds
```

### Step 6 — Create a virtual environment and install packages

A virtual environment keeps the app's packages separate from the rest of your system.

In the Terminal, navigate to the SDS-WS folder (replace the path with your actual location):

```
cd ~/Desktop/SDS
```

Then run these commands one at a time:

```
python3 -m venv .venv-ubuntu
source .venv-ubuntu/bin/activate
pip install requests flask zeroconf
```

You will see `(venv-ubuntu)` appear at the start of your Terminal line.
This means the virtual environment is active.

### Step 7 — Run the app

While the virtual environment is active, type:

```
python3 sds_gui.py
```

The SDS-WS window will open. You are ready to use the app.

> **Note:** Every time you open a new Terminal to run the app, you must first activate
> the virtual environment again with:
> ```
> source .venv-ubuntu/bin/activate
> ```
> Then run `python3 sds_gui.py`.

---

## Run the App

### Windows

```
python sds_gui.py
```

### Ubuntu / Linux

```
source .venv-ubuntu/bin/activate
python3 sds_gui.py
```

---

## How to Use the App

Once the app is open, follow these steps in order:

1. Add a storage node
2. Create a volume
3. Mount the volume
4. Use the volume
5. Unmount the volume when finished
6. Delete the volume only if you no longer need it

---

### Add a Storage Node

A storage node is the server where your volumes live.

1. Find the field to enter a storage node IP address in the app.
2. Type the IP address of your storage node. Example:
   ```
   192.168.30.55
   ```
3. Save it.
4. Select the node from the list.

After selecting the node, the app will show details about it.

---

### Create a Volume

A volume is a storage space, like a folder or drive, that lives on the storage node.

1. Select your storage node from the list.
2. Enter a name for the volume. Use a simple name for testing, such as:
   ```
   testvol1
   ```
3. Enter the size you want (for example: `10` for 10 GB).
4. Choose a protocol from the list: `NFS`, `CIFS`, `iSCSI-Chap`, or `iSCSI-NoChap`.
5. If the protocol needs a username and password, enter them.
6. Click **Create**.

When creation is complete, the app will show a confirmation message.

---

### Mount a Volume

Mounting connects the volume to your computer so you can use it.

1. If the volume list is not showing your new volume, click **Reload** (or a similar refresh button).
2. Select the volume from the list.
3. Click **Mount**.
4. Wait for the result message.

When mounting is complete:

- On **Windows** — a new drive may appear in File Explorer (for example, `F:\` or `G:\`).
- On **Linux** — a mount path will appear (for example, `/mnt/testvol1`).
  Open that path in your file manager to use the volume.

---

### Unmount a Volume

When you are finished using a volume, unmount it to disconnect it safely.

1. Select the mounted volume from the list.
2. Click **Unmount**.
3. Wait for the app to confirm the volume is no longer mounted.

---

### Delete a Volume

Delete a volume only when you are completely sure you no longer need it.
This action cannot be undone.

1. Unmount the volume first (see above).
2. Select the volume from the list.
3. Click **Delete**.
4. Confirm when the app asks you to confirm.

---

## Protocol Guide

| Protocol | Needs Username & Password |
|---|---|
| NFS | Usually no |
| CIFS | Yes |
| iSCSI-Chap | Yes |
| iSCSI-NoChap | Usually no |

### NFS

A common file-sharing protocol. Usually no login is needed.

### CIFS

Used for Windows-style file shares. You will need a username and password.

### iSCSI-Chap

Block storage over a network with authentication. You will need a username and password.

### iSCSI-NoChap

Block storage over a network without authentication. No login needed.

---

## Build a Standalone Executable (Optional)

If you want to create a single file you can run without needing Python installed,
follow these steps.

### Windows — Build an EXE

1. Open the Command Prompt and navigate to the SDS-WS folder:
   ```
   cd C:\Users\YourName\Desktop\SDS
   ```
2. Run the build script using PowerShell:
   ```
   powershell -ExecutionPolicy Bypass -File build_win.ps1
   ```
3. When done, the file `dist\SDS-WS\SDS-WS.exe` will be created.
   Double-click it to run the app without needing Python.

### Ubuntu / Linux — Build a single binary

1. Open the Terminal and navigate to the SDS-WS folder:
   ```
   cd ~/Desktop/SDS
   ```
2. Make the build script executable:
   ```
   chmod +x build_linux.sh
   ```
3. Run the build script:
   ```
   ./build_linux.sh
   ```
4. When done, the file `dist/SDS-WS` will be created.
   Run it with:
   ```
   ./dist/SDS-WS
   ```

---

## Common Messages and What They Mean

| Message | What it means |
|---|---|
| Volume created successfully | The volume was created on the storage node. |
| Volume mounted successfully | The volume is now connected to your computer. |
| Volume not mounted | The mount did not work. See Troubleshooting below. |

---

## Troubleshooting

### Volume not mounting

Check the following:

- The storage node IP address is correct.
- The volume exists on the storage node.
- The protocol is correct.
- The username and password are correct (for CIFS and iSCSI-Chap).
- Your computer can reach the storage node (try pinging it).

### Windows: "F:\ is not accessible" popup

This message can appear even when the iSCSI connection itself has worked.

It may mean:

- The disk connected but is not ready yet.
- The disk does not have a drive letter yet.
- Windows needs to initialize or format the disk first.

Check the app status first before assuming the mount failed.

### Windows: iSCSI connected but no drive appears

This can happen if:

- The disk is connected but not initialized.
- A drive letter has not been assigned yet.
- Windows needs a little more time to finish preparing the disk.

Wait a moment and check Disk Management (press **Windows + X** and choose **Disk Management**).

### CHAP volume fails to mount

Possible reasons:

- Wrong username or password.
- The storage node cannot be discovered on the network.
- The CHAP settings on the storage node side are not configured correctly.

### Ubuntu: "python3: command not found"

Run this to install Python:

```
sudo apt update && sudo apt install python3 python3-pip python3-tk python3-venv -y
```

### Ubuntu: "No module named tkinter"

Run this to install Tkinter:

```
sudo apt install python3-tk -y
```

### Ubuntu: forgot to activate the virtual environment

You will see an error like `No module named flask`. Activate the environment first:

```
source .venv-ubuntu/bin/activate
```

Then run the app again.

---

## Quick Reference

| Task | Windows command | Ubuntu / Linux command |
|---|---|---|
| Check Python version | `python --version` | `python3 --version` |
| Install packages | `pip install requests flask zeroconf` | `pip install requests flask zeroconf` |
| Activate virtual environment | *(not needed on Windows)* | `source .venv-ubuntu/bin/activate` |
| Run the app | `python sds_gui.py` | `python3 sds_gui.py` |
| Build standalone file | `powershell -File build_win.ps1` | `./build_linux.sh` |

---

## Good Practices

- Test one protocol at a time.
- Use simple volume names like `testvol1`.
- Mount one test volume first before testing many at once.
- Always unmount a volume before deleting it.
- If something goes wrong, note the exact message shown by the app — it helps with troubleshooting.
