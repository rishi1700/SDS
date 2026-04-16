from multiprocessing import Process
import signal
import sys

# Import the functions directly from your scripts
from sds_api_server import sds_manager
from sds_collector import sds_collector_manager

def signal_handler(sig, frame):
    print("\nReceived termination signal. Stopping...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def run_services():
    p1 = Process(target=sds_manager)
    p2 = Process(target=sds_collector_manager)

    p1.start()
    p2.start()

    p1.join()
    p2.join()

if __name__ == "__main__":
    run_services()
