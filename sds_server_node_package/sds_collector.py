
import requests
import time
import os
import socket
import subprocess
from sds_globalSettings import AWS_TEST

FLASK_ADDRESS = "127.0.0.1" # Change the ip address where flask is running
PORT = 4000 # Change port according Flask Rest Api
URL = f"http://{FLASK_ADDRESS}:{PORT}"
flag_file = "/tmp/db_ready.flag"
INTERVAL = 1 * 60 


def get_public_ip():
    if AWS_TEST:
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
            try:
                s.connect(("10.255.255.255", 1))
                ip = s.getsockname()[0]
            except Exception:
                try:
                    # Linux fallback using hostname -I
                    result = subprocess.check_output(["hostname", "-I"]).decode().strip()
                    ip = result.split()[0]
 
                except Exception:
                    try:
                        ip = socket.gethostbyname(socket.gethostname())
                    except Exception:
                        ip = None
        finally:
            s.close()

        return ip

def send_storage_node_data(node_ip):
    try:
        print(f"send_storage_node_data {node_ip}")
        payload = {"node_ip" : node_ip}
        response = requests.post(URL+"/storage-nodes",json=payload)
        # print(f"Response for Node {node_ip} : {response.text}")
    except Exception as e:
        print(f"Exception in saving for {node_ip} remote data : {str(e)}")

def send_all_data():
    storage_ip = get_public_ip()
    if storage_ip is None:
        print("Could not determine storage node IP. Skipping data send.")
        return
    
    send_storage_node_data(storage_ip)
    time.sleep(0.5) # Small delay between requests

def sds_collector_manager():
    print("Waiting for DB to be ready...")
    while not os.path.exists(flag_file):
        time.sleep(1)
        
    print("DB is ready. Starting SDS_Collector logic.")
    while True:
        send_all_data()
        time.sleep(INTERVAL)


if __name__ == "__main__":
    sds_collector_manager()
    