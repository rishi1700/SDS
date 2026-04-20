#!/usr/bin/env python3
import argparse
import sys
import subprocess

from mount_services import mountVolume, unmountVolume, deleteFolder

try:
    import pip
except ImportError:
    choice = input("pip not found. Do you want to install it now? (y/n): ").strip().lower()
    
    if choice in ("y", "yes"):
        try:
            import ensurepip
            ensurepip.bootstrap()
            print("pip installed successfully.")
        except Exception as e:
            print("Failed to install pip:", e)
            sys.exit(1)

        # Verify pip works
        try:
            import pip
        except ImportError:
            print("pip still not available after installation.")
            sys.exit(1)
    else:
        print("pip is required to run this script. Please install pip and try again.")
        sys.exit(1)

try:
    import requests
except ImportError:
    print("The 'requests' module is not installed.")

    choice = input("Do you want to install it now? (y/n): ").strip().lower()
    if choice in ("y", "yes"):
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", "requests", "--break-system-packages"
            ])
            print("requests installed successfully. Restarting import...")
            import requests
        except subprocess.CalledProcessError:
            print("Failed to install 'requests'. Please install it manually.")
            sys.exit(1)
    else:
        print("Installation cancelled by user.")
        sys.exit(1)
    
import requests
import time
import itertools
import threading

# ---------------------------
# Constants
# ---------------------------
AWS = False
PORT = 4000 # Change port according Flask Rest Api

global URL

PROTOCOLS = {
    "CIFS" : 1,
    "NFS" : 2,
    "iSCSI-Chap" : 3,
    "iSCSI-NoChap" : 4
}


# ---------------------------
# Loader Function
# ---------------------------
def spinner(msg, stop_event):
    spinner_cycle = itertools.cycle(['|', '/', '-', '\\'])
    while not stop_event.is_set():
        sys.stdout.write(f"\r{msg} {next(spinner_cycle)}")
        sys.stdout.flush()
        time.sleep(0.1)
    sys.stdout.write("\r" + " " * (len(msg) + 2) + "\r") 


# ---------------------------
# Helper Function
# ---------------------------
    
def is_strorge_node_reachable(url,timeout=10):
    try:
        print(f"Checking reachability of Storage Node at {url} ...")
        response = requests.get(url, timeout=timeout)
        return True
    except requests.exceptions.RequestException as e:
        return False
    except Exception as e:
        return False

# ---------------------------
# Command Implementations
# ---------------------------
def cmd_create_volume(args):
    stop_event = None
    loader_thread = None
    try:
        volumeName = args.name
        size = args.size
        sNode = args.Snode
        protocol_name = args.protocol
        if args.user and args.pw:
            user = args.user
            pw = args.pw
        else:
            user = ""
            pw = ""
            
        if sys.platform.startswith("win") and protocol_name in ["NFS"]:
            print(f"\nError: {protocol_name} protocol is not supported on Windows.")
            return

        stop_event = threading.Event()
        loader_thread = threading.Thread(target=spinner, args=("Creating SN Volume...", stop_event))
        loader_thread.start()

        protocolId = PROTOCOLS[protocol_name]

        priority = 1

        print(f"\nCreating volume '{volumeName}' size {size} ...")

        payload = {"volumeName" : volumeName,"size" : size,"protocolId" : protocolId, "priority" : priority, "user" : user, "password" : pw, "remote_ip" : sNode}         
        response = requests.post(URL+"/sn_volume",json=payload).json()

        stop_event.set()
        loader_thread.join()
        
        volume_status = response.get("status")
        if volume_status:
            print("\nVolume Created Successfully On Storage Node ....")
            print("Storage Node:", sNode)
            print("Pool Name:", response.get("poolInfo", {}).get("pool", {}).get("systemName"))
            print("\n")
        else:
            print("\nVolume Creation Failed On Storage Node ....")
            print("Message :",response.get("message") or response.get("message"))
            print("\n")
            
    except Exception as e:
        stop_event.set()
        loader_thread.join()
        print(f"Exception in creating volume : {str(e)}")
    finally:
        if stop_event:stop_event.set()
        if loader_thread: loader_thread.join()


