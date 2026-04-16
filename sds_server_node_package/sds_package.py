import subprocess
import signal
import sys
import os
import atexit
from sds_globalSettings import SDS_SERVICE

processes = []

def cleanup():
    if os.path.exists("/tmp/db_ready.flag"):
        os.remove("/tmp/db_ready.flag")
        print("[CLEANUP] Removed db_ready.flag")

    for proc in processes:
        try:
            print(f"[CLEANUP] Killing process group for PID {proc.pid}")
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except Exception as e:
            print(f"[CLEANUP] Error killing PID {proc.pid}: {e}")

atexit.register(cleanup)

def signal_handler(sig, frame):
    print("\n[SIGNAL] Received termination signal. Stopping all...")
    cleanup()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def main():
    try:
        proc1 = subprocess.Popen(["python3", "/home/sanuyi/sds_workstation/sds_server_node_package/sds_launcher.py"], preexec_fn=os.setsid)
        proc2 = subprocess.Popen(["python3", "/home/sanuyi/san/sds_main.py"], preexec_fn=os.setsid)
        processes.extend([proc1, proc2])

        # Wait for both
        proc1.wait()
        proc2.wait()
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)

if __name__ == "__main__":
    if SDS_SERVICE == "Enabled":
        main()
    else:
        print("[INFO] SDS_SERVICE is disabled. Exiting.")
        sys.exit(0)
