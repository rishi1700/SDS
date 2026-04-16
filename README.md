# GS_VolumeManager User Guide

GS_VolumeManager is a desktop app for managing storage volumes.

You can use it to:

- Add a storage node
- Create a volume
- Mount a volume
- Unmount a volume
- Delete a volume

---

## What You Need Before You Start

Please have these ready:

- The **IP address** of your storage node (example: `192.168.30.55`)
- The **protocol** you want to use: `NFS`, `CIFS`, `iSCSI-Chap`, or `iSCSI-NoChap`
- A **username and password** — only needed for `CIFS` and `iSCSI-Chap`

---

## Basic Flow

Most users follow this order:

1. Open the app
2. Add a storage node
3. Create a volume
4. Mount the volume
5. Use the volume
6. Unmount the volume when finished
7. Delete the volume only if you no longer need it

---

## Add a Storage Node

A storage node is the server where your volumes live.

1. Enter the IP address of your storage node in the app.
2. Save it.
3. Select it from the list.

After selecting the node, the app will show its details.

---

## Create a Volume

A volume is a storage space on the storage node, similar to a folder or drive.

1. Select your storage node from the list.
2. Enter a name for the volume. Use a simple name for testing, such as:
   ```
   testvol1
   ```
3. Enter the size you want.
4. Choose a protocol: `NFS`, `CIFS`, `iSCSI-Chap`, or `iSCSI-NoChap`.
5. Enter a username and password if the protocol asks for one.
6. Click **Create**.

The app will confirm when the volume is created.

---

## Mount a Volume

Mounting connects the volume to your computer so you can read and write files on it.

1. If your new volume is not showing in the list, click **Reload**.
2. Select the volume.
3. Click **Mount**.
4. Wait for the result message.

Once mounted:

- On **Windows** — a new drive may appear in File Explorer (for example `F:\`).
- On **Linux** — a mount path will appear (for example `/mnt/testvol1`). Open that path in your file manager to use the volume.

---

## Unmount a Volume

Unmount a volume when you are finished using it.

1. Select the mounted volume from the list.
2. Click **Unmount**.
3. Wait for the app to confirm the volume is no longer mounted.

---

## Delete a Volume

Delete a volume only when you are completely sure you no longer need it.
This cannot be undone.

1. Unmount the volume first.
2. Select the volume from the list.
3. Click **Delete**.
4. Confirm when the app asks.

---

## Protocol Guide

| Protocol | Needs Username and Password |
|---|---|
| NFS | Usually no |
| CIFS | Yes |
| iSCSI-Chap | Yes |
| iSCSI-NoChap | Usually no |

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
- The protocol is correct.
- The username and password are correct (for CIFS and iSCSI-Chap).
- Your computer can reach the storage node.

### Windows: "F:\ is not accessible" popup

This message can appear even when the iSCSI connection itself worked.

It may mean:

- The disk connected but is not ready yet.
- The disk does not have a drive letter yet.
- Windows needs to initialize or format the disk first.

Check the app status before assuming the mount failed.

### Windows: iSCSI connected but no drive appears

This can happen if:

- The disk is connected but not initialized.
- A drive letter has not been assigned yet.
- Windows needs a little more time to finish preparing the disk.

Wait a moment and check Disk Management (press **Windows + X** and choose **Disk Management**).

### CHAP volume fails to mount

Possible reasons:

- Wrong username or password.
- The storage node cannot be found on the network.
- CHAP is not configured correctly on the storage node side.

---

## Good Practices

- Test one protocol at a time.
- Use simple volume names like `testvol1`.
- Always unmount a volume before deleting it.
- Note the exact message shown by the app if something goes wrong — it helps with troubleshooting.