def cmd_mount_volume(args):
    try:
        volumeName= args.name
        protocol_name = args.protocol
        sNode = args.Snode
        protocolId = PROTOCOLS[protocol_name]

    
        payload = {"volumeName" : volumeName,"protocol_name" : protocol_name,"protocolId" : protocolId,"state" : 6,"remote_ip" : sNode}

        stop_event = threading.Event()
        loader_thread = threading.Thread(target=spinner, args=("Mounting SN Volume...", stop_event))
        loader_thread.start()

        response = requests.put(URL+"/onOff_SN_Volume",json=payload).json()
        
        stop_event.set()
        loader_thread.join()

        
        if not response.get("status"):
            print("\nVolume On Error on Storage Node ....")
            print("Message :",response.get("message"),"\n")
            return
        

        print("\nVolume On Response :",response.get("message"),"\n")
        print("Volume Name : ",volumeName)

        user_name = response.get("host").get("user_name")
        ip = response.get("host").get("iqn")
        password = response.get("host").get("pw")

        mountResponse = mountVolume(volumeName,protocol_name,sNode,user_name,ip,password)
        if mountResponse.get("status") == "success":
            print("\nVolume Mounted Successfully....")
            print("Is Volume Mounted? : ", "Yes")
            print("Volume Mounted Path : ", mountResponse.get("mount_path"))
        else:
            print("\nVolume Mounting Failed On ....")
            print("Is Volume Mounted? : ", "No")
            print("Volume Mounted Path : ", mountResponse.get("mount_path"))
            print("Error Message : ", mountResponse.get("error_message") or mountResponse.get("message"))

        print("\n")
    except Exception as e:
        print(f"Exception in mounting volume : {str(e)}")


def cmd_unmount_volume(args):
    try:
        volumeName= args.name
        protocol_name = args.protocol
        sNode = args.Snode
        protocolId = PROTOCOLS[protocol_name]

        payload = {"volumeName" : volumeName,"protocol_name" : protocol_name,"protocolId" : protocolId,"state" : 4,"remote_ip" : sNode}

        stop_event = threading.Event()
        loader_thread = threading.Thread(target=spinner, args=("Unmounting SN Volume...", stop_event))
        loader_thread.start()

        response = requests.put(URL+"/onOff_SN_Volume",json=payload).json()
        
        stop_event.set()
        loader_thread.join()
        
        if not response.get("status"):
            print("\nVolume Off Error")
            print("Message :",response.get("message"),"\n")
            return
        
        print("\nVolume Off Response :",response.get("message"),"\n")
        print("Volume Name : ",volumeName)
        
        unMountResponse = unmountVolume(volumeName,sNode,protocol_name)
        if unMountResponse.get("status") == "success":
            print("\nVolume UnMounted Successfully....")
            print("Is Volume UnMounted? : ", "Yes")
            print("Volume UnMounted Path : ", unMountResponse.get("unmount_path"))
        else:
            print("\nVolume UnMounting Failed On ....")
            print("Is Volume UnMounted? : ", "No")
            print("Volume UnMounted Path : ", unMountResponse.get("unmount_path"))
            print("Error Message : ", unMountResponse.get("error_message") or unMountResponse.get("message"))
        print("\n")
    except Exception as e:
        print(f"Exception in mounting volume : {str(e)}")


def cmd_delete_volume(args):
    try:
        
        volumeName= args.name
        protocol_name = args.protocol
        Snode = args.Snode

        protocolId = PROTOCOLS[protocol_name]

        payload = {"volumeName" : volumeName,"protocolId" : protocolId, "remote_ip" : Snode}
        
        stop_event = threading.Event()
        loader_thread = threading.Thread(target=spinner, args=("Deleting SN Volume...", stop_event))
        loader_thread.start()

        response = requests.delete(URL+"/sn_volume",json=payload).json()

        stop_event.set()
        loader_thread.join()

        if response.get("status"):
            print("\nVolume Deleted Successfully On Storage Node ....")
            print("Volume Name : ",volumeName)
            print("Message : ",response.get("message"))
            print("\n")
            
            deleteResponse = deleteFolder(volumeName,protocol_name)
            if deleteResponse.get("status") == "success":
                print("\nFolder Deleted Successfully....")
                print("Folder Deleted Path : ",deleteResponse.get("local_path"))
                print("Folder Deleted Message : ",deleteResponse.get("message"))
                print("\n")
            else:
                print("\nFolder Not Deleted Successfully....")
                print("Folder Deleted Path : ",deleteResponse.get("local_path"))
                print("Folder Deleted Message : ",deleteResponse.get("message"))
                print("\n")
        else:
            print("\nStorage Volume Not Deleted ")
            print("Message :",f"{volumeName} - {response.get('message')}")
            print("\n")

    except Exception as e:
        print(f"Exception in deleting volume : {str(e)}")


