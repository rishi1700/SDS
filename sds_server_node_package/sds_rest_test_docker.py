from flask import Flask, request, jsonify
import requests
import sqlite3
import os
from sds_DB_create import checkDb
app = Flask(__name__)


URL = "http://13.235.103.96/gui@Q/cgi/"

DB_PATH = "/mnt/data/sdsDB.db"

# Function no to take START
def sprint (a,b=0):
    print(a,b)

def compare_and_update_table_data(c,table, data, SN_controller_id, remote_id):
    """
    Compare and update record using sds_mapping.local_id as the anchor.
    This prevents duplicate issues if key fields (like system_name) change.
    """
    try:

        # Lookup local_id from sds_mapping
        c.execute(
            "SELECT local_id FROM sds_mapping WHERE element=? AND controller_id=? AND remote_id=?",
            [table, SN_controller_id, remote_id]
        )
        row = c.fetchone()
        if not row:
            return 0  # No mapping → treat as not found

        local_id = row[0]

        # Fetch existing row using local_id
        c.execute(f"SELECT * FROM {table} WHERE id=?", [local_id])
        record_exist = c.fetchone()
        if not record_exist:
            return 0

        # Get DB column names
        db_columns = [col[1] for col in c.execute(f"PRAGMA table_info({table})").fetchall()]
        db_dict = dict(zip(db_columns, record_exist))

        data_with_controller = dict(data)  # copy
        if "controller_id" in db_columns:
            data_with_controller["controller_id"] = SN_controller_id

        # Compare fields (ignore id)
        updated_fields = {}
        for field, value in data_with_controller.items():
            if field == "id":  
                continue
            if field in db_dict and str(db_dict[field]) != str(value):
                updated_fields[field] = value

        if updated_fields:
            set_clause = ", ".join([f"{key}=?" for key in updated_fields.keys()])
            values = list(updated_fields.values()) + [local_id]
            sql = f"UPDATE {table} SET {set_clause} WHERE id=?"
            c.execute(sql, values)
            sprint(f"{table} updated with data: {updated_fields}")

        return 1
    except Exception as e:
        sprint(f"Exception in compare_and_update_table_data for {table} : {e}")
        return -1
# Function no to take END

# Functions Start

def fetch_SN_Vm_image():
    try:
        response = requests.get(URL + "cgi_SdsDetail.py?requestType=vm_image")
        return response.json()
    except Exception as e:
        return -1

def fetch_SN_Vm_group():
    try:
        response = requests.get(URL + "cgi_SdsDetail.py?requestType=vm_group")
        return response.json()
    except Exception as e:
        return -1

def fetch_SN_Virtualmachine():
    try:
        response = requests.get(URL + "cgi_SdsDetail.py?requestType=virtualmachine")
        return response.json()
    except Exception as e:
        return -1

def fetch_SN_Network():
    try:
        response = requests.get(URL + "cgi_SdsDetail.py?requestType=network")
        return response.json()
    except Exception as e:
        return -1

def fetch_SN_Vm_profile():
    try:
        response = requests.get(URL + "cgi_SdsDetail.py?requestType=vm_profile")
        return response.json()
    except Exception as e:
        return -1

