import sys
import subprocess
try:
    import flask
except ImportError:
    print("The 'flask' module is not installed.")

    choice = input("Do you want to install it now? (y/n): ").strip().lower()
    if choice in ("y", "yes"):
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", "flask", "--ignore-installed", "blinker", "--break-system-packages"
            ])
            print("flask installed successfully. Restarting import...")
            import flask
        except subprocess.CalledProcessError:
            print("Failed to install 'flask'. Please install it manually.")
            sys.exit(1)
    else:
        print("Installation cancelled by user.")
        sys.exit(1)

from flask import Flask, request
import os
import time
import datetime
import socket
import json
import signal
import shutil

app = Flask(__name__)

HOST = '0.0.0.0' # Available for all
PORT = 4002      # Flask Port

SDS_VOLUME_MOUNT_PATH = "/mnt/"

def get_mount_base_path():
    if os.path.exists(SDS_VOLUME_MOUNT_PATH):
        return SDS_VOLUME_MOUNT_PATH
    return os.getcwd()


def _resolve_system_command(command_name):
    cmd = shutil.which(command_name)
    if cmd:
        return cmd
    for base in ("/usr/sbin", "/usr/bin", "/sbin", "/bin", "/usr/local/sbin", "/usr/local/bin"):
        candidate = os.path.join(base, command_name)
        if os.path.exists(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return command_name

def sprint (a,b=0):
    x=True
    if x==True:
        if b!=0:
            print(a,b)
            #loggerName="STCON_logger"
            #logger=STCON_logger
            #logger[0].info(loggerName+":"+str(a)+","+str(b))
        else:
            print(a)
            #loggerName="STCON_logger"
            #logger=STCON_logger
            #logger[0].info(loggerName+":"+str(a))

# ===============
# Supported Functions
# ===============
def get_free_window_drive_letter(volumeName, remote_ip):
    """
    Returns:
    - existing drive letter if volume already mounted
    - otherwise a new free drive letter
    """

    used = set()
    existing_drive = None

    try:
        result = subprocess.check_output(
            ["cmd", "/c", "net", "use"],
            universal_newlines=True
        )

        target = f"\\\\{remote_ip}\\{volumeName}".lower().rstrip("\\")

        for line in result.splitlines():
            parts = line.split()

            drive = None
            remote = None

            for p in parts:
                if p.endswith(":"):
                    drive = p
                elif p.startswith("\\\\"):
                    remote = p.lower().rstrip("\\")

            if drive:
                used.add(drive)

            if remote == target:
                existing_drive = drive

        if existing_drive:
            return existing_drive

    except Exception:
        pass

    # allocate new drive
    for letter in "ZYXWVUTSRQPONMLKJIHGFEDCBA":
        drive = letter + ":"
        if drive not in used:
            return drive

    return None


def run_powershell(cmd):
    return subprocess.check_output(
        ["powershell", "-Command", cmd],
        universal_newlines=True
    )


def find_mount_path(remote_ip, volume_name):
    # Read all exports from the remote server using showmount
    try:
        if sys.platform.startswith("win"):
            # Windows
            mount_path = f"\\\\{remote_ip}\\{volume_name}"
            sprint(f"Windows assumed mount path: {mount_path}","")
            return mount_path
        else:
            # Linux or Mac OS
            result = subprocess.run(
                [_resolve_system_command('showmount'), '-e', remote_ip],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                check=True
            )
            exports = result.stdout.strip().splitlines()
            for line in exports[1:]:
                export_path = line.split()[0]
                if os.path.basename(export_path) == volume_name:
                    sprint(f"Matched mount path: {export_path}")
                    return export_path
            sprint(f"No matching export found for volume: {volume_name}")
            return None
    except subprocess.CalledProcessError as e:
        sprint(f"Error running showmount: {e.stderr}")
        return None
    except FileNotFoundError:
        sprint("Required tool 'showmount' not found. Please install package 'nfs-common'.")
        return None
    except Exception as e:
        sprint("Exception in read mount path",e)
        return None
    
def create_mount_point(path):
    """Create the mount point if it doesn't exist."""
    wERC=0
    try:
      if not os.path.exists(path):
        if sys.platform.startswith("linux"):
            subprocess.run([_resolve_system_command("sudo"), "mkdir", "-p", path], check=True)
        else:
            os.makedirs(path)
        sprint(f"Created mount point: {path}")
        return wERC
      else:
        sprint(f"Mount point {path} already exists.")
        return wERC
        
        
    except subprocess.CalledProcessError as e:
      if sys.platform.startswith("linux"):
        sprint(f"create mount point except: Unable to create {path}. Please run the app with permission to write there or create the folder manually. ({e})")
      else:
        sprint(f"create mount point except: {e}")
      return -1
    except Exception as e:
      sprint(f"create mount point except: {e}")
      return -1
    
def ping_host(host, timeout=2,max_retries=1):
    """Ping the host until it responds or until max retries are reached."""
    retries = 0
    while retries < max_retries:
        # Ping the host
        if sys.platform.startswith("win"): # Windows
            cmd = ["ping", "-n", "4", host]
        else: # Linux or Mac
            cmd = ["ping", "-c", "4", host]

        response = subprocess.run(cmd, stdout=subprocess.PIPE)
        
        if response.returncode == 0:
            sprint(f"{host} is reachable.")
            return True
        else:
            sprint(f"{host} is not reachable. Retrying in {timeout} seconds... ({retries + 1}/{max_retries})")
            time.sleep(timeout)
            retries += 1
    sprint(f"{host} is not reachable after {max_retries} retries.")
    return False

def find_window_drive_by_volume(volume_name, protocol_name):
    try:
        if protocol_name == "CIFS":
            result = subprocess.check_output(
                ["cmd", "/c", "net", "use"],
                universal_newlines=True
            )

            for line in result.splitlines():
                if volume_name.lower() in line.lower():
                    parts = line.split()
                    for p in parts:
                        if p.endswith(":"):
                            return p
            return None
        else:
            return None
        
    except Exception:
        return None
    
def find_iscasi_target_iqn(remote_ip, volume_name):

    iqn = None
    try:
        # Step 1: Discover targets
        # sudo iscsiadm -m discovery -t sendtargets -p 192.168.30.20

        discover_cmd = ["iscsiadm", "-m", "discovery", "-t", "sendtargets", "-p", remote_ip]
        process1 = subprocess.check_output(discover_cmd)

        # Step 2: Parse IQN from discovery output
        for line in process1.decode().splitlines():
            if remote_ip in line and volume_name.lower() in line.lower():
                parts = line.split()

                if len(parts) >= 2:
                    iqn = parts[1].strip()
    except subprocess.CalledProcessError:
        pass


    # --------------------------------
    # STEP 2: SESSION (fallback)
    # --------------------------------
    try:
        out = subprocess.check_output(
            ["iscsiadm", "-m", "session"],
            stderr=subprocess.DEVNULL,
            universal_newlines=True
        )

        for line in out.splitlines():
            # Example:
            # tcp: [12] 192.168.30.20:3260,1 iqn.xxx:volumeName (non-flash)
            if remote_ip in line and volume_name.lower() in line.lower():
                parts = line.split()
                iqn = parts[3].strip()
                return 0, iqn

    except subprocess.CalledProcessError:
        pass

    if not iqn:
        sprint(f"IQN Not Found in discovery output {remote_ip} {volume_name}")
        return -1, None
    
    sprint("Extracted IQN", iqn)
    
    return 0, iqn

def is_mounted(path):
    try:
        if sys.platform.startswith("darwin"):
            result = subprocess.run(
                ["mount"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True
            )
            return path in result.stdout
        else:
            # os.path.ismount raises OSError (ESTALE) for stale NFS mounts,
            # so also check /proc/mounts directly.
            try:
                if os.path.ismount(path):
                    return True
            except OSError:
                pass
            norm = os.path.normpath(path)
            try:
                with open("/proc/mounts") as f:
                    for line in f:
                        parts = line.split()
                        if len(parts) >= 2 and os.path.normpath(parts[1]) == norm:
                            return True
            except Exception:
                pass
            return False
    except Exception:
        return False


def wait_until_unmounted(path, retries=10, delay=0.3):
    for _ in range(retries):
        if not is_mounted(path):
            return True
        time.sleep(delay)
    return not is_mounted(path)
    
def get_iscsi_windwos_iqn_by_volume(volume_name):
    """
        Get the IQN for a volume on Windows using iscsicli.
    """

    out = subprocess.check_output(
        ["iscsicli", "ListTargets"],
        universal_newlines=True
    )

    iqn = None
    for line in out.splitlines():
        if volume_name.lower() in line.lower():
            iqn = line.strip()
            break

    if not iqn:
        return -1
    
    return iqn

def iscsi_session_exists(iqn):
    """
        Linux or Mac OS
        Check if an iSCSI session exists for the given IQN .
    """
    try:
        out = subprocess.check_output(
            ["iscsiadm", "-m", "session"],
            stderr=subprocess.DEVNULL
        ).decode()

        return iqn in out
    except subprocess.CalledProcessError:
        return False

def get_block_devices():
    import subprocess

    out = subprocess.check_output(
        ["lsblk", "-dn", "-o", "NAME,TYPE"],
        universal_newlines=True
    )

    devices = set()

    for line in out.splitlines():
        name, typ = line.split()
        if typ == "disk":
            devices.add(name)

    return devices

def get_mac_disks():
    out = subprocess.check_output(
        ["diskutil", "list"],
        universal_newlines=True
    )
    disks = set()
    for line in out.splitlines():
        # /dev/disk4 (external, physical)
        if line.startswith("/dev/disk"):
            disks.add(line.split()[0])
    return disks

def check_mac_atto_cli():
    paths = [
        "/Applications/ATTO/ConfigTool/attoconfig",
        "/Applications/ATTO/ATTO Config Tool.app/Contents/MacOS/attoconfig"
    ]

    for p in paths:
        if os.path.exists(p) and os.access(p, os.X_OK):
            return 0, p

    return -1, "ATTO Config Tool not found"

def ensure_iscsid_running():
    try:
        # Check service status
        result = subprocess.run(
            ["systemctl", "is-active", "iscsid"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True
        )

        if result.stdout.strip() == "active":
            return 0

        # If not active → start it
        subprocess.check_output(["sudo", "systemctl", "start", "iscsid"])
        subprocess.check_output(["sudo", "systemctl", "enable", "iscsid"])

        return 0

    except Exception as e:
        sprint(f"Exception in ensure_iscsid_running: {e}")
        return -1


# ==============
# Show CIFS Mount 
# ==============


def ShowCifsMount(host_iqn,share,user,password):
    msg=str(host_iqn)+" "+str(share)+" "+str(user)+" "+str(password)
    sprint ("ShowCifsMount",msg)
    #smbclient --option='client min protocol=SMB2' -L 192.168.30.16 -U sanuyi%hello123 -g
    arg1="-L"
    arg2=host_iqn
    arg3="-U"
    arg4=user+"%"+password
    arg5="-g"
    arg6='--option='
    arg7="'client min protocol=SMB2'"
    try:
        if sys.platform.startswith("win"):
            # Windows
            sprint("Windows cannot list CIFS shares remotely")
            return 0 
        
        else:
            # Linux or Mac
            process1 = subprocess.check_output(["smbclient",arg6,arg7,arg1,arg2,arg3,arg4,arg5])
            sprint (process1,0)
            if process1.find(share)!=-1:
                sprint ("CIFS mnt exported",msg)
                status=0
            else:
                status=-1
                sprint ("CIFS mnt NOT exported",msg)
    except Exception as err:
        sprint ("ShowCifsMount except",msg)
        return -1
        
    return status

# ==============
# Show iSCSI Mount
# ==============


def ShowiSCSIChapMount(remote_ip, user, password, ip, volume_name):
    msg = f"{remote_ip} {user} {password} {ip}"
    sprint("ShowiSCSIChapMount", msg)

    try:

        if sys.platform.startswith("win"):
            # Windows

            # Configure the service
            subprocess.run(["powershell", "-Command", "Set-Service MSiSCSI -StartupType Automatic"])
            sprint("ISCSI Service configured")

            # Start the service
            subprocess.run(["powershell", "-Command", "Start-Service MSiSCSI"])

            sprint("ISCSI Service started")

            # Portal
            run_powershell(f"New-IscsiTargetPortal -TargetPortalAddress {remote_ip} -ErrorAction SilentlyContinue")

            # List targets
            out = subprocess.check_output(
                ["iscsicli", "ListTargets"],
                universal_newlines=True
            )

            iqn = None
            for line in out.splitlines():
                if volume_name.lower() in line.lower():
                    iqn = line.strip()
                    break

            if not iqn:
                sprint("Windows IQN not found", msg)
                return -1, None

            sprint(f"Windows Extracted IQ for volume : {volume_name}, Remote IP : {remote_ip} -> IQN : {iqn}","")
            

            # Set CHAP credentials
            try:
                run_powershell(f'Connect-IscsiTarget -NodeAddress "{iqn}" -IsPersistent $true')

                subprocess.run(["iscsicli", "AddTargetPortal", remote_ip], stdout=subprocess.DEVNULL)
            except subprocess.CalledProcessError:
                pass

            sprint("Windows CHAP settings applied", msg)

            return 0, iqn

        elif sys.platform.startswith("darwin"):

            status, ATTO = check_mac_atto_cli()
            if not status:
                sprint("macOS ATTO not found", ATTO)
                return -1

            # Discover targets
            out = subprocess.check_output(
                [ATTO, "iscsi", "listtargets"],
                universal_newlines=True
            )

            iqn = None
            for line in out.splitlines():
                if volume_name.lower() in line.lower():
                    iqn = line.strip()
                    break

            if not iqn:
                sprint("macOS IQN not found", volume_name)
                return -1, None

            # Set CHAP
            subprocess.check_output([
                ATTO, "iscsi", "chap",
                "--target", iqn,
                "--user", user,
                "--password", password
            ])

            # Login
            subprocess.check_output([
                ATTO, "iscsi", "login",
                "--target", iqn,
                "--address", remote_ip
            ])

            sprint("macOS iSCSI login success", iqn)
            return 0, iqn
        
        else:
            # Linux
        
            status, iqn = find_iscasi_target_iqn(remote_ip, volume_name)
            if status != 0:
                return -1, None    

            # Step 3: CHAP authentication settings
            cmd_auth = [
                ["sudo", "iscsiadm", "-m", "node", "-T", iqn, "-p", remote_ip, "--op", "update",
                "-n", "node.session.auth.authmethod", "-v", "CHAP"],
                ["sudo", "iscsiadm", "-m", "node", "-T", iqn, "-p", remote_ip, "--op", "update",
                "-n", "node.session.auth.username", "-v", user],
                ["sudo", "iscsiadm", "-m", "node", "-T", iqn, "-p", remote_ip, "--op", "update",
                "-n", "node.session.auth.password", "-v", password]
            ]

            for cmd in cmd_auth:
                subprocess.check_output(cmd)
                sprint("Executed", " ".join(cmd))

            sprint("iSCSI CHAP Settings Applied", msg)

            return 0, iqn   # RETURN IQN HERE

    except Exception as err:
        sprint("ShowiSCSIChapMount except", f"{msg} Error: {err}")
        return -1, None


# ==============
# Show iSCSI No Chap Mount 
# ==============

def ShowiSCSINoChapMount(remote_ip, ip,volume_name):
    msg = f"{remote_ip} {ip}"
    sprint("ShowiSCSINoChapMount", msg)

    try:
        if sys.platform.startswith("win"):
            # Configure the service
            subprocess.run(["powershell", "-Command", "Set-Service MSiSCSI -StartupType Automatic"])
            sprint("ISCSI Service configured")

            # Start the service
            subprocess.run(["powershell", "-Command", "Start-Service MSiSCSI"])

            sprint("ISCSI Service started")

            # Portal
            run_powershell(f"New-IscsiTargetPortal -TargetPortalAddress {remote_ip} -ErrorAction SilentlyContinue")
            
            sprint("Windows iSCSI portal added", remote_ip)

            # List targets
            out = subprocess.check_output(
                ["iscsicli", "ListTargets"],
                universal_newlines=True
            )

            iqn = None
            for line in out.splitlines():
                if volume_name.lower() in line.lower():
                    iqn = line.strip()
                    break

            if not iqn:
                sprint("Windows IQN not found", msg)
                return -1, None

            sprint(f"Windows Extracted IQ for volume : {volume_name}, Remote IP : {remote_ip} -> IQN : {iqn}","")

            try:
                subprocess.run(["iscsicli", "AddTargetPortal", remote_ip], stdout=subprocess.DEVNULL)
            except subprocess.CalledProcessError as e:
                print(e)
                pass

            sprint("Windows NoCHAP settings applied", msg)

            return 0, iqn
        
        elif sys.platform.startswith("darwin"):

            status, ATTO = check_mac_atto_cli()
            if not status:
                sprint("macOS ATTO not found", ATTO)
                return -1

            # Discover targets
            out = subprocess.check_output(
                [ATTO, "iscsi", "listtargets"],
                universal_newlines=True
            )

            iqn = None
            for line in out.splitlines():
                if volume_name.lower() in line.lower():
                    iqn = line.strip()
                    break

            if not iqn:
                sprint("macOS IQN not found", volume_name)
                return -1, None

            # Set CHAP
            subprocess.check_output([
                ATTO, "iscsi", "chap",
                "--target", iqn,
            ])

            # Login
            subprocess.check_output([
                ATTO, "iscsi", "login",
                "--target", iqn,
                "--address", remote_ip
            ])

            sprint("macOS iSCSI login success", iqn)
            return 0, iqn

        else:
            # Linux
        
            status, iqn = find_iscasi_target_iqn(remote_ip, volume_name)
            if status != 0:
                return -1, None    

            # Step 3: CHAP authentication settings
            cmd_auth = [
                ["sudo", "iscsiadm", "-m", "node", "-T", iqn, "-p", remote_ip, "--op", "update",
                "-n", "node.session.auth.authmethod", "-v", "CHAP"],
            ]

            for cmd in cmd_auth:
                subprocess.check_output(cmd)
                sprint("Executed", " ".join(cmd))

            sprint("iSCSI CHAP Settings Applied", msg)

            return 0, iqn   # RETURN IQN HERE

    except Exception as err:
        sprint("ShowiSCSINoChapMount Exception", f"{msg} Error: {err}")
        return -1, None

# ==============
# Mount NFS
# ==============


def mount_nfs(remote_ip, remote_path, local_path, protocol,wait_time=5):
    try: 
        protocol = protocol.lower()
        """Mount the NFS volume."""
        time.sleep(wait_time)
        if sys.platform.startswith("win"):
            # Windows
            if os.path.exists(local_path):
                sprint("Drive already exists")
                return -1

            mount_cmd = [
                "cmd", "/c",
                "net", "use",
                f"{remote_ip}:{remote_path}",
                local_path
            ]
        elif sys.platform.startswith("darwin"):
            # macOS
            if os.path.ismount(local_path):
                return -1
            mount_cmd = ["mount_nfs","-o", "nolocks,soft,timeo=30,vers=3",f"{remote_ip}:{remote_path}",local_path]
        elif sys.platform.startswith("linux"):
            # Linux
            if os.path.ismount(local_path):
                return -1
            mount_cmd = ['sudo', 'mount', '-t', protocol,'-o','soft,bg,timeo=30,fsc', f'{remote_ip}:{remote_path}', local_path]
        else:
            raise RuntimeError("Unsupported OS")
        subprocess.run(mount_cmd)
        sprint(f"Trying to mount {protocol} volume {remote_ip}:{remote_path} to {local_path}")
        return 0
    except Exception as e:
        sprint(f"Unable to mount share: {e}")
        return -1

# ==============
# Mount CIFS
# ==============


def mount_cifs(remote_ip, remote_path, loc_path, protocol,user,password,wait_time=5):
    try: 
        protocol = protocol.lower()
        """Mount the CIFS volume."""
        time.sleep(wait_time)
        sprint (f'mount_cifs arguments {remote_ip}, {remote_path}, {loc_path}, {protocol}')
        try:
            if sys.platform.startswith("win"):
                # Windows
                cmd = [
                    "cmd", "/c",
                    "net", "use",
                    loc_path,
                    f"\\\\{remote_ip}\\{remote_path}",
                    password,
                    f"/user:{user}"
                ]

                subprocess.run(cmd, check=True)
                sprint("CIFS mounted on Windows")
                return 0
            
        
            elif sys.platform.startswith("darwin"):
                # Mac OS
                if os.path.ismount(loc_path):
                    return -1
                command = f"mount_smbfs //{user}:{password}@{remote_ip}/{remote_path} {loc_path}"
            elif sys.platform.startswith("linux"):
                # Linux
                # arg0=" -t cifs -o username=guest -o password=hello123 //192.168.30.6/cifs1 /mnt/remote/mnt/cifs1"

                if os.path.ismount(loc_path):
                    return -1
                arg1='-t cifs '
                arg4=' -o username='
                arg5='password='
                remote=' //'+remote_ip+'/'+remote_path
                local_path=' '+loc_path
                extra_perms = 'uid=$(id -u),gid=$(id -g),file_mode=0777,dir_mode=0777,vers=3.0'
                arg0=str(arg1)+" "+str(arg4)+str(user)+","+str(arg5)+str(password)+","+str(extra_perms)+" "+str(remote)+" "+str(local_path)
                # sprint ("mount_cifs arg0",arg0)
                command='mount '+arg0

            sprint (command,0)
            # Retry loop: storage node may still be setting up the Samba share
            # when cmd_mount_volume (state=6) returns, so the first attempt can
            # fail with "does not exist". Retry a few times before giving up.
            _MAX_CIFS_RETRIES = 4
            _CIFS_RETRY_DELAY = 5  # seconds between retries
            for _attempt in range(_MAX_CIFS_RETRIES):
                p = subprocess.Popen([command],shell=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
                output = p.stdout.read()
                p.wait()
                sprint(output, 0)
                if p.returncode == 0:
                    break
                sprint(f"CIFS mount command failed with exit code {p.returncode}", 0)
                if b"does not exist" in output and _attempt < _MAX_CIFS_RETRIES - 1:
                    sprint(f"CIFS share not ready, retrying in {_CIFS_RETRY_DELAY}s (attempt {_attempt+1}/{_MAX_CIFS_RETRIES})", 0)
                    time.sleep(_CIFS_RETRY_DELAY)
                else:
                    return -1
            # Verify the mount actually succeeded
            if os.path.ismount(loc_path):
                return 0
            sprint(f"CIFS mount command ran but {loc_path} is not a mountpoint", 0)
            return -1
        except Exception as err:
            #https://linux.die.net/man/8/mount.cifs
            sprint ("DeviceConnectCIFS except",err)
            sprint ((json.JSONEncoder().encode({'status':'fail','description':'invalid remote directory'})),0)
            # process1 = subprocess.check_output(["rmdir",arg4])
            return -1
 
    except Exception as e:
       sprint(f"Unable to mount share: {e}")
       return -1

# ==============
# Mount iSCSI
# ==============


def mount_iscsi_chap(remote_ip, local_mnt_path, iqn, user, password, volume_name, wait_time):
    msg = f"{remote_ip} {local_mnt_path} {iqn} {wait_time}"
    sprint("mount_iscsi_chap", msg)

    try:
        # Windows mount
        if sys.platform.startswith("win"):
            # login
            subprocess.check_output([
                "iscsicli",
                "CHAPSecret",
                iqn,
                user,
                password
            ])

            sprint("Windows iSCSI login success", iqn)
            # Trigger storage rescan so Windows enumerates the new disk immediately
            try:
                run_powershell("Update-HostStorageCache")
            except Exception:
                pass
            return 0

        elif sys.platform.startswith("darwin"):
            # ============================
            # macOS iSCSI via ATTO
            # ============================

            status, ATTO = check_mac_atto_cli()
            if not status:
                sprint("macOS ATTO not found", ATTO)
                return -1

            # ----------------------------
            # 0. disks BEFORE login
            # ----------------------------
            before_disks = get_mac_disks()
            sprint("macOS disks before login", before_disks)

            # ----------------------------
            # 1. Discover targets
            # ----------------------------
            out = subprocess.check_output(
                [ATTO, "iscsi", "listtargets"],
                universal_newlines=True
            )

            iqn_found = None
            for line in out.splitlines():
                if volume_name.lower() in line.lower():
                    iqn_found = line.strip()
                    break

            if not iqn_found:
                sprint("macOS iSCSI target not found", volume_name)
                return -1

            sprint("macOS IQN detected", iqn_found)

            # ----------------------------
            # 2. Set CHAP
            # ----------------------------
            subprocess.check_output([
                ATTO, "iscsi", "chap",
                "--target", iqn_found,
                "--user", user,
                "--password", password
            ])

            sprint("macOS CHAP configured", iqn_found)

            # ----------------------------
            # 3. Login target
            # ----------------------------
            subprocess.check_output([
                ATTO, "iscsi", "login",
                "--target", iqn_found,
                "--address", remote_ip
            ])

            sprint("macOS iSCSI login success", iqn_found)

            # ----------------------------
            # 4. Wait for disk
            # ----------------------------
            time.sleep(int(wait_time))

            # ----------------------------
            # 5. disks AFTER login
            # ----------------------------
            after_disks = get_mac_disks()
            sprint("macOS disks after login", after_disks)

            new_disks = after_disks - before_disks

            if not new_disks:
                sprint("No new disk appeared after ATTO login", "")
                return -1

            # only newly created disk
            disk = list(new_disks)[0]

            sprint("Detected macOS iSCSI disk", disk)

            # ----------------------------
            # 6. Format if needed
            # ----------------------------
            fs = subprocess.run(
                ["diskutil", "info", disk],
                stdout=subprocess.PIPE,
                text=True
            )

            if "Filesystem Type" not in fs.stdout:
                sprint("Formatting APFS", disk)
                subprocess.check_call([
                    "diskutil", "eraseDisk", "APFS", volume_name, disk
                ])

            # ----------------------------
            # 7. Mount
            # ----------------------------
            subprocess.check_call(["diskutil", "mount", "-mountDisk", local_mnt_path, disk])

            sprint("macOS Mount SUCCESS", disk)
            return 0


        
        else:
            # Ubunut/Linix OS

            before_disks = get_block_devices()
            sprint("Disks before login", before_disks)
        
            if not iscsi_session_exists(iqn):
                # Login using the REAL IQN
                login_cmd = ["sudo", "iscsiadm", "-m", "node", "-T", iqn, "-p", remote_ip, "--login"]
                login_out = subprocess.check_output(login_cmd)
                sprint("Login Output", login_out)

            # Wait for device to appear
            time.sleep(int(wait_time))

            after_disks = get_block_devices()
            sprint("Disks after login", after_disks)

            # Detect new iscsi block device
            lsblk_out = subprocess.check_output(["lsblk", "-r", "-o", "NAME,TYPE"])
            sprint("lsblk Output", lsblk_out)

            new_disks = after_disks - before_disks

            if not new_disks:
                sprint("No new iSCSI disk detected", "")
                return -1

            disk_name = list(new_disks)[0]
            
            device_path = f"/dev/{disk_name}"

            sprint("Detected iSCSI Device", device_path)

            try:
                subprocess.check_output(["blkid", device_path])
            except subprocess.CalledProcessError:
                sprint("Formatting new iSCSI disk", device_path)
                subprocess.check_call(["mkfs.ext4", device_path])

            # Mount the device
            subprocess.check_call(["mount", device_path, local_mnt_path])

            sprint("Mount SUCCESS", f"{device_path} → {local_mnt_path}")
            return 0

    except Exception as err:
        sprint("mount_iscsi_chap Exception", f"{msg} Error: {err}")
        return -1


# ==============
# Mount iSCSI No CHAP
# ==============

def mount_iscsi_nochap(remote_ip, local_mnt_path, iqn, wait_time):
    msg = f"{remote_ip} {local_mnt_path} {iqn} {wait_time}"
    sprint("mount_iscsi_nochap", msg)

    try:
        if sys.platform.startswith("win"):
            # login
            subprocess.check_output([
                "iscsicli",
                "QLoginTarget",
                iqn,
            ])

            time.sleep(int(wait_time))

            # bring disk online + format handled separately
            sprint("Windows iSCSI No Chap login success", iqn)
            # Trigger storage rescan so Windows enumerates the new disk immediately
            try:
                run_powershell("Update-HostStorageCache")
            except Exception:
                pass
            return 0
        
        elif sys.platform.startswith("darwin"):
            # macOS

            status, ATTO = check_mac_atto_cli()
            if not status:
                sprint("macOS ATTO not found", ATTO)
                return -1

            # ----------------------------
            # 1. disks BEFORE login
            # ----------------------------
            before_disks = get_mac_disks()
            sprint("macOS disks before login", before_disks)

            # ----------------------------
            # 2. ATTO login (NO CHAP)
            # ----------------------------
            subprocess.check_output([
                ATTO, "iscsi", "login",
                "--target", iqn,
                "--address", remote_ip
            ])

            sprint("macOS iSCSI No-CHAP login success", iqn)

            # ----------------------------
            # 3. wait for device
            # ----------------------------
            time.sleep(int(wait_time))

            # ----------------------------
            # 4. disks AFTER login
            # ----------------------------
            after_disks = get_mac_disks()
            sprint("macOS disks after login", after_disks)

            new_disks = after_disks - before_disks

            if not new_disks:
                sprint("No new disk appeared after iSCSI login", "")
                return -1

            # only new disk
            disk = list(new_disks)[0]
            sprint("Detected macOS iSCSI disk", disk)

            # ----------------------------
            # 5. Mount disk
            # ----------------------------
            subprocess.check_call(["diskutil", "mount", "-mountDisk", local_mnt_path, disk])

            sprint("macOS iSCSI No-CHAP mount SUCCESS", disk)
            return 0

        
        else:
            # Ubunut/Linix OS
            before_disks = get_block_devices()
            sprint("Disks before login", before_disks)
        
            if not iscsi_session_exists(iqn):
                # Login using the REAL IQN
                login_cmd = ["sudo", "iscsiadm", "-m", "node", "-T", iqn, "-p", remote_ip, "--login"]
                login_out = subprocess.check_output(login_cmd)
                sprint("Login Output", login_out)

            # Wait for device to appear
            time.sleep(int(wait_time))

            after_disks = get_block_devices()
            sprint("Disks after login", after_disks)

            # Detect new iscsi block device
            lsblk_out = subprocess.check_output(["lsblk", "-r", "-o", "NAME,TYPE"])
            sprint("lsblk Output", lsblk_out)

            new_disks = after_disks - before_disks

            if not new_disks:
                sprint("No new iSCSI disk detected", "")
                return -1

            disk_name = list(new_disks)[0]
            
            device_path = f"/dev/{disk_name}"

            sprint("Detected iSCSI Device", device_path)

            try:
                subprocess.check_output(["blkid", device_path])
            except subprocess.CalledProcessError:
                sprint("Formatting new iSCSI disk", device_path)
                subprocess.check_call(["mkfs.ext4", device_path])

            # Step 4: Mount the device
            subprocess.check_call(["mkdir", "-p", local_mnt_path])
            subprocess.check_call(["mount", device_path, local_mnt_path])

            sprint("Mount SUCCESS", f"{device_path} → {local_mnt_path}")
            return 0

    except Exception as err:
        sprint("mount_iscsi_nochap Exception", f"{msg} Error: {err}")
        return -1


# ==============
# Mount Process functions
# ==============
            
def mount_process(volumeName, protcol_name,remote_ip, host_name, user_name, ip, password, wwn, url):
    error_message = ""
    if sys.platform.startswith("win"): # Windows
        if protcol_name == "CIFS":
            local_mnt_path = get_free_window_drive_letter(volumeName, remote_ip)
            sprint("local_mnt_path",local_mnt_path)
        else:
            Mount_Path = get_mount_base_path()
            local_mnt_path=os.path.join(Mount_Path, volumeName)
    else: # Linux or Mac
        Mount_Path = get_mount_base_path()
        local_mnt_path=os.path.join(Mount_Path, volumeName)

        if protcol_name in ["iSCSI-Chap","iSCSI-NoChap"] and sys.platform.startswith("linux"):
            res = ensure_iscsid_running()
            if res != 0:
                sprint("iscsid service is not running", "")
                return -1, "iscsid service is not running"

    drop=False
    if drop ==True:
        os.system("echo 1 > /proc/sys/vm/drop_caches")
        os.system("echo 2 > /proc/sys/vm/drop_caches")
        os.system("echo 3 > /proc/sys/vm/drop_caches")
    
    wait_time = 5 
    max_retries = 5
    myTries=0
    waitPing=True
    while (waitPing):
        if ping_host(remote_ip, max_retries=max_retries):
            waitPing=False
        else:
            time.sleep(2)
            waitPing=False
            sprint("Unable to mount volume because the StorageArray is not reachable.")
            return -1

    waitPing=True
    try:
        if not sys.platform.startswith("win"):
            command = ["sync", local_mnt_path]
            result = subprocess.run(command, check=True)
            sprint(result)

        if sys.platform.startswith("darwin"):
            command =  ["sudo", "unmount", "force", local_mnt_path]
        elif sys.platform.startswith("linux"):
            command = ["umount","-lf",  local_mnt_path]
        elif sys.platform.startswith("win"):
            if protcol_name == "CIFS":
                drive = local_mnt_path.rstrip("\\/")
                command = ["cmd", "/c", "net", "use", drive, "/delete", "/y"]
            else:
                command = []
        else:
            raise RuntimeError("Unsupported OS")
        
        if len(command) > 0:
            result = subprocess.run(command, check=True)
            sprint (result)
    except Exception as e:
        sprint(f"sync mount Error1: {e}")
    
    # Create mount folder to client server
    try: 
        if sys.platform.startswith("win"):
            pass
        else:
            res=create_mount_point(local_mnt_path)
            if res==0:
                sprint ("local mount point mounted",local_mnt_path)
                
    except Exception as e:
        sprint(f"sync mount Error2: {e}")
      
    while (waitPing==True and  protcol_name=='NFS'):
        remote_path = find_mount_path(remote_ip, volumeName)
        if not remote_path:
            sprint(f"Could not determine mount path for volume: {volumeName}")
            return -1, "Could not determine mount path for volume: "+volumeName, error_message
        res=mount_nfs(remote_ip, remote_path, local_mnt_path, protcol_name,wait_time)
        if res==0:
            waitPing=False
            sprint("NFS volume mount")
        else:
            waitPing = True
            error_message = "Unable to mount NFS volume."
            sprint(f"Unable to mount NFS volume.{res}",myTries)
            time.sleep(2)
            myTries=myTries+1
            return -1, local_mnt_path, error_message
    while (waitPing==True and  protcol_name=='CIFS'):
        share=volumeName
        user=user_name
        password=password
        res=ShowCifsMount(remote_ip,share,user,password)
        
        res=mount_cifs(remote_ip, share, local_mnt_path, protcol_name,user,password,wait_time)
        if res==0:
            waitPing=False
            sprint("CIFS volume mount")
        else:
            waitPing = True
            error_message = "Unable to mount CIFS volume."
            sprint(f"Unable to mount CIFS volume.{res}",myTries)
            time.sleep(2)
            myTries=myTries+1
            return -1, local_mnt_path, error_message
    
    while (waitPing==True and  protcol_name=='iSCSI-Chap'):
        status, iqn = ShowiSCSIChapMount(remote_ip,user_name,password, ip,volumeName)
        if status == 0 and iqn:
            res = mount_iscsi_chap(remote_ip, local_mnt_path, iqn, user_name, password, volumeName, wait_time)
            if res==0:
                local_mnt_path = "Session Logged in successfully"
                waitPing=False
                sprint("iSCSI Chap volume mount called","")
            else:
                waitPing = True
                local_mnt_path = "Unable to mount iSCSI Chap volume."
                error_message = "Unable to mount iSCSI Chap volume."
                sprint(f"Unable to mount iSCSI Chap volume.{res}",myTries)
                time.sleep(2)
                myTries=myTries+1
                return -1, error_message
        else:
            error_message = "Failed in CHAP or IQN not found"
            sprint(error_message,"")
            return -1, local_mnt_path, error_message

    
    while (waitPing==True and  protcol_name=='iSCSI-NoChap'):
        status, iqn = ShowiSCSINoChapMount(remote_ip,ip,volumeName)
        if status == 0 and iqn:
            res= mount_iscsi_nochap(remote_ip,local_mnt_path, iqn,wait_time)

            if res==0:
                waitPing=False
                sprint("iSCSI No Chap volume mount called")
            else:
                waitPing = True
                error_message = "Unable to mount iSCSI No chap volume."
                sprint(f"Unable to mount iSCSI No chap volume.{res}",myTries)
                time.sleep(2)
                myTries=myTries+1
                return -1, error_message
        else:
            error_message = "Failed in CHAP or IQN not found"
            sprint(error_message,"")
            return -1, local_mnt_path, error_message
        
    if res==0:
        sprint ("write completed correctly") 
        return 0, local_mnt_path, error_message
    else:
        sprint ("write completed in-correctly")
        return -1, local_mnt_path, error_message
    

# ==============
# Unmount Process functions
# ==============


def unmount_process(volumeName, remote_ip, protocol, user_name, password, ip):
    try: 
        # Windows
        if sys.platform.startswith("win"):
            if protocol == "CIFS":
                local_path = find_window_drive_by_volume(volumeName,protocol)
                return 0, local_path
            
            if protocol in ("iSCSI-Chap", "iSCSI-NoChap"):
                
                # Find IQN by volume
                iqn = get_iscsi_windwos_iqn_by_volume(volumeName)

                # logout target
                if iqn:
                    sprint(f"IQN Found for {volumeName}:{remote_ip}", iqn)
                    
                    run_powershell(f"Disconnect-IscsiTarget -NodeAddress {iqn} -Confirm:$false")

                    subprocess.run(
                        ["iscsicli", "RemovePersistentTarget", iqn],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    return 0, "iSCSI session logged out"
                else:
                    return -1, "iSCSI session not logged out"

            else:
                return -1, "Unsupported protocol"

        else:
            # Ubuntu/Linux and Mac OS

            Mount_Path = get_mount_base_path()
            local_path=os.path.join(Mount_Path, volumeName) #Client mount path
            sprint("local_path",local_path)    
            """Un Mount the NFS volume."""

            if protocol in ("iSCSI-Chap", "iSCSI-NoChap"):

                if sys.platform.startswith("darwin"):

                    status, ATTO = check_mac_atto_cli()
                    if not status:
                        sprint("macOS ATTO not found", ATTO)
                        return -1

                    # 1. Unmount disk
                    subprocess.run(
                        ["diskutil", "unmountDisk", "force", local_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )

                    # 2. Find IQN via ATTO
                    out = subprocess.check_output(
                        [ATTO, "iscsi", "listsessions"],
                        universal_newlines=True
                    )

                    iqn = None
                    for line in out.splitlines():
                        if volumeName.lower() in line.lower():
                            iqn = line.strip()
                            break

                    if not iqn:
                        sprint("macOS iSCSI session not found", volumeName)
                        return -1, local_path

                    # 3. Logout iSCSI
                    subprocess.check_output([
                        ATTO, "iscsi", "logout",
                        "--target", iqn
                    ])

                    sprint("macOS iSCSI session logged out", iqn)
                    return 0, local_path
                else:

                    status, iqn = find_iscasi_target_iqn(remote_ip, volumeName)
                    if status != 0:
                        return -1, "iSCSI session not logged in"

                    # unmount filesystem
                    subprocess.run(
                        ["sudo", "umount", local_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )

                    # logout iscsi session
                    if iqn and remote_ip:
                        logout_cmd = ['sudo', 'iscsiadm', '-m', 'node', '-T', iqn, '-p', remote_ip, '--logout']
                        subprocess.check_output(logout_cmd)
                        sprint("iSCSI session logged out")

                    return 0, local_path
                
            elif is_mounted(local_path):
                if sys.platform.startswith("darwin"):
                    umount_cmd = ['sudo', 'umount', '-f', local_path]
                    response = subprocess.check_output(umount_cmd)
                    sprint("Un mount response ",response)
                    sprint(f"Trying to unmount to {local_path}")
                    if not wait_until_unmounted(local_path):
                        sprint(f"Unmount verification failed for {local_path}")
                        return -1, local_path
                    return 0, local_path

                elif sys.platform.startswith("linux"):
                    umount_cmd = ['sudo', 'umount', '-f', '-l', local_path]
                    result = subprocess.run(
                        umount_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=15
                    )
                    sprint(f"Trying to unmount to {local_path}")
                    if result.returncode != 0:
                        stderr_txt = (result.stderr or b"").decode(errors="replace").lower()
                        if "not mounted" in stderr_txt or "no such file" in stderr_txt:
                            return 0, local_path
                        sprint(f"umount failed: {stderr_txt}")
                        return -1, local_path
                    return 0, local_path
                
                else:
                    raise RuntimeError("Unsupported OS")

            else:
                sprint(f"Mount path already not mounted {local_path}")
                return 0, local_path
    except Exception as e:
       err_txt = str(e)
       if sys.platform.startswith("linux") and "not mounted" in err_txt.lower():
           sprint(f"Mount path already not mounted {local_path}")
           return 0, local_path
       sprint(f"Unable to unmount share: {e}")
       return -1, local_path


# ==============
# Delete Process functions
# ==============

def deleteVolumeFolder(path, remote_ip, iqn, user_name, password, protocol_name):
    try:
        if sys.platform.startswith("win"):
            if protocol_name in ("iSCSI-Chap", "iSCSI-NoChap"):
                try:
                    # For ISCSI-CHAP and ISCSI-NoCHAP
                    run_powershell("Restart-Service MSiSCSI")
                    return 0
                except Exception as e:
                    sprint("Unable to restart iSCSI service", e)
                    return -1
            
            elif protocol_name == "CIFS":
                if not path:
                    # Drive already unmounted — no folder to clean up on Windows CIFS
                    return 0
                try:
                    cmd = ["cmd", "/c", "net", "use", path, "/delete", "/y"]
                    subprocess.run(cmd, check=True)
                    sprint("Windows drive deleted:", path)
                    return 0
                except Exception as e:
                    pass

            else:
                return -1

        else:

            # if protocol_name in ("iSCSI-Chap", "iSCSI-NoChap"):
            #     logout_cmd = ['sudo', 'iscsiadm', '-m', 'node', '-T', iqn, '-p', remote_ip, '--op', 'delete']
            #     subprocess.check_output(logout_cmd)
            #     sprint(f"iSCSI session logged out for {remote_ip} and path {path}")
    
            if os.path.exists(path):
                shutil.rmtree(path)
                return 0
            else:
                sprint(f"Path not found for  : {path}")
                return -1
    except Exception as e:
        sprint(f"Exception while deleting folder '{path}': {e}")
        return -1
    


@app.route("/mountVolume", methods=["POST"])
def mountVolume():
    try:
        data = request.get_json()
        volumeName = data.get('volumeName')
        protocol_name = data.get('protocol_name')
        remote_ip = data.get('remote_ip')
        host_name = data.get("host_name")
        user_name = data.get("user_name")
        ip = data.get("ip")
        password = data.get("password")
        wwn = data.get("wwn")
        url = data.get("url")

        result, mount_path, error_message = mount_process(volumeName, protocol_name, remote_ip, host_name,  user_name, ip, password, wwn, url)
        if result == 0:
            response_data = {"status": "success", "message": "Mount process completed successfully.", "mount_path" : mount_path, "error_message" :error_message}
        else:
            response_data = {"status": "failure", "message": "Mount process failed.", "mount_path" : mount_path, "error_message" : error_message}
        return response_data
    except Exception as e:
        response_data = {"status": "failure", "message": str(e), "mount_path" : "N/A", "error_message" : ""}
        return response_data

@app.route("/unmountVolume", methods=["POST"])
def unmountVolume():
    try:
        data = request.get_json()
        volumeName = data.get('volumeName')
        remote_ip = data.get('remote_ip')
        protocol_name = data.get("protocol_name")
        ip = data.get("ip")
        user_name = data.get("user_name")
        password = data.get("password")
        result, unmount_path = unmount_process(volumeName, remote_ip, protocol_name, user_name, password, ip)
        if result == 0:
            response_data = {"status": "success", "message": "Unmount process completed successfully.","unmount_path" : unmount_path}
        else:
            response_data = {"status": "failure", "message": "Unmount process failed.","unmount_path" : unmount_path}
        return response_data
    except Exception as e:
        response_data = {"status": "failure", "message": str(e), "unmount_path" : "N/A"}
        return response_data

@app.route("/deleteFolder", methods=["DELETE", "POST"])
def deleteFolder():
    try:
        data = request.get_json()
        volumeName = data.get('volumeName')
        node_ip = data.get('node_ip')
        iqn = data.get('iqn')
        user_name = data.get("user_name")
        password = data.get("password")
        protocol_name = data.get("protocol_name")

        if sys.platform.startswith("win"):
            local_path = find_window_drive_by_volume(volumeName,protocol_name)
        else:
            Mount_Path = get_mount_base_path()
            local_path=os.path.join(Mount_Path, volumeName)

        sprint("localPath to delete", local_path)
        result = deleteVolumeFolder(local_path, node_ip, iqn, user_name, password, protocol_name)
        if result == 0:
            response_data = {"status": "success", "message": "Folder deleted successfully.", "local_path" : local_path}
        else:
            response_data = {"status": "failure", "message": "Folder not deleted", "local_path" : local_path}
        return response_data
    except Exception as e:
        response_data = {"status": "failure", "message": str(e), "local_path" : "N/A"}
        return response_data

def TestMount():
    volumeName = 'cifs1'
    protocol_name = 'CIFS'
    remote_ip = '192.168.30.16'
    result = mount_process(volumeName, protocol_name, remote_ip)
    sprint ("cifs mount result=",result) 
    
if __name__ == "__main__":
    # TestMount()
    app.run(debug=False,port=PORT,host=HOST)