# ---------------------------
# CLI Parser
# ---------------------------
def build_parser():
    parser = argparse.ArgumentParser(description="SN CLI helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # sn create volume
    p_create = subparsers.add_parser("create-volume", help="Create a new volume")
    p_create.add_argument("--name", required=True, help="Volume name")
    p_create.add_argument("--size", required=True, help="Volume size (e.g., 10G)")

    p_create.add_argument(
        "--Snode",
        required=True,
        help="Storage Node IP"
    )
    
    p_create.add_argument(
        "--protocol",
        required=True,
        choices=["NFS", "CIFS", "iSCSI-Chap", "iSCSI-NoChap"],
        help="Protocol (choose from: NFS, CIFS, iSCSI-Chap, iSCSI-NoChap)"
    )
    p_create.add_argument("--user", help="User name (required for silver group)")
    p_create.add_argument("--pw", help="Password (required for silver group)")
    
    
    p_create.set_defaults(func=cmd_create_volume, require_group_node=True)

    # sn mount volume
    p_on = subparsers.add_parser("on-volume", help="On an existing volume")
    p_on.add_argument("--name", required=True, help="Volume name")
    p_on.add_argument(
        "--Snode",
        required=True,
        help="Storage Node IP"
    )
    p_on.add_argument(
        "--protocol",
        required=True,
        choices=["NFS", "CIFS", "iSCSI-Chap", "iSCSI-NoChap"],
        help="Protocol (choose from: NFS, CIFS, iSCSI-Chap, iSCSI-NoChap)"
    )
    p_on.set_defaults(func=cmd_mount_volume, require_group_node=False)

    # sn unmount volume
    p_off = subparsers.add_parser("off-volume", help="Off an existing volume")
    p_off.add_argument("--name", required=True, help="Volume name")
    p_off.add_argument(
        "--Snode",
        required=True,
        help="Storage Node IP"
    )
    p_off.add_argument(
        "--protocol",
        required=True,
        choices=["NFS", "CIFS", "iSCSI-Chap", "iSCSI-NoChap"],
        help="Protocol (choose from: NFS, CIFS, iSCSI-Chap, iSCSI-NoChap)"
    )
    p_off.set_defaults(func=cmd_unmount_volume, require_group_node=False)

    # delete volume
    p_delete = subparsers.add_parser("delete-volume", help="Delete a volume")
    p_delete.add_argument("--name", required=True, help="Volume name")
    p_delete.add_argument(
        "--Snode",
        required=True,
        help="Storage Node IP"
    )
    p_delete.add_argument(
        "--protocol",
        required=True,
        choices=["NFS", "CIFS", "iSCSI-Chap", "iSCSI-NoChap"],
        help="Protocol (choose from: NFS, CIFS, iSCSI-Chap, iSCSI-NoChap)"
    )
    p_delete.set_defaults(func=cmd_delete_volume, require_group_node=False)

    return parser


# ---------------------------
# Main Entry
# ---------------------------
def main():
    global URL
    parser = build_parser()
    args = parser.parse_args()
    sNode = args.Snode
    if getattr(args, "require_group_node", False):
        if not args.Snode:
            print("Error: --Snode is required.")
            sys.exit(1)

    if args.command == "create-volume" and (args.protocol == "CIFS" or args.protocol == "iSCSI-Chap"):
        if not args.user or not args.pw:
            print("Error: --user and --pw are required when using CIFS or iSCSI protocol.")
            sys.exit(1)

    URL = f"http://{sNode}:{PORT}" 

    if not is_strorge_node_reachable(URL):
        print(f"Error: Storage Node {sNode} is not reachable at {URL}.")
        sys.exit(1)

    args.func(args)



if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)


# Helper command
# NFS - sudo python3 gsVolClient.py create-volume --name vold1 --size 10 --Snode 192.168.30.20 --protocol NFS
# CIFS - sudo python3 gsVolClient.py create-volume --name vold1 --size 10 --Snode 192.168.30.20 --protocol CIFS --user sanuyi --pw hello123
# ISCI - sudo python3 gsVolClient.py create-volume --name vold1 --size 10 --Snode 192.168.30.20 --protocol iSCSI-Chap --user sanuyi --pw hello123
# ISCI No Chap - sudo python3 gsVolClient.py create-volume --name vold1 --size 10 --Snode 192.168.30.20 --protocol iSCSI-NoChap --user sanuyi --pw hello123

# Mount - 
    # sudo python3 gsVolClient.py on-volume --name vold1 --Snode 192.168.30.20 --protocol NFS
    # sudo python3 gsVolClient.py on-volume --name vold1 --Snode 192.168.30.20 --protocol CIFS
    # sudo python3 gsVolClient.py on-volume --name vold1 --Snode 192.168.30.20 --protocol iSCSI-Chap
    # sudo python3 gsVolClient.py on-volume --name vold1 --Snode 192.168.30.20 --protocol iSCSI-NoChap

# Unmount - 
    # sudo python3 gsVolClient.py off-volume --name vold1 --Snode 192.168.30.20 --protocol NFS
    # sudo python3 gsVolClient.py off-volume --name vold1 --Snode 192.168.30.20 --protocol CIFS
    # sudo python3 gsVolClient.py off-volume --name vold1 --Snode 192.168.30.20 --protocol iSCSI-Chap
    # sudo python3 gsVolClient.py off-volume --name vold1 --Snode 192.168.30.20 --protocol iSCSI-NoChap

# Delete - 
    # sudo python3 gsVolClient.py delete-volume --name vold1 --Snode 192.168.30.20 --protocol NFS
    # sudo python3 gsVolClient.py delete-volume --name vold1 --Snode 192.168.30.20 --protocol CIFS
    # sudo python3 gsVolClient.py delete-volume --name vold1 --Snode 192.168.30.20 --protocol iSCSI-Chap
    # sudo python3 gsVolClient.py delete-volume --name vold1 --Snode 192.168.30.20 --protocol iSCSI-NoChap