def DB_Create_SN_Vm_Image(SN_VM_image_info,SDS_Cont_id):
    res = -1
    db_open = False
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.text_factory = str
        c = conn.cursor()
        db_open = True

        data_not_inserted = []

        for item in SN_VM_image_info:
            c.execute(
                "SELECT local_id FROM sds_mapping WHERE element=? AND controller_id=? AND remote_id=?",
                ["vm_image", SDS_Cont_id, item["id"]]
            )
            isVmImageExist = c.fetchone()
            if not isVmImageExist:

                c.execute("Insert into vm_image (image_name, state, cr_date, edit_date,del_date,path_app_saved,vm_image_size,vm_group_id,downloded,image_cost,support_cost,image_description,path_image_icon,app_download_server,image_type,file_name,download_percentage,uuid,profile_id,controller_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
                    item["image_name"],
                    item["state"],
                    item["cr_date"],
                    item["edit_date"],
                    item["del_date"],
                    item["path_app_saved"],
                    item["vm_image_size"],
                    item["vm_group_id"],
                    item["downloded"],
                    item["image_cost"],
                    item["support_cost"],
                    item["image_description"],
                    item["path_image_icon"],
                    item["app_download_server"],
                    item["image_type"],
                    item["file_name"],
                    item["download_percentage"],
                    item["uuid"],
                    item["profile_id"],
                    SDS_Cont_id
                ])


                if c.lastrowid:
                    inserted_row_id = c.lastrowid
                    c.execute(
                        "INSERT INTO sds_mapping (element,controller_id,remote_id,local_id) VALUES (?,?,?,?)",
                        ["vm_image", SDS_Cont_id, item["id"], inserted_row_id]
                    )
                else:
                    data_not_inserted.append(item["image_name"])

                conn.commit()
            else:
                # Update the image
                compare_and_update_table_data(c,"vm_image",item,SDS_Cont_id,item["id"])
                conn.commit()
                
        
        if len(data_not_inserted) > 0:
            for item in data_not_inserted:
                sprint(f"Failed to insert vm image {item}")
        
        # Delete that data which is not in incoming data
        try:
            # Collect image_name from incoming vm_image
            source_vm_images_names = [item["image_name"] for item in SN_VM_image_info]

            # Fetch existing vm_images for this controller
            c.execute("SELECT id, image_name FROM vm_image WHERE controller_id = ?", [SDS_Cont_id])
            existing_vm_image = c.fetchall()

            for vm_image_id, vm_image_name in existing_vm_image:
                if vm_image_name not in source_vm_images_names:
                    # Delete mapping rows
                    c.execute("DELETE FROM sds_mapping WHERE controller_id = ? AND element = 'vm_image' AND element_name = ?", [SDS_Cont_id, vm_image_name])
                    # Delete the vm_image itself
                    c.execute("DELETE FROM vm_image WHERE id = ?", [vm_image_id])

                    sprint(f"{vm_image_name} is deleted from vm_image table")

            conn.commit()
        except Exception as cleanup_err:
            message = f"Exception during cleanup in vm_image table : {str(cleanup_err)}"
            sprint(message)
        
        if db_open:
            c.close()
            conn.close()
            db_open = False
        res = 1
        return res

    except Exception as e:
        sprint("Exception in DB_Create_SN_Vm_Image",e)
        if db_open:
            c.close()
            conn.close()
            db_open = False
        return res

def DB_Create_SN_Vm_group(SN_VM_group_info,SDS_Cont_id):
    res = -1
    db_open = False
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.text_factory = str
        c = conn.cursor()
        db_open = True

        data_not_inserted = []

        for item in SN_VM_group_info:
            c.execute(
                "SELECT local_id FROM sds_mapping WHERE element=? AND controller_id=? AND remote_id=?",
                ["vm_group", SDS_Cont_id, item["id"]]
            )
            isVmImageExist = c.fetchone()
            if not isVmImageExist:

                c.execute("Insert into vm_group (group_name, state, cr_date, edit_date,del_date,path_group_icon,controller_id) VALUES (?,?,?,?,?,?,?)", [
                    item["group_name"],
                    item["state"],
                    item["cr_date"],
                    item["edit_date"],
                    item["del_date"],
                    item["path_group_icon"],
                    SDS_Cont_id
                ])

                if c.lastrowid:
                    inserted_row_id = c.lastrowid
                    c.execute(
                        "INSERT INTO sds_mapping (element,controller_id,remote_id,local_id) VALUES (?,?,?,?)",
                        ["vm_group", SDS_Cont_id, item["id"], inserted_row_id]
                    )
                else:
                    data_not_inserted.append(item["group_name"])

                conn.commit()
            else:
                # Update the image
                compare_and_update_table_data(c,"vm_group",item,SDS_Cont_id,item["id"])
                conn.commit()
                
        
        if len(data_not_inserted) > 0:
            for item in data_not_inserted:
                sprint(f"Failed to insert vm_group {item}")
        
        # Delete that data which is not in incoming data
        try:
            # Collect image_name from incoming vm_group
            source_vm_group_names = [item["group_name"] for item in SN_VM_group_info]

            # Fetch existing vm_group for this controller
            c.execute("SELECT id, group_name FROM vm_group WHERE controller_id = ?", [SDS_Cont_id])
            existing_vm_group = c.fetchall()

            for vm_group_id, vm_group_name in existing_vm_group:
                if vm_group_name not in source_vm_group_names:
                    # Delete mapping rows
                    c.execute("DELETE FROM sds_mapping WHERE controller_id = ? AND element = 'vm_group' AND element_name = ?", [SDS_Cont_id, vm_group_name])
                    # Delete the vm_group itself
                    c.execute("DELETE FROM vm_group WHERE id = ?", [vm_group_id])

                    sprint(f"{vm_group_name} is deleted from vm_group table")

            conn.commit()
        except Exception as cleanup_err:
            message = f"Exception during cleanup in vm_group table : {str(cleanup_err)}"
            sprint(message)
        
        if db_open:
            c.close()
            conn.close()
            db_open = False
        res = 1
        return res

    except Exception as e:
        sprint("Exception in DB_Create_SN_Vm_group",e)
        if db_open:
            c.close()
            conn.close()
            db_open = False
        return res

