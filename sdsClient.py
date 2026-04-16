#!/usr/bin/env python3
import argparse
import sys
import subprocess
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

try:
    import flask
except ImportError:
    print("The 'flask' module is not installed.")

    choice = input("Do you want to install it now? (y/n): ").strip().lower()
    if choice in ("y", "yes"):
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", "flask", "--break-system-packages"
            ])
            print("flask installed successfully. Restarting import...")
            import flask
        except subprocess.CalledProcessError:
            print("Failed to install 'flask'. Please install it manually.")
            sys.exit(1)
    else:
        print("Installation cancelled by user.")
        sys.exit(1)
    
import requests
import time
import itertools
import threading
import json
import socket

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

def get_public_ip():
    if AWS:
        try:
            return requests.get("https://api.ipify.org").text.strip()
        except requests.RequestException:
            print("Failed to retrieve public IP address.")
            return None
        except Exception as e:
            print(f"An error occurred while reading pulic ip: {str(e)}")
            return None
    else:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))  # external IP (doesn't actually send data)
            ip = s.getsockname()[0]
        except Exception:
            ip = None
        finally:
            s.close()

        return ip

def ping_ip(ip , count = 5, timeout = 5):
    try:
        if AWS:
            url = f"http://{ip}"
            r = requests.get(url, timeout=timeout)
            return r.status_code == 200
        else:
            result = subprocess.run(
                ["ping", "-c", str(count), "-W", str(timeout), ip],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return result.returncode == 0
    except Exception:
        return False
    
def is_strorge_node_reachable(url,timeout=10):
    try:
        print(f"Checking reachability of Storage Node at {url} ...")
        response = requests.get(url, timeout=timeout)
        return True
    except requests.exceptions.RequestException as e:
        return False
    except Exception as e:
        return False

def getHostByProtocol(protocolId):
    try:
        response = requests.get(URL+"/getHostByProtocol",json={"protocolId" : protocolId}).json()
        return response
    except Exception as e:
        print(f"Exception in getting Host by Protocol : {str(e)}")

def getComputeNodeByComputeGroup(computeGroupId):
    try:
        response = requests.get(URL+"/getComputeNodeByComputeGroup",json={"computeGroupId" : computeGroupId}).json()
        return response
    except Exception as e:
        print(f"Exception in getting Host by Protocol : {str(e)}")

def getNodeIdFromStorageGroup(hostId):
    try:
        response = requests.post(URL+"/getHostGroup",json={"hostId" : hostId}).json()
        return response.get("controller_ids")
    except Exception as e:
        return None

def getNodeIpByController(controller_id):
    try:
        response = requests.post(URL+"/getEthPortsByController",json={"controller_id" : controller_id}).json()
        return response.get("ip")
    except Exception as e:
        return None
    
def getNodesDetails():
    try:
        response = requests.post(URL+"/getNodesDetails").json()
        return response
    except Exception as e:
        return None
    
def getComputeNodesDetails():
    try:
        response = requests.post(URL+"/getComputeNodesDetails").json()
        return response
    except Exception as e:
        return None
    
def save_storage_data(node_ip):
    try:
        if(not ping_ip(node_ip)):
            print(f"Node {node_ip} is not reachable")
            return
        
        if AWS:
            try:
                gui_check = requests.get(f"http://{node_ip}" + "/gui@Q", timeout=5)
                if gui_check.status_code != 200:
                    return
            except requests.RequestException as e:
                print(f"GUI check failed: {e}")
                return
        
        print(f"save_storage_data {node_ip}")
        payload = {"node_ip" : node_ip}
        response = requests.post(URL+"/storage-nodes",json=payload)
        print(f"Response for Node {node_ip} : {response.text}")
    except Exception as e:
        print(f"Exception in saving for {node_ip} remote data : {str(e)}")
    
def create_storage_group(hostName, protocol, iqn, user, pw):
    try:
        node_details = getNodesDetails()
        iqn_id = [item["id"] for item in node_details if item["ip"] in iqn]
        if not iqn_id:
            for item in iqn:
                save_storage_data(item)
            
            node_details = getNodesDetails()
            iqn_id = [item["id"] for item in node_details if item["value"] in iqn]

            if not iqn_id:
                return None
        payload = {"hostType" : "SDS Group", "name" : hostName, "protocol" : protocol,"iqn" : json.dumps(iqn_id),"user" : user,"password" : pw}
        response = requests.post(URL+"/create_SN_CN_HostGroup",json=payload).json()
        return response
    except Exception as e:
        print(f"Exception in creating storage group : {str(e)}")
        return None

def save_compute_node_data(name,address):
    try:
        payload = {"name" : name, "address" : address}
        response = requests.post(URL+"/compute-nodes",json=payload)
        print(f"\nResponse for Compute Node {name} : {response.text}")
    except Exception as e:
        print(f"Exception in saving for {name} remote data : {str(e)}")

def create_compute_group(hostName, protocol, iqn, user, pw):
    try:
        compute_ips = [item["address"] for item in iqn]

        compute_details = getComputeNodesDetails()
        iqn_id = [item["id"] for item in compute_details if item["value"] in compute_ips]
        
        if not iqn_id:
            for item in iqn:
                save_compute_node_data(item["name"],item["address"])
            
            compute_details = getComputeNodesDetails()
            iqn_id = [item["id"] for item in compute_details if item["value"] in compute_ips]
            if not iqn_id:
                return None

        
        
        payload = {"hostType" : "Compute Node Group", "name" : hostName, "protocol" : protocol,"iqn" : json.dumps(iqn_id),"user" : user,"password" : pw}
        response = requests.post(URL+"/create_SN_CN_HostGroup",json=payload).json()
        return response
    except Exception as e:
        print("Exception in creating compute group : ",str(e))
        return None

def readSDSVolumes():
    try:
        response = requests.post(URL+"/readVolumeBySDSDB",json={"volumeId" : "0"}).json()
        return response
    except Exception as e:
        print(f"Exception in reading SDS Volumes : {str(e)}")


def getRemoteIdByLocalId(table_name,local_id):
    try:
        payload = {"table_name" : table_name,"local_id" : local_id}
        response = requests.post(URL+"/getRemoteIdBySdsMapping",json=payload).json()
        return response.get("id")
    except Exception as e:
        print(f"Exception in getting remote id by local id : {str(e)}")
        return 0

# ---------------------------
# Command Implementations
# ---------------------------
def cmd_create_volume(args):
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

        CURRENT_IP = get_public_ip()
        if not CURRENT_IP:
            print("Error in getting public ip")
            return

        last_ip = CURRENT_IP.split(".")[-1] #192.168.30.117 - 117

        print("Selected Protocol : ",protocol_name)
        print("Current Compute IP : ",CURRENT_IP)

        compute_host_name = f"cngrp{protocol_name.lower()}{last_ip}"
        compute_ips = [{"name" : f"Compute Node {last_ip}", "address" : CURRENT_IP}]

        stop_event = threading.Event()
        loader_thread = threading.Thread(target=spinner, args=("Creating SDS Volume...", stop_event))
        loader_thread.start()

        protocolId = PROTOCOLS[protocol_name]

        hosts = getHostByProtocol(protocolId)

        if protocol_name in ["CIFS", "iSCSI-Chap"]:
            compute_node_data_id = [item for item in hosts if item["host_type"] == "Compute Node Group" and item["protocol_id"] == protocolId and item["name"].startswith(compute_host_name)  and item["user_name"] == user and item["pw"] == pw]
        else:
            compute_node_data_id = [item for item in hosts if item["host_type"] == "Compute Node Group" and item["protocol_id"] == protocolId and item["name"] == compute_host_name]
        
        if len(compute_node_data_id) == 0:
            # Genereate random Compute Group host name
            compute_node_name = f"{compute_host_name}_{len(hosts)+1}"
            response = create_compute_group(compute_node_name, protocolId, compute_ips, user, pw)
            if response == None:
                print("Error in creating Compute Group")
                return
            
            hosts = getHostByProtocol(protocolId)
            if protocol_name in ["CIFS", "iSCSI-Chap"]:        
                compute_node_data_id = [item for item in hosts if item["host_type"] == "Compute Node Group" and item["protocol_id"] == protocolId and item["name"] == compute_node_name and item["user_name"] == user and item["pw"] == pw]
            else:
                compute_node_data_id = [item for item in hosts if item["host_type"] == "Compute Node Group" and item["protocol_id"] == protocolId and item["name"] == compute_node_name] 
            
            compute_id = compute_node_data_id[0]["id"]
        else:
            compute_id = compute_node_data_id[0]["id"]


        compute_nodes = getComputeNodeByComputeGroup(compute_id)

        compute_node_ids = [host["id"] for host in compute_nodes]

        priority = 1

        print(f"\nCreating volume '{volumeName}' size {size} ...")

        print("Compute Node Ip's :",compute_ips)

        payload = {"volumeName" : volumeName,"size" : size,"protocolId" : protocolId, "priority" : priority,'computeId' : compute_id,"computeHost" : compute_node_ids}         
        response = requests.post(URL+"/sn_volume",json=payload).json()

        stop_event.set()
        loader_thread.join()
        
        volume_status = response.get("steps_info", {}).get("volume", {}).get("status")
        if volume_status:
            print("\nVolume Created Successfully On ....")
            print("Storage Node:", sNode)
            print("Pool Name:", response.get("pool_info", {}).get("pool", {}).get("systemName"))
            # print("Storage Group Name:", storage_group[0].get("name"))
            print("Compute Node Group Name:", compute_node_data_id[0].get("name"))
            print("\n")
        else:
            print("\nVolume Creation Failed",response.get("steps_info",{}).get("host",{}).get("message") or response.get("steps_info",{}).get("volume",{}).get("message"))
            print("\n")
            


    except Exception as e:
        stop_event.set()
        loader_thread.join()
        print(f"Exception in creating volume : {str(e)}")
    finally:
        stop_event.set()
        loader_thread.join()


def cmd_mount_volume(args):
    try:
        volumeName= args.name
        protocol_name = args.protocol
        protocolId = PROTOCOLS[protocol_name]

        volumes = readSDSVolumes()

        volume = [item for item in volumes if item[1] == volumeName and item[2] == protocolId]


        if len(volume) == 0:
            print(f"Volume '{volumeName}' not found on SDS DB.")
            return

        selected_volume = volume[0]
        volumeId = selected_volume[0]
        volumeType = selected_volume[15]
        controller_id = selected_volume[24]
    
        payload = {"controller_id" : controller_id,"volumeId" : volumeId,"volumeType" : volumeType,"state" : 6}

        stop_event = threading.Event()
        loader_thread = threading.Thread(target=spinner, args=("Mounting SDS Volume...", stop_event))
        loader_thread.start()

        response = requests.put(URL+"/onOff_SN_Volume",json=payload).json()
        
        stop_event.set()
        loader_thread.join()

        
        if not response.get("volume_on").get("status"):
            print("\nSDS Volume On Response :",response.get("volume_on").get("message"),"\n")
            return
        if(response.get("status")):
            print("\nVolume Mounted Successfully On ....")
            print("Volume Name : ",volumeName)
            for i in response.get("compute"):
                print("Compute Node IP : ",i.get("compute_node_ip"))
                print("Is Volume Mounted? : ", "Yes" if i.get("mount").get("status") else "No")
                print("Volume Mounted Path : ", i.get("mount").get("mount_path"))
        else:
            print("\nVolume Name : ",volumeName)
            for i in response.get("compute"):
                print("Compute Node IP : ",i.get("compute_node_ip"))
                print("Is Volume Mounted? : ", "Yes" if i.get("mount").get("status") else "No")
                print("Volume Mounted Path : ", i.get("mount").get("mount_path"))
                print("Error Message : ", i.get("mount").get("message"))
        print("\n")
    except Exception as e:
        print(f"Exception in mounting volume : {str(e)}")


def cmd_unmount_volume(args):
    try:
        volumeName= args.name
        protocol_name = args.protocol

        protocolId = PROTOCOLS[protocol_name]

        volumes = readSDSVolumes()

        volume = [item for item in volumes if item[1] == volumeName and item[2] == protocolId]


        if len(volume) == 0:
            print(f"Volume '{volumeName}' not found.")
            return

        selected_volume = volume[0]
        volumeId = selected_volume[0]
        volumeType = selected_volume[15]
        controller_id = selected_volume[24]

    
        payload = {"controller_id" : controller_id,"volumeId" : volumeId,"volumeType" : volumeType,"state" : 4}

        stop_event = threading.Event()
        loader_thread = threading.Thread(target=spinner, args=("Unmounting SDS Volume...", stop_event))
        loader_thread.start()

        response = requests.put(URL+"/onOff_SN_Volume",json=payload).json()
        
        stop_event.set()
        loader_thread.join()
        
        if not response.get("volume_on").get("status"):
            print("\nSDS Volume Off Response :",response.get("volume_on").get("message"),"\n")
            return
        
        if(response.get("status")):
            print("\nVolume Unmounted Successfully On ....")
            print("Volume Name : ",volumeName)
            for i in response.get("compute"):
                print("Compute Node IP : ",i.get("compute_node_ip"))
                print("Is Volume UnMounted? : ", "Yes" if i.get("mount").get("status") else "No")
                print("Volume Unmounted Path : ", i.get("mount").get("unmount_path"))
        else:
            print("\nVolume Name : ",volumeName)
            for i in response.get("compute"):
                print("Compute Node IP : ",i.get("compute_node_ip"))
                print("Is Volume UnMounted? : ", "Yes" if i.get("mount").get("status") else "No")
                print("Volume Unmounted Path : ", i.get("mount").get("unmount_path"))
                print("Error Message : ", i.get("mount").get("message"))
        print("\n")
    except Exception as e:
        print(f"Exception in mounting volume : {str(e)}")


def cmd_delete_volume(args):
    try:
        
        volumeName= args.name
        protocol_name = args.protocol

        protocolId = PROTOCOLS[protocol_name]

        volumes = readSDSVolumes()

        volume = [item for item in volumes if item[1] == volumeName and item[2] == protocolId]

        if len(volume) == 0:
            print(f"Volume '{volumeName}' not found.")
            return

        selected_volume = volume[0]
        volumeId = selected_volume[0]
        volumeType = selected_volume[15]    
        controller_id = selected_volume[24]

        payload = {"controller_id" : controller_id,"volumeId" : volumeId,"volumeType" : volumeType}
        
        stop_event = threading.Event()
        loader_thread = threading.Thread(target=spinner, args=("Deleting SDS Volume...", stop_event))
        loader_thread.start()

        response = requests.delete(URL+"/sn_volume",json=payload).json()

        stop_event.set()
        loader_thread.join()

        if response.get("status") == "fail":
            print("\nStorage Volume Not Deleted ")
            print("Message : ",response.get("description"))
            print("\n")
            return
        
        # print(f"\nStorage Volume Delete Response : {response}")
        print("\nVolume Deleted Successfully On ....")
        print("Volume Name : ",volumeName)
        print("Message : ",response.get("description"))
        print("Folder Deleted From Compute Node : ",'Yes' if response.get("compute",{}).get("status") == "success" else "No")
        print("Folder Deleted Path : ",response.get("compute",{}).get("local_path"))
        print("Folder Deleted Message : ",response.get("compute",{}).get("message"))
        print("\n")

    except Exception as e:
        print(f"Exception in deleting volume : {str(e)}")


# ---------------------------
# CLI Parser
# ---------------------------
def build_parser():
    parser = argparse.ArgumentParser(description="SDS CLI helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # sds create volume
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

    # sds mount volume
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

    # sds unmount volume
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

    if sys.platform.startswith("win"):
        flask_process = subprocess.Popen(
            [sys.executable, "computenode_service_client.py"]
        )
    else:    
        flask_process = subprocess.Popen(["python3", "computenode_service_client.py"]) 
    

    try:
        args.func(args)
    finally:
        flask_process.terminate()
        flask_process.wait()



if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)


# Helper command
# NFS - sudo python3 sdsClient.py create-volume --name vold1 --size 10 --Snode 192.168.30.20 --protocol NFS
# CIFS - sudo python3 sdsClient.py create-volume --name vold1 --size 10 --Snode 192.168.30.20 --protocol CIFS --user sanuyi --pw hello123
# ISCI - sudo python3 sdsClient.py create-volume --name vold1 --size 10 --Snode 192.168.30.20 --protocol iSCSI-Chap --user sanuyi --pw hello123
# ISCI No Chap - sudo python3 sdsClient.py create-volume --name vold1 --size 10 --Snode 192.168.30.20 --protocol iSCSI-NoChap --user sanuyi --pw hello123

# Mount - 
    # sudo python3 sdsClient.py on-volume --name vold1 --Snode 192.168.30.20 --protocol NFS
    # sudo python3 sdsClient.py on-volume --name vold1 --Snode 192.168.30.20 --protocol CIFS
    # sudo python3 sdsClient.py on-volume --name vold1 --Snode 192.168.30.20 --protocol iSCSI-Chap
    # sudo python3 sdsClient.py on-volume --name vold1 --Snode 192.168.30.20 --protocol iSCSI-NoChap

# Unmount - 
    # sudo python3 sdsClient.py off-volume --name vold1 --Snode 192.168.30.20 --protocol NFS
    # sudo python3 sdsClient.py off-volume --name vold1 --Snode 192.168.30.20 --protocol CIFS
    # sudo python3 sdsClient.py off-volume --name vold1 --Snode 192.168.30.20 --protocol iSCSI-Chap
    # sudo python3 sdsClient.py off-volume --name vold1 --Snode 192.168.30.20 --protocol iSCSI-NoChap

# Delete - 
    # sudo python3 sdsClient.py delete-volume --name vold1 --Snode 192.168.30.20 --protocol NFS
    # sudo python3 sdsClient.py delete-volume --name vold1 --Snode 192.168.30.20 --protocol CIFS
    # sudo python3 sdsClient.py delete-volume --name vold1 --Snode 192.168.30.20 --protocol iSCSI-Chap
    # sudo python3 sdsClient.py delete-volume --name vold1 --Snode 192.168.30.20 --protocol iSCSI-NoChap
