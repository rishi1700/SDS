# SDS-WS User Guide

SDS-WS is a desktop app used to work with storage volumes.

You can use it to:

- add a storage node
- create a volume
- mount a volume
- unmount a volume
- delete a volume

This guide is written in simple language and focuses only on how to use the app.

## What You Need Before You Start

Please keep these details ready:

- storage node IP address
- protocol you want to use
- username and password if your protocol needs them

The app supports:

- `NFS`
- `CIFS`
- `iSCSI-Chap`
- `iSCSI-NoChap`

## Basic Flow

Most users will follow this order:

1. Open the app
2. Add or select a storage node
3. Create a volume
4. Mount the volume
5. Use the volume
6. Unmount the volume when finished
7. Delete the volume only if you no longer need it

## Open The App

Start the SDS-WS app on your computer.

When the app opens, you will usually:

1. add a storage node if it is not already listed
2. select the storage node
3. reload volumes if needed

## Add a Storage Node

You need the storage node IP address.

Example:

```text
192.168.30.55
```

In the app:

1. enter the storage node IP address
2. save it
3. select it from the list

After selecting the node, the app may show basic node details such as:

- node IP
- other storage information, depending on what the app receives

## Create a Volume

In the app:

1. select the storage node
2. enter a volume name
3. enter the size
4. choose the protocol
5. enter username and password if needed
6. click create

Use simple names for testing, such as:

```text
testvol1
```

## Protocol Guide

### NFS

Usually does not need username or password.

### CIFS

Usually needs username and password.

### iSCSI-Chap

Needs username and password.

### iSCSI-NoChap

Usually does not need username or password.

## Mount a Volume

In the app:

1. reload the volume list if needed
2. select the volume
3. click mount
4. wait for the result message

If the mount works, the app should show that the volume is mounted.

## Use the Mounted Volume

After mounting:

- for file-based protocols like `NFS` and `CIFS`, you should usually get a usable folder path
- for `iSCSI`, the connection may succeed before you see a usable drive or folder

If Windows shows a new drive, you can open it in File Explorer.

If Linux shows a mount path, you can open that path with your file manager.

## Unmount a Volume

When you are finished using a volume:

1. select the mounted volume
2. click unmount

Wait for the app to confirm that the volume is no longer mounted.

## Delete a Volume

Delete a volume only when you no longer need it.

In the app:

1. unmount the volume first
2. select the volume
3. click delete
4. confirm the deletion

## Common Messages and What They Mean

### Volume created successfully

The volume was created on the selected storage node.

### Volume mounted successfully

The app was able to mount the volume.

### Volume not mounted

The mount did not complete successfully.

Check:

- the selected protocol
- the username and password
- the storage node IP
- whether the volume really exists

## Windows iSCSI Notes

### `F:\ is not accessible` popup

This message can be misleading.

Sometimes Windows shows this even when the iSCSI connection itself has worked.

This may mean:

- the disk is connected but not ready yet
- the disk has no drive letter yet
- Windows still needs the disk to be initialized or formatted

Do not assume the full mount failed just because of this popup.

Check the app status and volume details first.

### iSCSI connected but no drive appears

This can happen if:

- the disk is connected but not initialized
- the drive letter is not assigned
- Windows needs a little more time to finish preparing the disk

## CHAP Notes

If a `CHAP` volume fails to mount, possible reasons include:

- wrong username or password
- target is not discoverable
- storage side CHAP export is not set correctly

## Good Testing Practice

To avoid confusion during testing:

- test one protocol at a time
- use simple volume names
- mount one new test volume first before testing many at once
- note the exact error message shown by the app

## Main App Files

Main files used by this app:

- [sds_gui.py](/C:/Users/rishi/Documents/SDS/sds_gui.py)
- [sdsClient.py](/C:/Users/rishi/Documents/SDS/sdsClient.py)
- [computenode_service_client.py](/C:/Users/rishi/Documents/SDS/computenode_service_client.py)

## Final Advice

- start simple
- test one step at a time
- read the exact app message carefully
- if something fails, keep the screenshot or error text for troubleshooting