def DB_Create_SN_Virtualmachine(SN_Virtualmachine_info,SDS_Cont_id):
    res = -1
    db_open = False
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.text_factory = str
        c = conn.cursor()
        db_open = True

        data_not_inserted = []

        for item in SN_Virtualmachine_info:
            
            c.execute(
                "SELECT local_id FROM sds_mapping WHERE element=? AND controller_id=? AND remote_id=?",
                ["virtualmachine", SDS_Cont_id, item["id"]]
            )
            isVmImageExist = c.fetchone()
            if not isVmImageExist:

                c.execute("Insert into virtualmachine (name, type, parent_VM_id, state, cr_date, started_date, edit_date, del_date, location, num_cores, memory_GB, saved_path, vm_disk_size, vm_image_id, last_local_backup, last_remote_backup, percentage, xml_path, port, system_id,ssh_port,controller_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
                    item["name"],
                    item["type"],
                    item["parent_VM_id"],
                    item["state"],
                    item["cr_date"],
                    item["started_date"],
                    item["edit_date"],  
                    item["del_date"],
                    item["location"],
                    item["num_cores"],
                    item["memory_GB"],
                    item["saved_path"],
                    item["vm_disk_size"],
                    item["vm_image_id"],
                    item["last_local_backup"],
                    item["last_remote_backup"],
                    item["percentage"],
                    item["xml_path"],
                    item["port"],
                    item["system_id"],
                    item["ssh_port"],
                    SDS_Cont_id
                ])


                if c.lastrowid:
                    inserted_row_id = c.lastrowid
                    c.execute(
                        "INSERT INTO sds_mapping (element,controller_id,remote_id,local_id) VALUES (?,?,?,?)",
                        ["virtualmachine", SDS_Cont_id, item["id"], inserted_row_id]
                    )
                else:
                    data_not_inserted.append(item["name"])

                conn.commit()
            else:
                # Update the image
                compare_and_update_table_data(c,"virtualmachine",item,SDS_Cont_id,item["id"])
                conn.commit()
                
        
        if len(data_not_inserted) > 0:
            for item in data_not_inserted:
                sprint(f"Failed to insert virtualmachine {item}")
        
        # Delete that data which is not in incoming data
        try:
            # Collect image_name from incoming virtualmachine
            source_vm_names = [item["name"] for item in SN_Virtualmachine_info]

            # Fetch existing virtualmachine for this controller
            c.execute("SELECT id, name FROM virtualmachine WHERE controller_id = ?", [SDS_Cont_id])
            existing_vm = c.fetchall()

            for vm_id, vm_name in existing_vm:
                if vm_name not in source_vm_names:
                    # Delete mapping rows
                    c.execute("DELETE FROM sds_mapping WHERE controller_id = ? AND element = 'virtualmachine' AND element_name = ?", [SDS_Cont_id, vm_name])
                    # Delete the virtualmachine itself
                    c.execute("DELETE FROM virtualmachine WHERE id = ?", [vm_id])

                    sprint(f"{vm_name} is deleted from virtualmachine table")

            conn.commit()
        except Exception as cleanup_err:
            message = f"Exception during cleanup in virtualmachine table : {str(cleanup_err)}"
            sprint(message)
        
        if db_open:
            c.close()
            conn.close()
            db_open = False
        res = 1
        return res

    except Exception as e:
        sprint("Exception in DB_Create_SN_Virtualmachine",e)
        if db_open:
            c.close()
            conn.close()
            db_open = False
        return res

