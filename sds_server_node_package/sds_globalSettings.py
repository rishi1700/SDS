# SDS Service's
SDS_SERVICE = "Enabled" # Enabled and Disabled
# ----If the SDS_SERVICE is Enabled ------
# SDS related all scipts will be called
# SDS related DATA will be shown from DB into the GUI
# SDS related all GUI features will be shown

# ---- If the SDS_SERVICE is Disabled ------
# None of the above scripts / GUI features / DB data will be shown / called

SDS_SERVER = "Local" # Local and Remote
SDS_URL = "127.0.0.1" #It can be local ip or remote ip
# SDS_SERVER can be in local or remote. Wherever the SDS Flask server is running, we need to put in that particular IP ADDRESS.

# Database Paths
DB_PATH = "/mnt/data/sdsDB.db"


# Table Json
DEFAULT_PATH_TO_DB_CONFIG = "sds_db_details.json"

# Logs
ConsoleAlertLogPath = "/mnt/xdata/sds_console_alerts.log"
ConsoleLogPath = "/mnt/xdata/sds_console.log"

# AWS Test
AWS_TEST = False

# Ports
PORT = 4000 # SDS Rest Main Port
CLIENT_PORT = 4002 # Compute Rest Client Port