def DB_Create_SN_Network(SN_network_info,SDS_Cont_id):
    res = -1
    db_open = False
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.text_factory = str
        c = conn.cursor()
        db_open = True

        data_not_inserted = []

        for item in SN_network_info:
            c.execute(
                "SELECT local_id FROM sds_mapping WHERE element=? AND controller_id=? AND remote_id=?",
                ["network", SDS_Cont_id, item["id"]]
            )
            isVmImageExist = c.fetchone()
            if not isVmImageExist:

                c.execute("Insert into network (name, state, cr_date, edit_date, del_date, cidr, enable_dhcp,controller_id) VALUES (?,?,?,?,?,?,?,?)", [
                    item["name"],
                    item["state"],
                    item["cr_date"],
                    item["edit_date"],
                    item["del_date"],
                    item["cidr"],
                    item["enable_dhcp"],                
                    SDS_Cont_id
                ])

                
                if c.lastrowid:
                    inserted_row_id = c.lastrowid
                    c.execute(
                        "INSERT INTO sds_mapping (element,controller_id,remote_id,local_id) VALUES (?,?,?,?)",
                        ["network", SDS_Cont_id, item["id"], inserted_row_id]
                    )
                else:
                    data_not_inserted.append(item["name"])

                conn.commit()
            else:
                # Update the image
                compare_and_update_table_data(c,"network",item,SDS_Cont_id,item["id"])
                conn.commit()
                
        
        if len(data_not_inserted) > 0:
            for item in data_not_inserted:
                sprint(f"Failed to insert network {item}")
        
        # Delete that data which is not in incoming data
        try:
            # Collect image_name from incoming network
            source_vm_names = [item["name"] for item in SN_network_info]

            # Fetch existing network for this controller
            c.execute("SELECT id, name FROM network WHERE controller_id = ?", [SDS_Cont_id])
            existing_vm = c.fetchall()

            for vm_id, vm_name in existing_vm:
                if vm_name not in source_vm_names:
                    # Delete mapping rows
                    c.execute("DELETE FROM sds_mapping WHERE controller_id = ? AND element = 'network' AND element_name = ?", [SDS_Cont_id, vm_name])
                    # Delete the network itself
                    c.execute("DELETE FROM network WHERE id = ?", [vm_id])

                    sprint(f"{vm_name} is deleted from network table")

            conn.commit()
        except Exception as cleanup_err:
            message = f"Exception during cleanup in network table : {str(cleanup_err)}"
            sprint(message)
        
        if db_open:
            c.close()
            conn.close()
            db_open = False
        res = 1
        return res

    except Exception as e:
        sprint("Exception in DB_Create_SN_Virtualmachine",e)
        if db_open:
            c.close()
            conn.close()
            db_open = False
        return res


def DB_Create_SN_Vm_profile(SN_vm_profile_info,SDS_Cont_id):
    res = -1
    db_open = False
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.text_factory = str
        c = conn.cursor()
        db_open = True

        data_not_inserted = []

        for item in SN_vm_profile_info:
            c.execute(
                "SELECT local_id FROM sds_mapping WHERE element=? AND controller_id=? AND remote_id=?",
                ["vm_profile", SDS_Cont_id, item["id"]]
            )
            isVmImageExist = c.fetchone()
            if not isVmImageExist:

                c.execute("Insert into vm_profile (name, vCPU, memory, storage, storage, edit_date, del_date,controller_id) VALUES (?,?,?,?,?,?,?,?)", [
                    item["name"],
                    item["vCPU"],
                    item["memory"],
                    item["storage"],
                    item["storage"],
                    item["edit_date"],
                    item["del_date"],             
                    SDS_Cont_id
                ])

                
                if c.lastrowid:
                    inserted_row_id = c.lastrowid
                    c.execute(
                        "INSERT INTO sds_mapping (element,controller_id,remote_id,local_id) VALUES (?,?,?,?)",
                        ["vm_profile", SDS_Cont_id, item["id"], inserted_row_id]
                    )
                else:
                    data_not_inserted.append(item["name"])

                conn.commit()
            else:
                # Update the image
                compare_and_update_table_data(c,"vm_profile",item,SDS_Cont_id,item["id"])
                conn.commit()
                
        
        if len(data_not_inserted) > 0:
            for item in data_not_inserted:
                sprint(f"Failed to insert vm_profile {item}")
        
        # Delete that data which is not in incoming data
        try:
            # Collect image_name from incoming vm_profile
            source_vm_names = [item["name"] for item in SN_vm_profile_info]

            # Fetch existing vm_profile for this controller
            c.execute("SELECT id, name FROM vm_profile WHERE controller_id = ?", [SDS_Cont_id])
            existing_vm = c.fetchall()

            for vm_id, vm_name in existing_vm:
                if vm_name not in source_vm_names:
                    # Delete mapping rows
                    c.execute("DELETE FROM sds_mapping WHERE controller_id = ? AND element = 'vm_profile' AND element_name = ?", [SDS_Cont_id, vm_name])
                    # Delete the vm_profile itself
                    c.execute("DELETE FROM vm_profile WHERE id = ?", [vm_id])

                    sprint(f"{vm_name} is deleted from vm_profile table")

            conn.commit()
        except Exception as cleanup_err:
            message = f"Exception during cleanup in vm_profile table : {str(cleanup_err)}"
            sprint(message)
        
        if db_open:
            c.close()
            conn.close()
            db_open = False
        res = 1
        return res

    except Exception as e:
        sprint("Exception in DB_Create_SN_Virtualmachine",e)
        if db_open:
            c.close()
            conn.close()
            db_open = False
        return res

def readDockerData():

    try:
        tables = ['vm_image','vm_group','virtualmachine',"network","vm_profile"]
        for table in tables:
            if table == "vm_image":
                res = fetch_SN_Vm_image()
                if res:
                    DB_Create_SN_Vm_Image(res,3)
            elif table == "vm_group":
                res = fetch_SN_Vm_group()
                if res:
                    DB_Create_SN_Vm_group(res,3)
            elif table == "virtualmachine":
                res = fetch_SN_Virtualmachine()
                if res:
                    DB_Create_SN_Virtualmachine(res,3)
            elif table == "network":
                res = fetch_SN_Network()
                if res:
                    DB_Create_SN_Network(res,3)
            elif table == "vm_profile":
                res = fetch_SN_Vm_profile()
                if res:
                    DB_Create_SN_Vm_profile(res,3)
                
                        

    except Exception as e:
        print(e)


def get_nodes_details():
    conn = sqlite3.connect(DB_PATH)
    conn.text_factory = str
    c = conn.cursor()
    db_open = True
    dbdata = []
    try:
        dbquery="SELECT c.id,c.name,sn.ip from storage_node sn JOIN controller c  ON sn.controller_id = c.id"
        conn.commit()
        c.execute(dbquery)
        rows = c.fetchall()

        for row in rows:
            jsonschema = {
                "id": row[0],
                "name": f"{row[1]}@{row[2]}",
                "value" : row[0]
            }
            dbdata.append(jsonschema)
                
        c.close()
        conn.close()
        db_open = False
        return dbdata
    except Exception as err:
        if db_open:
            c.close()
            conn.close()
            db_open = False
        return dbdata

# Functions End

# App Routes Start

@app.route("/getVmGroup", methods=['GET'])
def getVmGroup():
    data = []
    db_open = False
    try:
        payload = request.get_json()
        controller_id = payload.get("controller_id")

        conn = sqlite3.connect(DB_PATH)
        conn.text_factory = str
        c = conn.cursor()
        db_open = True

        c.execute("SELECT id,group_name FROM vm_group where controller_id = ?", [controller_id])
        rows = c.fetchall()

        for row in rows:
            row_data = {
                "id": row[0],
                "group_name": row[1]
            }
            data.append(row_data)
        if db_open:
            c.close()
            conn.close()
            db_open = False
        return jsonify(data)
    except Exception as e:
        if db_open:
            c.close()
            conn.close()
            db_open = False
        print(f"Exception in getVmGroup : {str(e)}")
        return jsonify(data)

@app.route("/getVmImage", methods=['GET'])
def getVmImage():
    data = []
    db_open = False
    try:
        payload = request.get_json()
        controller_id = payload.get("controller_id")
        vm_group_id = payload.get("vm_group_id")

        conn = sqlite3.connect(DB_PATH)
        conn.text_factory = str
        c = conn.cursor()
        db_open = True

        c.execute("SELECT id,image_name FROM vm_image where controller_id = ? and vm_group_id = ? and downloded = 'yes' ", [controller_id,vm_group_id])
        rows = c.fetchall()

        for row in rows:
            row_data = {
                "id": row[0],
                "name": row[1]
            }
            data.append(row_data)
        
        if db_open:
            c.close()
            conn.close()
            db_open = False
        return jsonify(data)
    except Exception as e:
        if db_open:
            c.close()
            conn.close()
            db_open = False
        print(f"Exception in getVmImage : {str(e)}")
        return jsonify(data)

@app.route("/getVmNetwork", methods=['GET'])
def getVmNetwork():
    data = []
    db_open = False
    try:
        payload = request.get_json()
        controller_id = payload.get("controller_id")

        conn = sqlite3.connect(DB_PATH)
        conn.text_factory = str
        c = conn.cursor()
        db_open = True

        c.execute("SELECT id,name,cidr FROM network where controller_id = ?", [controller_id])
        rows = c.fetchall()

        for row in rows:
            row_data = {
                "id": row[0],
                "name": row[1],
                "cidr": row[2]
            }
            data.append(row_data)
        
        if db_open:
            c.close()
            conn.close()
            db_open = False

        return jsonify(data)
    except Exception as e:
        if db_open:
            c.close()
            conn.close()
            db_open = False
        print(f"Exception in getVmImage : {str(e)}")
        return jsonify(data)

@app.route("/getVmProfile", methods=['GET'])
def getVmProfile():
    data = []
    db_open = False
    try:
        payload = request.get_json()
        controller_id = payload.get("controller_id")

        conn = sqlite3.connect(DB_PATH)
        conn.text_factory = str
        c = conn.cursor()
        db_open = True

        c.execute("SELECT id,name,vCPU,memory,storage FROM vm_profile where controller_id = ?", [controller_id])
        rows = c.fetchall()

        for row in rows:
            row_data = {
                "id": row[0],
                "name": row[1],
                "vCPU": row[2],
                "memory": row[3],
                "storage": row[4]
            }
            data.append(row_data)
        
        if db_open:
            c.close()
            conn.close()
            db_open = False

        return jsonify(data)
    except Exception as e:
        if db_open:
            c.close()
            conn.close()
            db_open = False
        print(f"Exception in getVmProfile : {str(e)}")
        return jsonify(data)

@app.route("/checkVmName", methods=['GET'])
def checkVmName():
    db_open = False
    try:
        payload = request.get_json()
        controller_id = payload.get("controller_id")
        name = payload.get("name")

        conn = sqlite3.connect(DB_PATH)
        conn.text_factory = str
        c = conn.cursor()
        db_open = True

        c.execute("SELECT * FROM virtualmachine where controller_id = ? and name = ?", [controller_id,name])
        row = c.fetchone()
        if row:
            status = True
        else:
            status = False
        
        if db_open:
            c.close()
            conn.close()
            db_open = False

        return jsonify({"status" : status})
    except Exception as e:
        if db_open:
            c.close()
            conn.close()
            db_open = False
        print(f"Exception in getVmProfile : {str(e)}")
        return jsonify({"status" : False})

def save_data_sn_vm(data):
    try:
        port_no = data.get("port_no")
        server_name = data.get("server_name")
        vcpu = data.get("vcpu")
        memory = data.get("memory")
        disk_size = data.get("disk_size")
        image_id = data.get("image_id")
        network_name = data.get("network_name")
        selectedOrgGroups = data.get("selectedOrgGroups")
        SSHPortNo = data.get("SSHPortNo")
        response = requests.get(URL + f"cgi_myserver_save_config.py?portNo={port_no}&server_name={server_name}&vcpu={vcpu}&memory={memory}&disk_size={disk_size}&image_id={image_id}&network_name={network_name}&selectedOrgGroups={selectedOrgGroups}&SSHPortNo={SSHPortNo}")
        return response.json()
    
    except Exception as e:
        return {"status" : "fail" , "description" : f"Exception in save_data_sn_vm {str(e)}"}

def launch_sn_vm(data):
    try:
        server_name = data.get("server_name")
        start_response = requests.get(URL + f"cgi_myserver_launch.py?server_name={server_name}&state=4&uuid=VhxZs6H8").json()
        if(start_response.get("state") == "5"):
            on_response = requests.get(URL + f"cgi_myserver_launch.py?server_name={server_name}&state=5&uuid=VhxZs6H8").json()
            return on_response
        else:
            return start_response
            
    except Exception as e:
        return {"status" : "fail" , "description" : f"Exception in save_data_sn_vm {str(e)}"}

@app.route("/getNodesDetails", methods=["POST"])
def getNodesDetails():
    nodes = get_nodes_details()
    return nodes

@app.route("/sn_vm", methods=["GET"])
def get_sn_vm():
    db_open = False
    data = []
    try:
        payload = request.get_json()
        controller_id = payload.get("controller_id")

        conn = sqlite3.connect(DB_PATH)
        conn.text_factory = str
        c = conn.cursor()
        db_open = True

        c.execute("SELECT name, type, parent_VM_id, state, cr_date, started_date, edit_date, del_date, location, num_cores, memory_GB, saved_path, vm_disk_size, vm_image_id, last_local_backup, last_remote_backup, percentage, xml_path, port, system_id,ssh_port,controller_id FROM virtualmachine where controller_id = ?", [controller_id])
        rows = c.fetchall()

        for row in rows:
            row_data = {
                "name": row[0],
                "type": row[1],
                "parent_VM_id": row[2],
                "state": row[3],
                "cr_date": row[4],
                "started_date": row[5],
                "edit_date": row[6],
                "del_date": row[7],
                "location": row[8],
                "num_cores": row[9],
                "memory_GB": row[10],
                "saved_path": row[11],
                "vm_disk_size": row[12],
                "vm_image_id": row[13],
                "last_local_backup": row[14],
                "last_remote_backup": row[15],
                "percentage": row[16],
                "xml_path": row[17],
                "port": row[18],
                "system_id": row[19],
            }
            data.append(row_data)
        
        if db_open:
            c.close()
            conn.close()
            db_open = False

        return jsonify(data)

    except Exception as e:
        sprint(f"Exception in get_sn_vm : {str(e)}")
        if db_open:
            c.close()
            conn.close()
            db_open = False
        return jsonify(data)

@app.route("/sn_vm", methods=["POST"])
def save_sn_vm():
    try:
        data = request.get_json()
        response = save_data_sn_vm(data)
        return jsonify(response)
    except Exception as e:
        return jsonify({"status" : "fail" , "description" : f"Exception in save_sn_vm {str(e)}"})

@app.route("/sn_launch_vm", methods=["POST"])
def sn_launch_vm():
    try:
        data = request.get_json()
        response = launch_sn_vm(data)
        return jsonify(response)
    except Exception as e:
        return jsonify({"status" : "fail" , "description" : f"Exception in save_sn_vm {str(e)}"})

def checkDB():
    try:
        checkDb(DB_PATH, "db_details.json")
        os.chmod(DB_PATH, 0o777)
        with open("/tmp/db_ready.flag", "w") as f:
            f.write("ready")
    except Exception as e:
        sprint(f"Exception in creating db : {str(e)}")


if __name__ == '__main__':
    readDockerData()
    checkDB()
    app.run(host='0.0.0.0', port=5001)