from flask import Flask, jsonify,request
import requests
import os
import sqlite3
from sds_DB_create import checkDb
import ast
import random
import threading
import atexit
import sys
import signal
import subprocess
import time
import socket
import shutil
from sds_logRoutine import init_CONlogger
from sds_globalSettings import DB_PATH, AWS_TEST, PORT, CLIENT_PORT

volOff=4
volStarting=5
volOn=6
VolSuspended=7
cifs=1
nfs=2
iSCSI_Chap=3
iSCSI_NoChap=4
ftp=5
FC=6
iSER_Chap=8
iSER_NoChap=9
NFS_RDMA =10

MIN_FreeSpace=350


app = Flask(__name__)

#poolType = "HDD POOL" #HDD POOL,MegaRAID POOL


global SDSRest_ThreadDebug
SDSRest_ThreadDebug=1
 
 
global SDSRestCONhandler
SDSRestCONhandler = "CONSDSRest"
 
 
global SDSRestCONLogger
SDSRestCONLogger =None
 
def SDSRestCONLoggerInit(arg):
    global SDSRestCONLogger
    if (arg ==0):
        SDSRestCONLogger = init_CONlogger(SDSRestCONhandler)
        sprint(("SDSRestCONLogger 0",SDSRestCONLogger[0]))
        sprint(("SDSRestCONLogger 1",SDSRestCONLogger[1]))
    return (SDSRestCONLogger)
 
 
def sprint (a,b=0):
    
    if SDSRest_ThreadDebug==1:
        if b!=0:
            print ((a,b))
            loggerName=SDSRestCONhandler
            logger=SDSRestCONLoggerInit(1)
            logger[0].info(loggerName+": "+str(a)+","+str(b))
        else:
            print (a)
            loggerName=SDSRestCONhandler
            logger=SDSRestCONLoggerInit(1)
            logger[0].info(loggerName+": "+str(a))
 
def InitSDSRest():    
    SDSRestCONLoggerInit(0)
 
InitSDSRest()

def ping_ip(ip , count = 5, timeout = 5):
    try:
        if AWS_TEST:
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

def create_url(node_ip):
    try:
        if not ping_ip(node_ip):
            sprint(f"Node {node_ip} is not reachable")
            return -2
        
        if AWS_TEST:
            URL = f"http://{node_ip}/gui@Q/cgi/" # For Aws
        else:
            URL = f"http://{node_ip}/cgi/" # For Client Server

        return URL
    except Exception as e:
        sprint("Error creating URL for node "+node_ip+"",str(e))
        return -1

def check_protocol_support(protocolId):
    PROTOCOLS = {
         1 : "CIFS" ,
         2 : "NFS" ,
         3 : "iSCSI-Chap" ,
         4 : "iSCSI-NoChap" ,
    }

    try:
        protocol = PROTOCOLS[protocolId]
    except KeyError:
        return False


    if protocol in ["iSCSI-Chap", "iSCSI-NoChap"]:
        return shutil.which("targetcli") is not None

    elif protocol == "CIFS":
        return shutil.which("smbd") is not None

    elif protocol == "NFS":
        return shutil.which("exportfs") is not None

    print(f"Unsupported protocol: {protocol}")

    return False


def read_SN_system_controller(node_ip,requestType):
    try:
        URL = create_url(node_ip)
        data = requests.get(f"{URL}cgi_SdsDetail.py?requestType={requestType}")
        return data.json()
    except Exception as e:
        sprint(f"Error in fetching system data from {node_ip} : {str(e)}")
        return {"error" : -2}

def read_SN_eth_ports(node_ip):
    try:
        URL = create_url(node_ip)
        data = requests.get(f"{URL}cgi_EthernetPorts_Manager.py?requestType=read_lan")
        return data.json()
    except Exception as e:
        sprint(f"Error in fetching eth ports data from {node_ip} : {str(e)}")
        return {"error" : -2}

def read_SN_volume_eth_ports(node_ip):
    try:
        URL = create_url(node_ip)
        data = (requests.get(URL+f"cgi_VolumeManager.py?requestType=read_Ethernet_ports"))
        return data.json()
    except Exception as e:
        sprint(f"Error in fetching eth ports data from {node_ip} : {str(e)}")
        return {"error" : -2}

def read_SN_Pools(node_ip):
    try:
        URL = create_url(node_ip)
        data = requests.get(f"{URL}cgi_Setup_Pool_Manager.py?RequestType=read_pool&PoolType=Select+Pool")
        return data.json()
    except Exception as e:
        sprint(f"Error in fetching pools data from {node_ip} : {str(e)}")
        return {"error" : -2}

def get_controller_id_by_pool_id(poolId):
    conn = sqlite3.connect(DB_PATH)
    conn.text_factory = str
    c = conn.cursor()
    db_open = True
    try:
        dbquery=c.execute("select sds_controller_id from multi_device where id = ?",[poolId])
        controller_id = c.fetchone()[0]
        c.close()
        conn.close()
        db_open = False
        return controller_id
    except Exception as e:
        if db_open:
            c.close()
            conn.close()
            db_open = False
        return 0

def get_controller_id_by_volume_id(volume_id):
    conn = sqlite3.connect(DB_PATH)
    conn.text_factory = str
    c = conn.cursor()
    db_open = True
    try:
        dbquery=c.execute("select controller_id from volume where id = ?",[volume_id])
        controller_id = c.fetchone()[0]
        c.close()
        conn.close()
        db_open = False
        return controller_id
    except Exception as e:
        if db_open:
            c.close()
            conn.close()
            db_open = False
        return 0

def get_controller_id_by_host_group(hostId):
    conn = sqlite3.connect(DB_PATH)
    conn.text_factory = str
    c = conn.cursor()
    db_open = True
    try:
        dbquery=c.execute("select controller_id from sds_host_group where host_id = ?",[hostId])
        controller_ids = c.fetchall()
        c.close()
        conn.close()
        db_open = False
        return controller_ids
    except Exception as e:
        if db_open:
            c.close()
            conn.close()
            db_open = False
        return 0
    
def get_storage_ip_by_controller(controller_id):
    conn = sqlite3.connect(DB_PATH)
    conn.text_factory = str
    c = conn.cursor()
    db_open = True
    try:
        dbquery=c.execute("select ip from storage_node where controller_id = ?",[controller_id])
        ip = c.fetchone()[0]
        c.close()
        conn.close()
        db_open = False
        return ip
    except Exception as e:
        if db_open:
            c.close()
            conn.close()
            db_open = False
        return None

def get_system_id_by_controller(controller_id):
    conn = sqlite3.connect(DB_PATH)
    conn.text_factory = str
    c = conn.cursor()
    db_open = True
    try:
        dbquery=c.execute("select system_id from controller where id = ?",[controller_id])
        system_id = c.fetchone()[0]
        c.close()
        conn.close()
        db_open = False
        return system_id
    except Exception as e:
        if db_open:
            c.close()
            conn.close()
            db_open = False
        return 0

def get_volume_id_by_name(name):
    conn = sqlite3.connect(DB_PATH)
    conn.text_factory = str
    c = conn.cursor()
    db_open = True
    try:
        dbquery=c.execute("select id from volume where name = ?",[name])
        id = c.fetchone()[0]
        c.close()
        conn.close()
        db_open = False
        return id
    except Exception as e:
        if db_open:
            c.close()
            conn.close()
            db_open = False
        return 0

def get_host_id_by_name(name):
    conn = sqlite3.connect(DB_PATH)
    conn.text_factory = str
    c = conn.cursor()
    db_open = True
    try:
        dbquery=c.execute("select id from host where name = ?",[name])
        id = c.fetchone()[0]
        c.close()
        conn.close()
        db_open = False
        return id
    except Exception as e:
        if db_open:
            c.close()
            conn.close()
            db_open = False
        return 0
    
def getControllerIdByStorageIp(ip):
    conn = sqlite3.connect(DB_PATH)
    conn.text_factory = str
    c = conn.cursor()
    db_open = True
    try:
        dbquery=c.execute("select controller_id from storage_node where ip = ?",[ip])
        id = c.fetchone()[0]
        c.close()
        conn.close()
        db_open = False
        return id
    except Exception as e:
        if db_open:
            c.close()
            conn.close()
            db_open = False
        return 0

def get_id_by_remote_id(table,controller_id, remote_id):
    conn = sqlite3.connect(DB_PATH)
    conn.text_factory = str
    c = conn.cursor()
    db_open = True
    try:
        controller_key = 'sds_controller_id' if table == "multi_device" else 'controller_id'
        dbquery=c.execute(f"select id from {table} where {controller_key} = ? and remote_id = ?",[controller_id,remote_id])
        id = c.fetchone()[0]
        c.close()
        conn.close()
        db_open = False
        return id
    except Exception as e:
        if db_open:
            c.close()
            conn.close()
            db_open = False
        return 0

def get_remote_id_by_local_id(table,local_id):
    conn = sqlite3.connect(DB_PATH)
    conn.text_factory = str
    c = conn.cursor()
    db_open = True
    try:
        dbquery=c.execute(f"select remote_id from {table} where id = ?",[local_id])
        id = c.fetchone()[0]
        c.close()
        conn.close()
        db_open = False
        return id
    except Exception as e:
        if db_open:
            c.close()
            conn.close()
            db_open = False
        return 0

def get_storage_pools_data():
    conn = sqlite3.connect(DB_PATH)
    conn.text_factory = str
    c = conn.cursor()
    db_open = True
    try:
        query = "select id,name,level,0 available,deduplication,compression,(case when acceleration_storage > 0 then ROUND(acceleration_storage,2)|| ' GB' WHEN acceleration_storage <= 0 AND name='HDD POOL' then 'No' else 'N/A' end),system_name,ifnull(calculatedraw,0),state,pool_storage,ifnull(encryption,'n/a'),controller_id,sds_controller_id from multi_device where name!='system'"
        dbquery=c.execute(query)
        data = c.fetchall()
        c.close()
        conn.close()
        db_open = False
        return data
    except Exception as e:
        if db_open:
            c.close()
            conn.close()
            db_open = False
        return []

def get_nodes_details_prev():
    conn = sqlite3.connect(DB_PATH)
    conn.text_factory = str
    c = conn.cursor()
    db_open = True
    dbdata = []
    try:
        dbquery='''SELECT c.id,c.name,eth.ip from controller c
            JOIN eth_ports eth ON eth.controller_id = c.id
            where eth.ip is not null and eth.ip <> '' and eth.name = 'LAN1'
        '''
        conn.commit()
        query = c.execute(dbquery)
        for col in c:
            if(col[2] != 'null'):
                jsonschema = {"id" : col[0],"name" : col[1]+"@"+col[2]}
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

def get_nodes_details():
    conn = sqlite3.connect(DB_PATH)
    conn.text_factory = str
    c = conn.cursor()
    db_open = True
    dbdata = []
    try:
        dbquery="SELECT c.id,c.name,sn.ip,sn.active from storage_node sn JOIN controller c  ON sn.controller_id = c.id"
        conn.commit()
        c.execute(dbquery)
        rows = c.fetchall()

        for row in rows:
            jsonschema = {
                "id": row[0],
                "name": f"{row[1]}@{row[2]}",
                "value" : row[0],
                "ip" : row[2],
                "active" : row[3]
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

def get_host_nodes_details_prev():
    conn = sqlite3.connect(DB_PATH)
    conn.text_factory = str
    c = conn.cursor()
    db_open = True
    dbdata = []
    try:
        dbquery='''SELECT c.id,c.name,eth.ip from controller c
            JOIN eth_ports eth ON eth.controller_id = c.id
            where eth.ip is not null and eth.ip <> '' and eth.name = 'LAN1'
        '''
        c.execute(dbquery)

        for col in c:
            jsonschema = {"name":col[1]+"@"+col[2],"value":col[0]}
            dbdata.append(jsonschema)

        c.close()
        conn.close()
        db_open = False
        return dbdata
    except Exception as e:
        sprint(f"Error fetching host nodes details: {e}")
        if db_open:
            c.close()
            conn.close()
        return dbdata

def get_storage_nodes_details():
    conn = sqlite3.connect(DB_PATH)
    conn.text_factory = str
    c = conn.cursor()
    db_open = True
    dbdata = []
    try:
        dbquery='''SELECT c.id, c.name,s.ip, s.active from storage_node s 
            JOIN controller c ON c.id = s.controller_id
        '''
        c.execute(dbquery)

        rows = c.fetchall()

        for row in rows:            
            jsonschema = {
                "id": row[0],
                "name": f"{row[1]}@{row[2]}",
                "value" : row[0],
                "active" : row[3]
            }
            dbdata.append(jsonschema)

        c.close()
        conn.close()
        db_open = False
        return dbdata
    except Exception as e:
        sprint(f"Error fetching host nodes details: {e}")
        if db_open:
            c.close()
            conn.close()
        return dbdata

def get_sds_pools_local_id(name):
    conn = sqlite3.connect(DB_PATH)
    conn.text_factory = str
    c = conn.cursor()
    db_open = True
    try:
        dbquery=c.execute("select id from multi_device where system_name = ?",[name])
        id = c.fetchone()[0]
        c.close()
        conn.close()
        db_open = False
        return id
    except Exception as e:
        if db_open:
            c.close()
            conn.close()
            db_open = False
        return 0
    
def getTheSDSPoolName(controller_id):
    conn = sqlite3.connect(DB_PATH)
    conn.text_factory = str
    c = conn.cursor()
    db_open = True
    dbdata = []
    try:
        dbquery='''SELECT c.name,sn.ip from controller c
            JOIN storage_node sn ON sn.controller_id = c.id
            where controller_id=?
        '''
        conn.commit()
        query = c.execute(dbquery,[controller_id])
        data = c.fetchone()
        name = data[0]+"@"+data[1]
                
        c.close()
        conn.close()
        db_open = False
        return name
    except Exception as err:
        if db_open:
            c.close()
            conn.close()
            db_open = False
        return ""


def getAvailableNVMeOF():
    return 20*1000

def getAvailableiSTOR():
    return 20*1000

def getAvailableMegaRAID(c,cx):

    MRpoolSize=0
    ctrl= cx 
    dbquery=c.execute("select sum(size) from disks where controller_id ='{}".format(ctrl)+"'")
    resp=c.fetchone()[0]
    if (isinstance(resp, int))==True:
        MRpoolSize=int(resp)
    return MRpoolSize

def getRAIDlevel(PoolType):
    level=0
    conn = sqlite3.connect(DB_PATH)
    conn.text_factory = str
    c = conn.cursor()
    try:
        dbquery=c.execute("select level from multi_device where name=?",[PoolType])
        resp=c.fetchone()
        if resp !="None":
            level=resp[0]
        else:
            level=0
        return level
    except Exception as err:
        c.close()
        conn.close()
        return level
    
def getAvailableDisks(c,controller_id,PoolType):
    nbDisks=0
    AllocatedDisks=0
    ctrl= controller_id

    if PoolType=="HDD POOL":
        dbquery=c.execute("select count(*) from disks where rotation =1")
        resp=c.fetchone()[0]
        if (isinstance(resp, int))==True:
            nbDisks=int(resp)
        dbquery=c.execute("select id from multi_device where name='HDD POOL'")
        IdList=c.fetchall()
        for md_id in IdList:
            #sprint( ("id=",md_id[0]))
            PoolId=md_id[0]
            dbquery=c.execute("select count(*) from disks where multi_device_id=?",[PoolId])
            resp=c.fetchone()[0]
            if (isinstance(resp, int))==True:
                AllocatedDisks=AllocatedDisks+int(resp)
        return (nbDisks-AllocatedDisks)

    elif PoolType=="MegaRAID POOL":
        ctrl='/c0'
        dbquery=c.execute("select count(*) from disks where controller_id ='{}".format(ctrl)+"'")
        #dbquery=c.execute("select count(*) from disks where name='mra' or name='mrb' or name='mrc' or name='mrd'")
        resp=c.fetchone()[0]
        if (isinstance(resp, int))==True:
            MRnbDisks=int(resp)
            return MRnbDisks
    else:
        return 10

def read_sds_pool(controller_id,PoolType):
    conn = sqlite3.connect(DB_PATH)
    conn.text_factory = str
    c = conn.cursor()
    db_open = True
    try:
        dbquery=f"SELECT id,name,level,pool_storage,state,compression,acceleration,deduplication,acceleration_storage,system_name,percentage,calculatedRaw,controller_id from multi_device where sds_controller_id = {controller_id}"

        query = c.execute(dbquery)
        dbdata = []
        conn.commit()
        for col in c:
            if(col[12]):
                systemName = getTheSDSPoolName(col[12])+"@"+col[9]
            else:
                systemName = col[9]
            jsonschema = {"id":col[0],"name" : col[1],"level" :col[2],"pool_storage" : col[3],"state":col[4],"compression" :col[5],"acceleration" : col[6],"deduplication":col[7],"acceleration_storage":col[8],"systemName":systemName,"percentage":col[10],"calculatedRaw":col[11],'systemValue' : col[9],"controller_id" : col[12]}
            dbdata.append(jsonschema)


        if True:
            AllocatedHDD = 0
            #dbquery=c.execute("select sum(calculatedRaw+pool_storage) from multi_device where name='HDD POOL'")
            dbquery=c.execute("select sum(calculatedRaw) from multi_device where name='HDD POOL'")
            resp=c.fetchone()[0]
            if (isinstance(resp, int))==True:
                AllocatedHDD=int(resp)

            AllocatedAcceleration = 0.0
            dbquery=c.execute("select sum(acceleration_storage) from multi_device where name='HDD POOL'")
            AllocatedAcceleration = c.fetchone()[0]
            
            AllocatedSSD = 0
            dbquery=c.execute("select sum(calculatedRaw) from multi_device where name='SSD POOL'")
            resp=c.fetchone()[0]
            if (isinstance(resp, int))==True:
                AllocatedSSD=int(resp)

            AllocatediSTOR = 0
            dbquery=c.execute("select sum(calculatedRaw) from multi_device where name='iSCSI POOL'")
            resp=c.fetchone()[0]
            if (isinstance(resp, int))==True:
                AllocatediSTOR=int(resp)

            AllocatedNVMeOF = 0
            dbquery=c.execute("select sum(calculatedRaw) from multi_device where name='NVMeOF POOL'")
            resp=c.fetchone()[0]
            if (isinstance(resp, int))==True:
                AllocatedNVMeOF=int(resp)

            AllocatedMegaRAID = 0
            dbquery=c.execute("select sum(calculatedRaw) from multi_device where name='MegaRAID POOL'")
            resp=c.fetchone()[0]
            if (isinstance(resp, int))==True:
                AllocatedMegaRAID=int(resp)   

            AllocatedHDD = 0
            dbquery=c.execute("select sum(calculatedRaw) from multi_device where name='HDD POOL'")
            resp=c.fetchone()[0]
            if (isinstance(resp, int))==True:
                AllocatedHDD=int(resp)
            

                #get HDD space
            TotalHDDStorage=0
            rotation=1
            query=c.execute("select state,size from disks where rotation=?",[rotation])
            state=0
            size=1
            online=0
            DiskList = c.fetchall()
            for disk in DiskList:
                if disk[state]==online:
                    TotalHDDStorage=TotalHDDStorage+disk[size]
                    #sprint( ("TotalHDDStorage=",TotalHDDStorage))
                    
            #get SSD space
            TotalSSDStorage=0
            rotation=0
            query=c.execute("select state,size,vid,name from disks where rotation=?",[rotation])
            DiskList = c.fetchall()
            for disk in DiskList:
                if not (disk[3].startswith("mr")): 
                    if (disk[0]==0 and disk[2]!="BROADCOM"):
                        TotalSSDStorage=TotalSSDStorage+disk[1]
                    #sprint( ("TotalSSDStorage=",TotalSSDStorage))
            availableHDD=int(TotalHDDStorage)-int(AllocatedHDD)    #This is in GB
            availableSSD=int(TotalSSDStorage)-int(AllocatedSSD)    #This is in GB
            #availableSSD=int(1000*TotalSSDStorage)-int(AllocatedSSD)-int(AllocatedAcceleration)    
            
            availableiSTOR=getAvailableiSTOR()
            availableiSTOR=availableiSTOR-AllocatediSTOR
            
            availableNVMeOF=getAvailableNVMeOF()
            availableNVMeOF=availableNVMeOF-AllocatedNVMeOF

            availableMegaRAID=getAvailableMegaRAID(c,controller_id)
            PoolType="MegaRAID POOL"
            RAIDlevel=getRAIDlevel(PoolType)
            if RAIDlevel==1:
                availableMegaRAID=availableMegaRAID*.745
        
            if AllocatedMegaRAID > availableMegaRAID:
                availableMegaRAID =0
            else:
                availableMegaRAID=availableMegaRAID-AllocatedMegaRAID
            if availableMegaRAID < MIN_FreeSpace:
                availableMegaRAID=0
                

            Disks=getAvailableDisks(c,controller_id, PoolType)

            
        c.close()
        conn.close()
        db_open = False
        return jsonify({
            "poolData":dbdata,"availableDisks":Disks,"availableHDDStorage":availableHDD,
            "availableSSDStorage":availableSSD,"availableMVMeOFStorage":availableNVMeOF,"availableiSTORStorage":availableiSTOR,"availableMegaRAIDStorage":availableMegaRAID,
            "AllocatedHDD":AllocatedHDD,"AllocatedSSD":AllocatedSSD,"AllocatedAcceleration":AllocatedAcceleration
        })
    except Exception as e:
        if db_open:
            c.close()
            conn.close()
        return {"status" : "fail", "description" : str(e)}

def read_sds_host_details(query):
    conn = sqlite3.connect(DB_PATH)
    conn.text_factory = str
    c = conn.cursor()
    db_open = True
    try:
        c.execute(query)
        data = c.fetchall()
        c.close()
        conn.close()
        db_open = False
        return data
    except Exception as e:
        sprint(f"Error in fetching host details: {str(e)}")
        if db_open:
            c.close()
            conn.close()
        return []


def getAvailableSDSStorage():
    return 20*1000

def getSDSHostDetailsById(id):
    conn = sqlite3.connect(DB_PATH)
    conn.text_factory = str
    c = conn.cursor()
    db_open = True
    try:
        dbquery=c.execute("SELECT h.id,h.name,h.protocol,h.user_name,h.   iqn,h.pw,h.wwn,url,p.name,h.host_type,ifnull(h.password_hidden,1) from host  h inner join protocol p on h.protocol = p.id where h.id = ?", [id])
        resp=c.fetchone()
        c.close()
        conn.close()
        db_open = False
        return resp
    except Exception as e:
        if db_open:
            c.close()
            conn.close()
            db_open = False
        return []

def get_SN_PoolsStorage(node_ip):
    try:
        URL = create_url(node_ip)
        pools = requests.get(URL+f"cgi_Pool_Get.py?requestType=read_pool").json()
        return pools
    except Exception as e:
        return []
    
def read_sds_compute_host(computeGroupId):
    conn=sqlite3.connect(DB_PATH)
    conn.text_factory=str
    c=conn.cursor()
    db_open = True
    response = []
    try:
        data = c.execute("select compute_node_id from compute_host_group where host_id = ?", [computeGroupId]).fetchall()
        if not data:
            return []
        
        compute_node_ids = [row[0] for row in data]
        placeholders = ','.join('?' * len(compute_node_ids))
        compute_data = c.execute(f"SELECT id,name,compute_node_ip FROM compute_node WHERE id IN ({placeholders})", compute_node_ids).fetchall()

        for col in compute_data:
            response.append({"id" : col[0], "name" : col[1]+"@"+col[2], "value" : col[2]})
        if db_open :
            c.close()
            conn.close()
            db_open = False
        return response
    except Exception as e:
        return response
# 

def get_remote_id(name,controller_id):
    try:
        node_ip = get_storage_ip_by_controller(controller_id)
        payload = {"node_ip":node_ip,"element" : "volume"}
        response = requests.post(f"http://127.0.0.1:{PORT}"+"/readAllDetails",json=payload).json()
        vol_id = [volume['id'] for volume in response if volume["name"] == name]
        return vol_id[0]
    except Exception as e:
        return 0

def get_remote_host_id_by_name(name,controller_id):
    try:
        node_ip = get_storage_ip_by_controller(controller_id)
        payload = {"node_ip":node_ip,"element" : "host"}
        response = requests.post(f"http://127.0.0.1:{PORT}"+"/readAllDetails",json=payload).json()
        host_id = [host["id"] for host in response if host["name"] == name]
        return host_id[0]
    except Exception as e:
        return 0


def read_SN_ComputeNodes(volumeId):
    conn=sqlite3.connect(DB_PATH)
    conn.text_factory=str
    c=conn.cursor()
    db_open = True
    try:
        volume = c.execute("select computeId from volume where id = ?", [volumeId]).fetchone()
        if not volume:
            return []

        data = c.execute("select compute_node_id from compute_volume_mapping where compute_host_group_id = ? and sds_volume_id = ?", [volume[0],volumeId]).fetchall()
        if not data:
            return []

        compute_node_ids = [row[0] for row in data]
        placeholders = ','.join('?' * len(compute_node_ids))
        compute_data = c.execute(f"SELECT compute_node_ip FROM compute_node WHERE id IN ({placeholders})", compute_node_ids).fetchall()

        if db_open :
            c.close()
            conn.close()
            db_open = False
        return [row[0] for row in compute_data]
    except Exception as e:
        if db_open:
            c.close()
            conn.close()
        return []


def update_pool_from_sds_db(data):
    PoolName = data.get("PoolName")
    Compression = data.get("Compression")
    Deduplication = data.get("Deduplication")
    systemName = data.get("systemName")
    AccelerationPercent = data.get("AccelerationPercent")
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.text_factory = str
        c = conn.cursor()
        db_open = True

        query_FT=c.execute("update multi_device set compression=?,deduplication=?,system_name=?,acceleration=? where system_name=?",[Compression,Deduplication,systemName,AccelerationPercent,PoolName])
        conn.commit()
        c.close()
        conn.close()
        db_open = False

    except Exception as e:
        if db_open:
            c.close()
            conn.close()
        return {"status" : "fail", "description" : str(e)}

def delete_pool_from_sds_db(data):
    PoolName = data.get("name")
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.text_factory = str
        c = conn.cursor()
        db_open = True

        query=c.execute("delete from  multi_device where system_name=?",[PoolName])
        conn.commit()
        
        c.close()
        conn.close()
        db_open = False
    except Exception as e:
        if db_open:
            c.close()
            conn.close()
        return {"status" : "fail", "description" : str(e)}

def DB_Create_SN_VolumeDB(data,poolId,node_ip,controller_id):
    volumeName=data.get("volumeName")
    size=data.get('size') 
    hostId=data.get('hostId')
    dedup=data.get('dedup','false') 
    compression=data.get('compression','false')
    backup_device=data.get('backup_device','false')
    thin=data.get('thin')
    lun=data.get('lun') 
    portId=data.get('portId')
    priority=data.get('priority')
    computeId=data.get('computeId')
    computeHost=data.get('computeHost')

    
    conn=sqlite3.connect(DB_PATH)
    conn.text_factory=str
    c=conn.cursor()

    try:
                        
        volumes = read_SN_Volumes(node_ip)
        remote_id = [volume["id"] for volume in volumes if volume["name"] == volumeName]
        if not remote_id:
            sprint(f"Volume {volumeName} not found in remote storage")
            return
        
        remote_id = remote_id[0]
            
        query=c.execute("insert into  Volume(name,state,size,deduplication,compression,thin,multi_device_id,cr_date,type,sds_group,priority,controller_id,computeId,remote_id) values(?,?,?,?,?,?,?,datetime(),'Native',?,?,?,?,?)",[volumeName,4,size,dedup,compression,thin,poolId,"true",priority,controller_id,computeId,remote_id])
        conn.commit()

        last_id = c.lastrowid

        if last_id:
            volumeId = last_id
            query_SP=c.execute("update volume set backup_device=? where id=?",[backup_device,volumeId])
            query_SP=c.execute("insert into  export(port_id,vol_id,host_id,lun) values(?,?,?,?)",[portId,volumeId,computeId,lun])
            conn.commit()

            # Insert selected compute host
            for compute_node_id in computeHost:
                c.execute("Insert into compute_volume_mapping (sds_volume_id,compute_host_group_id,compute_node_id,volume_name,cr_date) values(?,?,?,?,datetime())",[volumeId,computeId,compute_node_id,volumeName])
                conn.commit()
    
        return {'status':'success','description':'Volume created successfully'}
    except Exception as e:
        sprint(f"Exception in creating volume in DB : {e}")
        return {"description" : str(e), "status" : "fail"}
    finally:
        if c : c.close()
        if conn : conn.close()


def mount_volumes(compute_node_ip, volume, protocol_name, node_ip, host_name, user_name, iqn, pw, wwn, url, steps_info,isNew,volumeId,controller_id,volume_name,storage_node_ip):
    try:
        response = requests.post(
            f"http://127.0.0.1:{PORT}/mountVolume",
            json={
                "volumeName": volume["name"],
                "protocol_name": protocol_name,
                "remote_ip": node_ip,
                "compute_node_ip": compute_node_ip,
                "host_name": host_name,
                "user_name": user_name,
                "ip": iqn,
                "password": pw,
                "wwn": wwn,
                "url": url,
            },
        ).json()
        sprint(f"compute_node_ip {compute_node_ip} {response}")
        if response["status"]:
            if isNew :
                insert_into_storage_compute_vol(volumeId,volume_name,storage_node_ip, compute_node_ip,controller_id)
            steps_info["compute"].append({"compute_node_ip": compute_node_ip, "mount": {"status": True, "message": response["message"], "mount_path": response["mount_path"]}})
        else:
            steps_info["compute"].append(
                {"compute_node_ip": compute_node_ip, "mount": {"status": False, "message": response["message"], "mount_path": response["mount_path"]}}
            )
            steps_info["status"] = False
    except Exception as e:
        steps_info["status"] = False
        steps_info["compute"].append({"compute_node_ip": compute_node_ip, "mount": {"status": False, "message": str(e), "mount_path": "N/A"}})


def unmount_volumes(compute_node_ip, volume, remote_ip, protocol_name, username, pw, iqn, steps_info):
    try:
        response = requests.post(
            f"http://127.0.0.1:{PORT}/unmountVolume",
            json={
                "volumeName": volume["name"],
                "compute_node_ip": compute_node_ip,
                "remote_ip" : remote_ip,
                "protocol_name": protocol_name,
                "ip": iqn,
                "user_name": username,
                "password": pw,
            },
        ).json()
        sprint(f"compute_node_ip {compute_node_ip} {response}")
        if response["status"]:
            steps_info["compute"].append({"compute_node_ip": compute_node_ip, "mount": {"status": True, "message": response["message"], "unmount_path": response["unmount_path"]}})
        else:
            steps_info["compute"].append(
                {"compute_node_ip": compute_node_ip, "mount": {"status": False, "message": response["message"], "unmount_path": response["unmount_path"]}}
            )
            steps_info["status"] = False
    except Exception as e:
        steps_info["status"] = False
        steps_info["compute"].append({"compute_node_ip": compute_node_ip, "mount": {"status": False, "message": str(e), "unmount_path": "N/A"}})




def get_compute_node_ip(volumeId,volume_name,storage_node_ip,controller_id):
    conn=sqlite3.connect(DB_PATH)
    conn.text_factory=str
    c=conn.cursor()
    db_open = True
    compute_node_ip = []
    try:
        c.execute("select compute_node_ip from storage_compute_vol where sds_volume_id=? and volume_name = ? and storage_node_ip = ? and controller_id = ?", [volumeId,volume_name, storage_node_ip, controller_id])
        result = c.fetchall()
        if result:
            compute_node_ip = [item[0] for item in result]
        if db_open:
            c.close()
            conn.close()
            db_open = False
        return compute_node_ip
    except Exception as e:
        if db_open:
            c.close()
            conn.close()
        sprint(f"Excpetion in reading compute_node_ip : {e}")
        return compute_node_ip
def insert_into_storage_compute_vol(volumeId,volume_name,storage_node_ip, compute_node_ip,controller_id):
    conn=sqlite3.connect(DB_PATH)
    conn.text_factory=str
    c=conn.cursor()
    db_open = True
    try:
        c.execute("Insert into storage_compute_vol (sds_volume_id,controller_id,storage_node_ip,compute_node_ip,volume_name,cr_date) values(?,?,?,?,?,datetime())",[volumeId,controller_id,storage_node_ip,compute_node_ip,volume_name])
        conn.commit()
        sprint(f"Compute node details saved into table, Storage Node IP : {storage_node_ip}, Compute Node IP : {compute_node_ip}, Volume Name : {volume_name}, Controller Id : {controller_id}")
        if db_open:
            c.close()
            conn.close()
            db_open = False
    except Exception as e:
        if db_open:
            c.close()
            conn.close()
        sprint(f"Exception in inserting data into storage_compute_vol table : {e}")

def delete_volume_from_storage_compute_vol(volumeId):
    conn=sqlite3.connect(DB_PATH)
    conn.text_factory=str
    c=conn.cursor()
    db_open = True
    try:
        c.execute("delete from storage_compute_vol where sds_volume_id=?",[volumeId])
        conn.commit()
        if db_open:
            c.close()
            conn.close()
            db_open = False
    except Exception as e:
        if db_open:
            c.close()
            conn.close()

def onOff_volume_into_sdsDB(data):
    volumeId = data.get('volumeId')
    volumeState=data.get('state') 

    conn=sqlite3.connect(DB_PATH)
    conn.text_factory=str
    c=conn.cursor()
    db_open = True
    try:
        query=c.execute("update volume set state = ? where id=?",[volumeState,volumeId])
        conn.commit()
        if db_open:
            c.close()
            conn.close()
            db_open = False
    except Exception as e:
        if db_open:
            c.close()
            conn.close()
    
def delete_volume_from_sdsDB(data):
    volumeId = data.get('volumeId')
    volumeType = data.get('volumeType')
    conn=sqlite3.connect(DB_PATH)
    conn.text_factory=str
    c=conn.cursor()
    db_open = True

    try:
        if volumeType == 'Native' or volumeType == 'Foreign':  
            query_lan=c.execute("select count(*) from Volume where state=6 and id='"+ str(volumeId)+"'")
            state = c.fetchone()[0]
            conn.commit()
            if state > 0:
                c.close()
                conn.close()
                return {'status':'fail','description':'Cannot Delete running Volume'}

            query=c.execute("delete from volume where id='"+ str(volumeId)+"'")
            conn.commit()
            query=c.execute("delete from export where vol_id='"+ str(volumeId)+"'")
            conn.commit()

            query = "Delete from vm_storage where volume_id in ("+str(volumeId)+")"
            query_FT=c.execute(query)
            conn.commit()

            query = "Delete from volume_snapshot where vol_id in ("+str(volumeId)+")"
            query_FT=c.execute(query)
            conn.commit()

        else:
            query_lan=c.execute("select count(*) from volume_snapshot where state=6 and id='"+ str(volumeId)+"'")
            state = c.fetchone()[0]
            conn.commit()
            if state > 0:
                return {'status':'fail','description':'Cannot Delete running Volume'}    
            

        if db_open:
            c.close()
            conn.close()
            db_open = False

    except Exception as e:
        if db_open:
            c.close()
            conn.close()
        return {'status':'fail','description': str(e)}  



def deleteFolderFromComputeNode(compute_node_ip,volumeName,node_ip,iqn,user_name, pw, protocol_name,result):
    conn = sqlite3.connect(DB_PATH)
    conn.text_factory = str
    c = conn.cursor()
    db_open = True
    try:
        CLIENT_API_URL = f"http://{compute_node_ip}:{CLIENT_PORT}"
        payload = {"volumeName": volumeName, "node_ip": node_ip, "iqn": iqn, "user_name": user_name, "password": pw, "protocol_name": protocol_name}
        response = requests.delete(f"{CLIENT_API_URL}/deleteFolder", json=payload).json()
        if db_open:
            c.close()
            conn.close()
            db_open = False
        sprint(response)
        result["compute"] = response
        return response
    except Exception as e:
        if db_open:
            c.close()
            conn.close()
        sprint(f"Exception in delete compute volume folder : {e}")
        result["compute"] = {"status": "failure", "message": str(e), "local_path" : "N/A"}
        return {"status": "failure", "message": str(e), "local_path" : "N/A"}

def check_system_exist(data):
    conn = sqlite3.connect(DB_PATH)
    conn.text_factory = str
    c = conn.cursor()
    db_open = True
    try:

        c.execute("select * from system where serial_number = ?",[data[0]["serial_number"]])
        data = c.fetchone()

        c.close()
        conn.close()
        db_open = False
        return data
    except Exception as e:
        if db_open:
            c.close()
            conn.close()
            db_open = False
        return False

def check_controller_already_exist(system_id):
    conn = sqlite3.connect(DB_PATH)
    conn.text_factory = str
    c = conn.cursor()
    db_open = True
    try:

        c.execute("select * from controller where system_id = ?",[system_id])
        data = c.fetchone()

        c.close()
        conn.close()
        db_open = False
        return data
    except Exception as e:
        if db_open:
            c.close()
            conn.close()
            db_open = False
        return False

def check_data_exists(table_name,controller_id):
    conn = sqlite3.connect(DB_PATH)
    conn.text_factory = str
    c = conn.cursor()
    db_open = True
    try:

        c.execute(f"select * from {table_name} where controller_id = ?",[controller_id])
        data = c.fetchone()

        c.close()
        conn.close()
        db_open = False
        return data
    except Exception as e:
        if db_open:
            c.close()
            conn.close()
            db_open = False
        return False

def compare_and_update_system_controller_table(c,table, key_fields, data, extra_keys=None):
    """
    Compare and update an existing record in a table based on key_fields.
    Returns:
        - record_id (int): ID of the record that was found or updated
        - -2 if record not found
        - -1 if an exception occurred
    """
    try:
        

        merged_data = dict(data)
        if extra_keys:
            merged_data.update(extra_keys)

        # Build WHERE clause
        where_clause = " AND ".join([f'"{k}"=?' for k in key_fields])
        where_values = [merged_data[k] for k in key_fields]

        # Fetch existing record
        c.execute(f"SELECT * FROM {table} WHERE {where_clause}", where_values)
        existing = c.fetchone()

        if not existing:
            # No record found
            return -2

        # Get record ID and current values
        db_columns = [col[1] for col in c.execute(f"PRAGMA table_info({table})").fetchall()]
        db_dict = dict(zip(db_columns, existing))
        record_id = db_dict.get("id")

        # Compare fields and collect differences
        updated_fields = {}
        for field, value in merged_data.items():
            if field == "id" or field in key_fields:
                continue
            if field in db_dict and str(db_dict[field]) != str(value):
                updated_fields[field] = value

        # Perform update if necessary
        if updated_fields:
            set_clause = ", ".join([f'"{key}"=?' for key in updated_fields.keys()])
            values = list(updated_fields.values()) + where_values
            sql = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"
            c.execute(sql, values)
            c.connection.commit()
            sprint(f"✅ Updated {table} (ID {record_id}) with {updated_fields}")
        else:
            pass

        return record_id

    except Exception as e:
        sprint(f"❌ Exception in compare_and_update_system_controller_table for {table}: {e}")
        return -1


def normalize_value(val):
    """
    Normalize DB and incoming values for consistent comparison.
    Treat None and '' as equal.
    """
    # Convert None or empty strings to None
    if val is None or (isinstance(val, str) and val.strip() == ""):
        return None
    
    # Convert 'None', 'null', 'NULL' text to None
    if isinstance(val, str) and val.strip().lower() in ["none", "null"]:
        return None
    
    # Convert boolean-like strings
    if isinstance(val, str) and val.strip().lower() in ["true", "false"]:
        return val.strip().lower() == "true"
    
    # Try to convert numeric strings to numbers
    if isinstance(val, str):
        try:
            if "." in val:
                return float(val)
            return int(val)
        except ValueError:
            return val.strip()

    return val


def compare_and_update_table_data(c, table, data, SN_controller_id, local_id):
    """
    Returns:
        >0 : local_id (success, record found)
         -2 : No update needed (data identical)
         -1 : Exception occurred
          0 : No mapping or record not found
    """
    try:

        # 2️Fetch existing row using local_id
        c.execute(f"SELECT * FROM {table} WHERE id=?", [local_id])
        record_exist = c.fetchone()
        if not record_exist:
            sprint(f"⚠️ No existing record found in {table} for local_id={local_id}")
            return 0

        # 3️⃣ Get DB column names
        db_columns = [col[1] for col in c.execute(f"PRAGMA table_info({table})").fetchall()]
        db_dict = dict(zip(db_columns, record_exist))

        # 4️⃣ Merge controller_id if applicable
        data_with_controller = dict(data)
        if "controller_id" in db_columns:
            data_with_controller["controller_id"] = SN_controller_id

        # 5️⃣ Compare fields (ignore id)
        updated_fields = {}
        for field, value in data_with_controller.items():
            if field == "id":
                continue
            if field in db_dict:
                db_val = normalize_value(db_dict[field])
                new_val = normalize_value(value)
                if db_val != new_val:
                    updated_fields[field] = value

        # 6️⃣ Perform update if differences exist
        if updated_fields:
            set_clause = ", ".join([f"{key}=?" for key in updated_fields.keys()])
            values = list(updated_fields.values()) + [local_id]
            sql = f"UPDATE {table} SET {set_clause} WHERE id=?"
            c.execute(sql, values)
            c.connection.commit()
            
            sprint(f"Updated {table} (ID: {local_id}) with fields: {list(updated_fields.keys())}")
            return local_id  # Success: record updated

        else:
            #sprint(f"ℹ️ No changes detected in {table} for local_id={local_id}")
            return -2  # No update needed

    except Exception as e:
        sprint(f"❌ Exception in compare_and_update_table_data for {table}: {e}")
        return -1


def normalize_and_merge(existing_row, new_data, key_map=None):
    """
    Performs:
    1. Key renaming using key_map
    2. camelCase → snake_case normalization
    3. Merge into existing_row (existing values retained if missing)

    Returns a NEW merged dict.
    """

    if key_map is None:
        key_map = {}

    merged = {}

    for key, new_value in new_data.items():

        # Step 1: rename key if needed
        if key in key_map:
            if key_map[key] is None:
                continue
            k2 = key_map[key]
        else:
            k2 = key

        # Step 2: camelCase → snake_case
        normalized = ""
        for c in k2:
            if c.isupper():
                normalized += "_" + c.lower()
            else:
                normalized += c
        normalized = normalized.lstrip("_")

        merged[normalized] = new_value

    # Step 3: Fill missing fields with existing values
    final_data = existing_row.copy()
    final_data.update(merged)

    return final_data

def update_if_changed(c,table, new_data, existing_data, where_keys, exclude=None):
    """
    Generic dynamic UPDATE:
    - Updates only fields that changed
    - Skips excluded fields
    - Builds WHERE using where_keys
    """
    try:
        if exclude is None:
            exclude = set()
        else:
            exclude = set(exclude)

        update_fields = []
        update_values = []
        if table == "eth_ports":
            g_exclude = {k for k in new_data.keys() if k.startswith("g_")}
            exclude.update(g_exclude)
        if table == "controller":
            v_exclude = {k for k in new_data.keys() if k.startswith("V_")}
            exclude.update(v_exclude)

        for key, new_value in new_data.items():
            #print(f"Comparing field: {key} | New: {new_value} | Old: {existing_data.get(key)}")
            #print(f"Comparing field: {type(key)} | New: {type(new_value)} | Old: {type(existing_data.get(key))}")
            #print("-----")

            if key in exclude:
                continue
            
            old_value = existing_data.get(key)

            # Normalize both sides for comparison
            if old_value is None and new_value is None:
                continue

            # Convert both to string for safe comparison of "2.07" vs 2.07
            old_norm = str(old_value) if old_value is not None else None
            new_norm = str(new_value) if new_value is not None else None

            if old_norm != new_norm:
                update_fields.append(f"`{key}` = ?")
                update_values.append(new_value)

        # Nothing changed → skip
        if not update_fields:
            return -2   # No update

        # Build WHERE clause
        where_clause = " AND ".join(f"{k} = ?" for k in where_keys)
        where_values = [new_data[k] for k in where_keys]

        query = f"""
            UPDATE {table}
            SET {', '.join(update_fields)}
            WHERE {where_clause}
        """
        #print(query)
        c.execute(query, update_values + where_values)
        c.connection.commit()
        
        return 1
    except Exception as e:
        sprint(f" Exception in update_if_changed for {table}: {e}")
        time.sleep(10)
        return -1

    
def DB_Create_SN_Get_System(SN_system_info):   
    res = -1 
    system_info=SN_system_info

    system_name = system_info.get("name", "Unknown System")
    state = system_info.get("state", "unknown")
    serial_number = system_info.get("serial_number", "unknown")
    cr_date = system_info.get("cr_date", "unknown")
    total_memoryGB = system_info.get("total_memoryGB", 0)
    total_storageGB = system_info.get("total_storageGB", 0)
    total_vcpu = system_info.get("total_vcpu", 0)
    used_memoryGB = system_info.get("used_memoryGB", 0)
    used_storageGB = system_info.get("used_storageGB", 0)
    used_vcpu = system_info.get("used_vcpu", 0)
    location = system_info.get("location", "unknown")
    build = system_info.get("build", "unknown")
    retail_version = system_info.get("retail_version", "unknown")
    oem = system_info.get("oem", "unknown")
    cba_identitySerial = system_info.get("cba_identitySerial", "unknown")
    cba_reportSerial = system_info.get("cba_reportSerial", "unknown")
    FactoryBoot = system_info.get("FactoryBoot", "unknown")
    lastGoodBoot = system_info.get("lastGoodBoot", "unknown")
    CurrentBoot = system_info.get("CurrentBoot", "unknown")
    reset_on_extraction = system_info.get("reset_on_extraction", 0)
    reset_on_db = system_info.get("reset_on_db", 0)
    pool_manager = system_info.get("pool_manager", "unknown")
    megaRaid_support = system_info.get("megaRaid_support", 0)
    uuid = system_info.get("uuid", "unknown")

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.text_factory = str
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            # check serial number already exist or not
            c.execute("select * from system where serial_number=?",[system_info["serial_number"]])
            existing_record = c.fetchone()
            if not existing_record:
                # Insert into System
                c.execute('''INSERT  INTO system ("name", "state", "cr_date", "location", "total_vcpu", "total_memoryGB", "total_storageGB", "used_vcpu", "used_memoryGB", "used_storageGB", "FactoryBoot", "lastGoodBoot", "CurrentBoot", "serial_number", "build", "retail_version", "oem", "cba_identitySerial", "cba_reportSerial", "reset_on_extraction", "reset_on_db", "pool_manager", "megaRaid_support","uuid")VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                (system_name, state, cr_date,location, total_vcpu, total_memoryGB, total_storageGB, used_vcpu, used_memoryGB, used_storageGB, FactoryBoot, lastGoodBoot, CurrentBoot, serial_number, build, retail_version, oem, cba_identitySerial, cba_reportSerial, reset_on_extraction, reset_on_db, pool_manager, megaRaid_support,uuid))
                conn.commit()

                if c.lastrowid:
                    system_id = c.lastrowid
                else:
                    system_id = -1
                return system_id
            else:
                # Update into system 
                existing_row= dict(existing_record)
                exclude = {"id", "cr_date", "del_date"}
                result = update_if_changed(
                        c,
                        table="system",
                        new_data=system_info,
                        existing_data=existing_row,
                        where_keys=["serial_number"],
                        exclude=exclude
                    )

                if result == -2:
                    # sprint("System already up-to-date",0)
                    pass
                elif result == -1:
                    sprint("Error updating System",0)
                else:
                    sprint("System updated successfully",0)

                return existing_row["id"]
    except Exception as e:
        sprint("Error in Creating System Entry in DB :" ,str(e))    
        return res
    
def DB_Create_SN_Get_Controller(SN_controller_info,SDS_sys_id,SN_ip):
    """
    Create or update a controller record linked to a system.
    Returns:
        controller_id (int) - ID of the inserted or existing controller
        -1 on exception
    """
    res =-1
    controller_info=SN_controller_info

    SN_cont_name = controller_info.get("name", "Unknown Controller")
    controller_state = controller_info.get("state", "unknown")
    cr_date = controller_info.get("cr_date", "unknown")
    location = controller_info.get("location", "unknown")
    default = controller_info.get("default", 0)
    low_threshold = controller_info.get("low_threshold", 0)
    t_min = controller_info.get("t_min", 0)
    hi_threshold = controller_info.get("hi_threshold", 0)
    t_max = controller_info.get("t_max", 0)

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.text_factory = str
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            c.execute("select * from controller where system_id = ?",[SDS_sys_id])
            existing_record = c.fetchone()
            if not existing_record:
                c.execute('''INSERT INTO controller ("name", "state", "cr_date", "system_id", "location", "default", "low_threshold", "t_min", "hi_threshold", "t_max") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                (SN_cont_name, controller_state, cr_date, SDS_sys_id, location, default, low_threshold, t_min, hi_threshold, t_max))
                conn.commit()
                if c.lastrowid:
                    sds_cont_id=c.lastrowid
                else:
                    return -1
            else:
                # --------------------------
                # UPDATE existing controller
                # --------------------------
                existing_row= dict(existing_record)
                sds_cont_id = existing_row["id"]#existing_record[0]
                exclude_keys = {"id", "cr_date", "del_date", "system_id","edit_date",}
                where_keys=["system_id"]

                result = update_if_changed(
                        c,
                        table="controller",
                        new_data=controller_info,
                        existing_data=existing_row,
                        where_keys=where_keys,
                        exclude=exclude_keys
                    )

                if result == -2:
                    # sprint("Controller already up-to-date",0)
                    pass
                elif result == -1:
                    sprint("Error updating Controller",0)
                else:
                    sprint("Controller updated successfully",0)

            # --------------------------
            # Store Storage Node IP
            # --------------------------
            c.execute("select * from storage_node where ip = ? and controller_id = ?", [SN_ip,sds_cont_id])
            storage_node = c.fetchone()
            if not storage_node:
                c.execute("insert into storage_node (ip,controller_id,active) values(?,?,?)", [SN_ip,sds_cont_id,"yes"])
                conn.commit() 
            
            return sds_cont_id
    except Exception as e:
        sprint("Error in Creating Controller Entry in DB :" ,str(e))
        return res

def DB_Create_SN_Disks(SN_Disk_info, SDS_Cont_id):
    """
    Insert/update/delete disks for a controller.
    Returns:
        1  -> success
       -1  -> error
    """
    result = -1
    conn = None
    c = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.text_factory = str
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        not_inserted = []

        for disk in SN_Disk_info:

            d_sys_name = disk.get("system_name", "Unknown Disk")
            d_name= disk.get("name", "Unknown Disk")
            d_state= disk.get("state", "unknown")
            d_id = disk.get("d_id", 0)
            d_loc = disk.get("location", "unknown")
            d_type = disk.get("type", "unknown")
            d_size = disk.get("size", 0)
            d_interface = disk.get("interface", "unknown")
            d_multi_device_id = disk.get("multi_device_id", "unknown")
            d_vid = disk.get("vid", "unknown")
            d_pid = disk.get("pid", "unknown")
            d_prl = disk.get("prl", "unknown")
            d_rev = disk.get("rev", "unknown")
            d_serial = disk.get("serial", "unknown")
            d_wwn = disk.get("wwn", "unknown")
            d_tx_rx_def = disk.get("tx_rx_default")
            d_err_thres=disk.get("err_threshold")
            d_err_max=disk.get("err_max")
            d_txrx_mon=disk.get("tx_rx_monitor")
            d_temp=disk.get("temp")
            d_def=disk.get("default")
            d_lo_thresh = disk.get("low_threshold")
            d_t_min = disk.get("t_min")
            d_hi_thresh = disk.get("hi_threshold")
            d_t_max = disk.get("t_max")
            d_temp_def = disk.get("temp_default")
            d_rotation = disk.get("rotation")
            d_smart_status = disk.get("smart_status")
            d_smart_test= disk.get("smart_test")
            d_remote_id = disk.get("id")

            try:
                c.execute("select * from disks where controller_id = ? and remote_id = ?", [SDS_Cont_id, d_remote_id])
                existing_mapping = c.fetchone()

                if not existing_mapping:
                    # Insert disk
                    c.execute("""
                        INSERT INTO disks (
                            system_name, name, state, d_id, controller_id, location,
                            type, size, interface, multi_device_id, vid, pid, prl, rev, serial, wwn,
                            tx_rx_default, err_threshold, err_max, tx_rx_monitor, temp, [default], low_threshold,
                            t_min, hi_threshold, t_max, temp_default, rotation, smart_status, smart_test,remote_id
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """, 
                    (d_sys_name, d_name, d_state, d_id, SDS_Cont_id, d_loc,
                    d_type, d_size, d_interface, d_multi_device_id, d_vid, d_pid, d_prl, d_rev, d_serial, d_wwn,
                    d_tx_rx_def, d_err_thres, d_err_max, d_txrx_mon, d_temp,d_def, d_lo_thresh,
                    d_t_min, d_hi_thresh, d_t_max, d_temp_def, d_rotation, d_smart_status, d_smart_test,d_remote_id))
                    conn.commit()

                    # c.execute("SELECT id FROM disks WHERE name = ? AND controller_id = ?", [disk.get("name"), SDS_Cont_id])
                    # row = c.fetchone()
                    if not c.lastrowid:
                        not_inserted.append(disk.get("name"))
                        conn.rollback()
                        continue

                    sprint("Inserted disk ",disk.get('name'))

                else:
                    existing_row= dict(existing_mapping)
                    exclude_keys = {"id", "cr_date", "edit_date","del_date","controller_id"}
                    where_keys=["controller_id","remote_id"]
                    disk["remote_id"] = existing_row["remote_id"]
                    disk["controller_id"] = existing_row["controller_id"]
                    result = update_if_changed(
                            c,
                            table="disks",
                            new_data=disk,
                            existing_data=existing_row,
                            where_keys=where_keys,
                            exclude=exclude_keys
                        )

                    if result == -2:
                        # sprint("Disk Data already up-to-date",0)
                        pass
                        #conn.rollback()
                    elif result == -1:
                        sprint("Error updating Disk Data",0)
                        conn.rollback()
                    else:
                        sprint("Disk Data updated successfully",0)

            except Exception as per_disk_err:
                conn.rollback()
                sprint(f"Exception while processing disk '{disk.get('name')}' : {per_disk_err}")

        # cleanup stale disks
        try:
            source_names = [d.get("name") for d in SN_Disk_info]
            c.execute("SELECT id, name FROM disks WHERE controller_id = ?", [SDS_Cont_id])
            existing = c.fetchall()
            for did, dname in existing:
                if dname not in source_names:
                    c.execute("DELETE FROM disks WHERE id=?", [did])
                    sprint(f"🗑️ Removed stale disk '{dname}'")
            conn.commit()
        except Exception as cleanup_err:
            conn.rollback()
            sprint(f"Exception during disk cleanup: {cleanup_err}")

        if not_inserted:
            for name in not_inserted:
                sprint(f"Disk not inserted: {name}")

        result = 1
        return result

    except Exception as e:
        sprint(f"Exception in DB_Create_SN_Disks: {e}")
        if conn:
            conn.rollback()
        return -1
    finally:
        if c:
            c.close()
        if conn:
            conn.close()
    

def DB_Create_SN_EthPorts(SN_eth_info, SDS_Cont_id):
    """
    Insert, update, or delete Ethernet ports (eth_ports + gateway) for a controller.
    Returns:
        1  → Success
        0  → Nothing inserted/updated
        -1 → Error
    """
    result = -1
    db_open = False
    data_not_inserted = []

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.text_factory = str
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        db_open = True

        for ethport in SN_eth_info:

            port_sys_name = ethport.get("system_name", "Unknown EthPort")
            port_name = ethport.get("name", "Unknown EthPort")
            port_state = ethport.get("state", "unknown")
            cr_date = ethport.get("cr_date", "unknown")
            edit_date = ethport.get("edit_date", "unknown")
            controller_id = SDS_Cont_id
            location = ethport.get("location", "unknown")
            ip = ethport.get("ip")
            netmask = ethport.get("netmask")
            dhcp_enabled = ethport.get("dhcp_enabled", 0)
            port_id = ethport.get("port_id", 0) 
            enable_port = ethport.get("enable_port", 0)
            speed = ethport.get("speed", 0)
            tx_rx_default = ethport.get("tx_rx_default", 0)
            err_threshold = ethport.get("err_threshold", 0)
            err_max = ethport.get("err_max", 0)
            tx_rx_monitor = ethport.get("tx_rx_monitor", 0)
            mtu_size = ethport.get("mtu_size", 0)
            remote_id = ethport.get("id")
                # Gateway fields
            g_system_name = ethport.get("g_system_name", port_sys_name)
            g_name = ethport.get("g_name", "Unknown Gateway")
            g_state = ethport.get("g_state", "unknown")
            g_cr_date = ethport.get("g_cr_date", "unknown")
            g_edit_date = ethport.get("g_edit_date", "unknown")
            g_location = ethport.get("g_location", "unknown")
            g_default_gateway_ip = ethport.get("g_default_gateway_ip")
            g_dns_server = ethport.get("g_dns_server")

            try:
                # --- Check if eth_port already exists in mapping ---
                c.execute("select * from eth_ports where system_name = ? and controller_id = ? and remote_id = ?", [port_sys_name, SDS_Cont_id, ethport["id"]])

                mapping_row = c.fetchone()

                if not mapping_row:
                    # --- INSERT new eth_port ---
                    c.execute('''INSERT INTO eth_ports (
                        system_name, name, state, cr_date, edit_date,controller_id, location,
                        ip, netmask, dhcp_enabled, port_id, enable_port, speed, tx_rx_default,
                        err_threshold, err_max, tx_rx_monitor, mtu_size,remote_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,?)''', 
                    (port_sys_name, port_name, port_state, cr_date, edit_date, controller_id, location,
                     ip, netmask, dhcp_enabled, port_id, enable_port, speed, tx_rx_default,
                     err_threshold, err_max, tx_rx_monitor, mtu_size,remote_id))

                    if not c.lastrowid:
                        data_not_inserted.append(port_sys_name)
                        sprint(f"Failed to verify insertion of eth_port {port_sys_name}")
                        continue

                    # --- Insert into gateway ---
                    c.execute('''INSERT INTO gateway (
                        system_name, name, state, cr_date, edit_date,
                        controller_id, location, default_gateway_ip, dns_server
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                    (g_system_name, g_name, g_state, g_cr_date, g_edit_date,controller_id,g_location,
                      g_default_gateway_ip, g_dns_server))
                    

                    sprint(f"Inserted eth_port '{port_sys_name}' and gateway successfully.")
                    conn.commit()

                else:
                    # --- UPDATE existing eth_port ---
                    existing_row= dict(mapping_row)
                    
                    exclude_keys = {"id", "cr_date", "edit_date","del_date","controller_id"}
                    where_keys=["controller_id","remote_id"]#: SDS_sys_id}
                    ethport["remote_id"] = existing_row["remote_id"]
                    ethport["controller_id"] = existing_row["controller_id"]
                    result = update_if_changed(
                            c,
                            table="eth_ports",
                            new_data=ethport,
                            existing_data=existing_row,
                            where_keys=where_keys,
                            exclude=exclude_keys
                        )

                    if result == -2:
                        # sprint("Port Data already up-to-date")
                        pass
                        #conn.rollback()
                    elif result == -1:
                        sprint("Error updating Port Data")
                        conn.rollback()
                    else:
                        sprint("Port Data updated successfully")
                    
                    # --- Update gateway data ---
                    c.execute('''UPDATE gateway 
                                 SET default_gateway_ip=?, dns_server=?, location=? 
                                 WHERE system_name=? AND controller_id=?''',
                              [g_default_gateway_ip, g_dns_server,
                               g_location, g_system_name, SDS_Cont_id])
                    
                    conn.commit()


            except Exception as per_eth_err:
                conn.rollback()
                sprint(f"Exception while processing eth_port '{ethport.get('system_name', 'unknown')}' : {per_eth_err}")

        # --- Handle missing eth_ports cleanup ---
        try:
            source_eth_names = [item["system_name"] for item in SN_eth_info]
            c.execute("SELECT id, system_name FROM eth_ports WHERE controller_id = ?", [SDS_Cont_id])
            existing_ethports = c.fetchall()

            for eth_id, eth_name in existing_ethports:
                if eth_name not in source_eth_names:
                    # Delete dependent entries
                    c.execute("DELETE FROM gateway WHERE controller_id=? AND system_name=?", [SDS_Cont_id, eth_name])
                    c.execute("DELETE FROM eth_ports WHERE id=?", [eth_id])
                    sprint(f"Removed stale eth_port '{eth_name}'")

            conn.commit()
        except Exception as cleanup_err:
            conn.rollback()
            sprint(f"Exception during eth_port cleanup: {cleanup_err}")

        # --- Final report ---
        if data_not_inserted:
            for name in data_not_inserted:
                sprint(f"eth_port '{name}' not inserted properly.")
        result = 1

    except Exception as e:
        sprint(f"Exception in DB_Create_SN_EthPorts: {e}")
        if db_open:
            conn.rollback()
    finally:
        if db_open:
            c.close()
            conn.close()
            db_open = False

    return result

#------------------------------
#Storage Node Pools
#------------------------------ 

def DB_Create_SN_Pool(SN_disks_info, SDS_Cont_id):
    """
    Insert/update/delete multi_device (pools) entries for a controller.
    Returns:
        1  -> success
        0  -> nothing inserted/updated
       -1  -> error
    """
    result = -1
    conn = None
    c = None
    try:
        if not isinstance(SN_disks_info, dict) or 'poolData' not in SN_disks_info:
            sprint("poolData not found in request")
            return -1

        pools = SN_disks_info['poolData']
        conn = sqlite3.connect(DB_PATH)
        conn.text_factory = str
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        not_inserted = []

        for pool in pools:
            try:
                p_name = pool.get("name", "Unknown Pool")
                p_state = pool.get("state", "unknown")
                p_compression = pool.get("compression", "unknown")
                p_acceleration = pool.get("acceleration", "unknown")
                p_deduplication = pool.get("deduplication", "unknown")
                p_system_name = pool.get("systemName", "unknown")
                p_level = pool.get("level", "unknown")
                p_pool_storage = pool.get("pool_storage", 0)
                p_acceleration_storage = pool.get("acceleration_storage", 0)
                p_percentage = pool.get("percentage", 0)
                p_calculatedraw = pool.get("calculatedRaw", 0)
                p_remote_id = pool.get("id")

                # Check mapping
                c.execute("select * from multi_device where sds_controller_id = ? and remote_id = ?", [SDS_Cont_id, p_remote_id])
                mapping_row = c.fetchone()

                if not mapping_row:
                    # Insert
                    c.execute("""
                        INSERT INTO multi_device (
                            name, state, compression, acceleration, deduplication, system_name, level,
                            pool_storage, acceleration_storage, percentage, calculatedraw, controller_id, sds_controller_id,remote_id
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (p_name,p_state,p_compression,p_acceleration,p_deduplication, p_system_name,p_level,
                          p_pool_storage,p_acceleration_storage,p_percentage,p_calculatedraw, pool.get("controller_id") if "controller_id" in pool else None,
                          SDS_Cont_id, p_remote_id))

                    if not c.lastrowid:
                        not_inserted.append(p_system_name)
                        conn.rollback()
                        continue

                    sprint(f"Inserted pool '{p_system_name}'")

                else:
                    existing_row= dict(mapping_row)
                    exclude_keys = {"id", "cr_date", "edit_date","del_date","sds_controller_id"}
                    where_keys=["sds_controller_id","remote_id"]
                    pool["remote_id"] = existing_row["remote_id"]
                    pool["sds_controller_id"] = existing_row["sds_controller_id"]
                    key_map = {
                    "systemName": "system_name",
                    "calculatedRaw": "calculatedraw",
                    "systemValue": None
                    }
                    update_data = normalize_and_merge(existing_row, pool, key_map)
                    result = update_if_changed(
                            c,
                            table="multi_device",
                            new_data=update_data,
                            existing_data=existing_row,
                            where_keys=where_keys,
                            exclude=exclude_keys
                        )

                    if result == -2:
                        # sprint("Pool Data already up-to-date",0)
                        pass
                        #conn.rollback()
                    elif result == -1:
                        sprint("Failed to update pool ",0)
                        conn.rollback()
                    else:
                        sprint("pool updated successfully",p_name)

            except Exception as per_pool_err:
                conn.rollback()
                sprint(f"Exception while processing pool '{pool.get('systemName')}' : {per_pool_err}")

        # cleanup stale pools
        try:
            source_names = [p.get("systemName") for p in pools]
            c.execute("SELECT id, system_name FROM multi_device WHERE sds_controller_id = ?", [SDS_Cont_id])
            existing = c.fetchall()
            for pid, pname in existing:
                if pname not in source_names:
                    c.execute("DELETE FROM multi_device WHERE id = ?", [pid])
                    sprint(f"🗑️ Removed stale pool '{pname}'")
            conn.commit()
        except Exception as cleanup_err:
            conn.rollback()
            sprint(f"Exception during pool cleanup: {cleanup_err}")

        if not_inserted:
            for name in not_inserted:
                sprint(f"Pool not inserted: {name}")

        result = 1
        return result

    except Exception as e:
        sprint(f"Exception in DB_Create_SN_Pool: {e}")
        if conn:
            conn.rollback()
        return -1
    finally:
        if c:
            c.close()
        if conn:
            conn.close()

#------------------------------
#Storage Node Hosts

def read_SN_Hosts(node_ip):
    try:
        URL = create_url(node_ip)
        data = requests.get(f"{URL}cgi_HostManager.py?requestType=read_Host&hostId=0")
        return data.json()
    except Exception as e:
        sprint(f"Error in fetching hosts data from {node_ip} : {str(e)}")
        return {"error" : -2}

def DB_Create_SN_Host(SN_Host_info, SDS_Cont_id):
    """
    Insert/update/delete hosts for a controller.
    Returns:
        1  -> success
        0  -> nothing inserted/updated
       -1  -> error
    """
    result = -1
    conn = None
    c = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.text_factory = str
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        not_inserted = []

        for host in SN_Host_info:
            try:
                h_name = host.get("name")
                h_usr_name = host.get("user_name")
                h_iqn = host.get("iqn")
                h_wwn = host.get("wwn")
                h_pw = host.get("pw")
                h_prot_id = host.get("protocol_id")
                h_url = host.get("url")            
                h_type = host.get("host_type")
                h_pwd_hdn = host.get("password_hidden")
                h_remote_id = host.get("id")

                if h_type in ["Compute Node Group","SDS Group"]:
                    # sprint(f"Skipping host '{h_name}' of type '{h_type}'")
                    continue

                c.execute("select * from host where controller_id = ? and remote_id = ? and host_type = ?", [SDS_Cont_id, host.get("id"), host.get("host_type")])
                mapping_row = c.fetchone()

                if not mapping_row:
                    # Insert host
                    c.execute("""
                        INSERT INTO host (
                            name, user_name, iqn, wwn, pw, protocol, url, host_type, password_hidden, controller_id,remote_id
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,?)
                    """,(h_name,h_usr_name,h_iqn,h_wwn,h_pw,h_prot_id,h_url,h_type,h_pwd_hdn,SDS_Cont_id,h_remote_id))

                    if not c.lastrowid:
                        not_inserted.append(host.get("name"))
                        conn.rollback()
                        continue

                    sprint(f"Inserted host '{host.get('name')}'")

                else:
                    existing_row= dict(mapping_row)
                    exclude_keys = {"id", "cr_date", "edit_date","del_date","controller_id","protocol_name"}
                    where_keys=["controller_id","remote_id"]
                    host["remote_id"] = existing_row["remote_id"]
                    host["controller_id"] = existing_row["controller_id"]
                    key_map = {
                    "protocol_id": "protocol"
                    }
                    update_data = normalize_and_merge(existing_row, host, key_map)
                    result = update_if_changed(
                            c,
                            table="host",
                            new_data=update_data,
                            existing_data=existing_row,
                            where_keys=where_keys,
                            exclude=exclude_keys
                        )

                    if result == -2:
                        # sprint("Host Data already up-to-date",0)
                        pass
                    elif result == -1:
                        sprint("Failed to update host '{host.get('name')}'")
                        conn.rollback()
                    else:
                        sprint("host updated successfully",h_name)

            except Exception as per_host_err:
                conn.rollback()
                sprint(f"Exception while processing host '{host.get('name')}' : {per_host_err}")

        # cleanup stale hosts
        try:
            source_names = [h.get("name") for h in SN_Host_info]
            c.execute("SELECT id, name FROM host WHERE controller_id = ?", [SDS_Cont_id])
            existing = c.fetchall()
            for hid, hname in existing:
                if hname not in source_names:
                    c.execute("DELETE FROM host WHERE id=?", [hid])
                    sprint(f"🗑️ Removed stale host '{hname}'")
            conn.commit()
        except Exception as cleanup_err:
            conn.rollback()
            sprint(f"Exception during host cleanup: {cleanup_err}")

        if not_inserted:
            for name in not_inserted:
                sprint(f"Host not inserted: {name}")

        result = 1
        return result

    except Exception as e:
        sprint(f"Exception in DB_Create_SN_Host: {e}")
        if conn:
            conn.rollback()
        return -1
    finally:
        if c:
            c.close()
        if conn:
            conn.close()

#------------------------------
#End Storage Node Hosts
#------------------------------

#------------------------------
#Storage Node Volumes

def read_SN_Volumes(node_ip):
    try:
        URL = create_url(node_ip)
        data = requests.get(f"{URL}cgi_VolumeManager.py?requestType=read_Volume&volumeId=0")
        return data.json()
    except Exception as e:
        sprint(f"Error in fetching volumes data from {node_ip} : {str(e)}")
        return {"error" : -2}#------------------------------

def insert_update_vol_export_sds(c,volume, id, SDS_Cont_id,isCreate=True):
    try:
    
        # fetch host local id from host for export
        c.execute("select id from host where remote_id = ? and controller_id = ?", [volume["hostId"],SDS_Cont_id])
        host_id = c.fetchone()

        # fetch Eth Ports local id from eth_ports for export
        
        c.execute("select id from eth_ports where remote_id = ? and controller_id = ?", [volume["portId"],SDS_Cont_id])
        portId = c.fetchone()

        if host_id and portId:
            host_id = host_id[0]
            portId = portId[0]
            
            if isCreate:
                c.execute("insert into export(port_id,vol_id,host_id,lun) values(?,?,?,?)",[portId,id,host_id,volume["lun"]])
            else:
                c.execute("update export set port_id=?,host_id=?,lun=? where vol_id = ?",[portId,host_id,volume["lun"],id])
        
        return 1

    except Exception as e:
        message = f"Exception in export table : {str(e)}"
        sprint(message)
        return -1

    
def DB_Create_SN_Volume(SN_vol_info,SDS_Cont_id):
    res = -1
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.text_factory = str
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        db_open = True
        data_not_inserted = []
        for volume in SN_vol_info:
            v_name = volume.get("name","unknown")
            v_state = volume.get("state","1")
            v_pool_id = volume.get("poolId")
            v_size = volume.get("size")
            v_comp = volume.get("compression")
            v_dedup = volume.get("deduplication")
            v_bkp_dvc = volume.get("backup_device")
            v_type = volume.get("type")
            v_thin = volume.get("thin")
            SDS_Cont_id=int(SDS_Cont_id)
            remote_vol_id = volume.get("id")
            vol_type = volume.get("volumeType","unknown")
            if vol_type == "SDS":
                # sprint(f"Skipping SDS volume '{v_name}'")
                continue
            if v_type in ["Snapshot", "SnapClone"]:
                continue

            c.execute("""SELECT * FROM volume WHERE controller_id=? AND (sds_group IS NULL OR sds_group = '' OR sds_group = 'false')  AND name=? AND remote_id=?""",[SDS_Cont_id,v_name,remote_vol_id])
            mapping_row = c.fetchone()

            if not mapping_row:
                try:
                    c.execute("Insert into volume ( name, state, multi_device_id, size, compression, backup_device, type, thin,controller_id,remote_id) values(?,?,?,?,?,?,?,?,?,?)", 
                        (v_name,v_state,v_pool_id,v_size,v_comp,v_bkp_dvc,v_type,v_thin,SDS_Cont_id,remote_vol_id))

                    if c.lastrowid:
                        inserted_row_id = c.lastrowid
                    else:
                        data_not_inserted.append(volume["name"])
                        break

                    res_export = insert_update_vol_export_sds(c,volume,inserted_row_id,SDS_Cont_id,isCreate=True)
                    if res_export == -1:
                        print("Failed to insert export Info for volume in EXPORT Table",0)

                    conn.commit()

                    sprint(f"{volume['name']} is saved into volume table")
                except Exception as e:
                    conn.rollback()
                    sprint(f"Failed to insert volume {volume['name']} : {e}")
            else:
                existing_row= dict(mapping_row)
                where_keys=["controller_id","remote_id"]
                volume["remote_id"] = existing_row["remote_id"]
                volume["controller_id"] = existing_row["controller_id"]
                exclude_keys = {"id", "cr_date", "edit_date","del_date","controller_id","sds_group","computeId","priority", "protocol_id", "host_id", "port_id", "port_name", "host_name", "protocol_name", "pool_name", "disk_type", "volume_name", "volume_type","lun"}

                key_map = {
                    "createdDate": "cr_date",
                    "poolId" : "multi_device_id",
                    "dedup": "deduplication",

                    }
                update_data = normalize_and_merge(existing_row, volume, key_map)
                result = update_if_changed(
                        c,
                        table="volume",
                        new_data=update_data,
                        existing_data=existing_row,
                        where_keys=where_keys,
                        exclude=exclude_keys
                    )

                if result == -2:
                    # sprint("Volume Data already up-to-date",0)
                    pass
                    #conn.rollback()
                elif result == -1:
                    sprint("Failed to update volume", v_name)
                    conn.rollback()
                else:
                    sprint("Volume updated successfully",v_name)
                #compare_and_update_table_data(c,"volume",volume,SDS_Cont_id,volume_data[0])
                    insert_update_vol_export_sds(c,volume,mapping_row["id"],SDS_Cont_id,isCreate=False)

                conn.commit()
        
        if len(data_not_inserted) > 0:
            for item in data_not_inserted:
                sprint(f"Failed to insert volume {item}")

        # Delete Volume Data if data not exist in Storage Node Server
        
        try:
            # Collect volume names from incoming data
            source_volume_names = [item["name"] for item in SN_vol_info]

            # Fetch existing volumes for this controller
            c.execute("SELECT id, name FROM volume WHERE controller_id = ?", [SDS_Cont_id])
            existing_volumes = c.fetchall()

            for vol_id, vol_name in existing_volumes:
                if vol_name not in source_volume_names:
                    # Delete export rows first
                    c.execute("DELETE FROM export WHERE vol_id = ?", [vol_id])
                    # Delete the volume itself
                    c.execute("DELETE FROM volume WHERE id = ?", [vol_id])
                    sprint(f"{vol_name} is deleted from volume table")

            conn.commit()
        except Exception as cleanup_err:
            message = f"Exception during cleanup in volume table : {str(cleanup_err)}"
            sprint(message)

        if db_open:
            c.close()
            conn.close()
            db_open = False
        res = 1
        return res
    except Exception as e:
        message = f"Exception in volume table : {str(e)}"
        sprint(message)
        if db_open:
            c.close()
            conn.close()
            db_open = False
        return res

def checkDB():
    try:
        #if not os.path.exists(DB_PATH):
        #    sprint(f"\n {DB_PATH} is absent \n")
        #else:
        #    sprint(f"\n {DB_PATH} is present \n")
        checkDb(DB_PATH, "db_details.json")
        os.chmod(DB_PATH, 0o777)
        with open("/tmp/db_ready.flag", "w") as f:
            f.write("ready")
    except Exception as e:
        sprint(f"Exception in creating db : {str(e)}")


def fetch_SN_elements(node_ip, element):
    """Fetch data for a specific storage node element directly (no HTTP)."""
    if element in ["controller", "system", "ethPorts", "disks"]:
        return read_SN_system_controller(node_ip, element)
    elif element == "pool":
        return read_SN_Pools(node_ip)
    elif element == "host":
        return read_SN_Hosts(node_ip)
    elif element == "volume":
        return read_SN_Volumes(node_ip)
    else:
        return {"error": f"Unknown element {element}"}

def update_storage_node_status(node_ip, status):
    conn = None
    c = None
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        c.execute("SELECT active FROM storage_node WHERE ip = ?", (node_ip,))
        row = c.fetchone()

        if not row:
            return {"status": "fail", "description": "Storage node not found"}

        old_status = row[0]

        if old_status != status:
            c.execute("UPDATE storage_node SET active=? WHERE ip=?", (status, node_ip))
            conn.commit()

            sprint(f"Storage node {node_ip} is {'Up' if status == 'yes' else 'Down'}")

        return {
            "status": "success",
            "description": "Storage node IP status updated"
        }

    except Exception as e:
        return {
            "status": "fail",
            "description": f"Exception in update_storage_node_status {str(e)}"
        }

    finally:
        if c: c.close()
        if conn: conn.close()


def check_node_ip_status(node_ip):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        c.execute("SELECT * FROM storage_node WHERE ip = ? AND active = 'yes'",[node_ip])

        data = c.fetchone()

        return data is not None

    except Exception as e:
        sprint("Error in check_node_ip_status:", str(e))
        return False

    finally:
        if conn:
            conn.close()

def check_compute_ip_status(node_ip):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        c.execute("SELECT * FROM compute_node WHERE compute_node_ip = ? AND active = 'yes'",[node_ip])

        data = c.fetchone()

        return data is not None

    except Exception as e:
        sprint("Error in check_node_ip_status:", str(e))
        return False

    finally:
        if conn:
            conn.close()



# ==============================
# Flask Routes start from here #
# ==============================


@app.route("/",methods=["GET"])
def index():
    return jsonify({"message" : "SDS Api Working"})


@app.route("/getTheSDSPoolNameByControllerId", methods=["POST"])
def getTheSDSPoolNameByControllerId():
    data = request.get_json()
    controller_id = data.get("controller_id")
    response = getTheSDSPoolName(controller_id)
    return response


@app.route("/getControllerIdByPoolId", methods=["POST"])
def getControllerIdByPoolId():
    data = request.get_json()
    poolId = data.get("poolId")
    controller_id = get_controller_id_by_pool_id(poolId)
    return {"controller_id" : controller_id }

@app.route("/getSDSHostGroup", methods=["POST"])
def getSDSHostGroup():
    data = request.get_json()
    hostId = data.get("hostId")
    controller_ids = get_controller_id_by_host_group(hostId)
    return {"controller_ids" : controller_ids }

@app.route("/getStorageIpByController", methods=["POST"])
def getStorageIpByController():
    data = request.get_json()
    controller_id = data.get("controller_id")
    ip = get_storage_ip_by_controller(controller_id)
    return {"ip" : ip }

@app.route("/getSystemIdByController", methods=["POST"])
def getSystemIdByController():
    data = request.get_json()
    controller_id = data.get("controller_id")
    system_id = get_system_id_by_controller(controller_id)
    return {"system_id" : system_id }


@app.route("/getVolumeIdByName", methods=["POST"])
def getVolumeIdByName():
    data = request.get_json()
    name = data.get("name")
    id = get_volume_id_by_name(name)
    return {"id" : id }


@app.route("/getHostIdByName", methods=["POST"])
def getHostIdByName():
    data = request.get_json()
    name = data.get("name")
    id = get_host_id_by_name(name)
    return {"id" : id }


@app.route("/getIdBySdsMapping", methods=["POST"])
def getIdBySdsMapping():
    data = request.get_json()
    table = data.get("table")
    controller_id = data.get("controller_id")
    remote_id = data.get("remote_id")
    id = get_id_by_remote_id(table,controller_id,remote_id)
    return {"id" : id }


@app.route("/getRemoteIdFromSDSTable", methods=["POST"])
def getRemoteIdFromSDSTable():
    data = request.get_json()
    table_name = data.get("table_name")
    local_id = data.get("local_id")
    id = get_remote_id_by_local_id(table_name,local_id)
    return {"id" : id }

@app.route("/getStoragePoolsData", methods=["POST"])
def getStoragePoolsData():
    # data = request.get_json()
    # query = data.get("query")
    response = get_storage_pools_data()
    return response


@app.route("/getPoolsReamining", methods=["POST"])
def getPoolsReamining():
    data = request.get_json()
    poolSize = data.get("poolSize")
    poolID = data.get("poolID")
    controller_id = data.get("controller_id")

    conn = sqlite3.connect(DB_PATH,check_same_thread=False)
    conn.text_factory = str
    c=conn.cursor()
    used = 0
    remaining =0   
    try:
        c=conn.cursor()
        dbquery=c.execute("select sum(size) from volume where multi_device_id=? and controller_id = ?",[poolID, controller_id])
        resp=c.fetchone()[0]
        if (isinstance(resp, int))==True:
            used=int(resp)
        c.close
        conn.close()

        remaining=int(poolSize)-int(used)
    except Exception as e:
        c.close()
        conn.close()
    return {"used" : used,"remaining" : remaining}


@app.route("/getVolPools", methods=["POST"])
def getVolPools():
    conn = sqlite3.connect(DB_PATH,check_same_thread=False)
    conn.text_factory = str
    c=conn.cursor()
    try:
        c=conn.cursor()
        dbquery=c.execute("SELECT id,name,level,pool_storage,state,compression,acceleration,deduplication,system_name,ifnull(pool_storage,0),sds_controller_id from multi_device where name != 'system'")
        row = c.fetchall()
        return row
    except Exception as e:
        c.close()
        conn.close()
        return []

@app.route("/getNodesDetails", methods=["POST"])
def getNodesDetails():
    nodes = get_nodes_details()
    return nodes

@app.route("/getStorageNodesDetails", methods=["POST"])
def getHostNodesDetails():
    nodes = get_storage_nodes_details()
    return nodes

@app.route("/readSdsPools", methods=["POST"])
def readSdsPools():
    data = request.get_json()
    controller_id = data.get("controller_id")
    PoolType = data.get("PoolType")
    response = read_sds_pool(controller_id,PoolType)
    return response


@app.route("/ReadComputeHost", methods=["POST"])
def ReadComputeHost():
    data = request.get_json()
    computeGroupId = data.get("computeGroupId")
    response = read_sds_compute_host(computeGroupId)
    return response

@app.route("/ReadVolumeHost", methods=["POST"])
def ReadVolumeHost():
    data = request.get_json()
    grouped_hosts = {}
    try:
        # Sqlite3 Connection
        conn=sqlite3.connect(DB_PATH)
        conn.text_factory=str
        c=conn.cursor()
        db_open = True

        c.execute("select h.id, h.name, c.name as controller_name,et.ip from host h left join controller c on c.id = h.controller_id left join eth_ports et on et.controller_id = c.id where et.name = 'LAN1' and h.controller_id <> ''")
        data = c.fetchall()
        for col in data:
            ip = col[3]
            if ip not in grouped_hosts:
                grouped_hosts[ip] = []
            grouped_hosts[ip].append({
                "id" : col[0],
                "name" : col[1],
                "controller_name" : col[2],
                "ip" : ip,
            })
        if db_open:
            c.close()
            conn.close()
            db_open = False
        return grouped_hosts
    except Exception as e:
        if db_open:
            c.close()
            conn.close()
        return grouped_hosts

@app.route("/ReadVolumeHostById", methods=["POST"])
def ReadVolumeHostById():
    try:
        data = request.get_json()
        volumeId = data.get("volumeId")
        node_ip = data.get("node_ip")
        controller_id = getControllerIdByStorageIp(node_ip)
        volumes = read_SN_Volumes(node_ip)
        volume= [volume for volume in volumes if int(volume["id"]) == int(volumeId)][0]
        hostId = get_id_by_remote_id("host",controller_id,volume["hostId"])
        return {"hostId" : hostId,"hostName" : volume["hostName"]}
    except Exception as e:
        return {"hostId" : ""}

@app.route("/readHostDetails", methods=["POST"])
def readHostDetails():
    try:
        data = request.get_json()
        hostId = data.get("hostId")
        if hostId != str(0):
            query="SELECT h.id,h.name,h.protocol,h.user_name,h.iqn,h.pw,h.wwn,url,p.name,h.host_type,ifnull(h.password_hidden,1),GROUP_CONCAT(hg.controller_id) AS controller_ids,GROUP_CONCAT(chg.compute_node_id) AS compute_node_ids from host  h inner join protocol p on h.protocol = p.id left join sds_host_group hg on hg.host_id = h.id left join compute_host_group chg on chg.host_id = h.id where h.id="+str(hostId)+" GROUP BY h.id order by h.id desc"
        else:
            query = "SELECT h.id,h.name,h.protocol,h.user_name,h.iqn,h.pw,h.wwn,url,p.name,h.host_type,ifnull(h.password_hidden,1),GROUP_CONCAT(hg.controller_id) AS controller_ids,GROUP_CONCAT(chg.compute_node_id) AS compute_node_ids from host h inner join protocol p on h.protocol = p.id left join sds_host_group hg on hg.host_id = h.id left join compute_host_group chg on chg.host_id = h.id where h.host_type in ('SDS Group','Compute Node Group') GROUP BY h.name order by h.id desc"

        response = read_sds_host_details(query)
        return response
    except Exception as e:
        return []

@app.route("/readVolumeBySDSDB", methods=["POST"])
def readVolumeBySDSDB():
    conn=sqlite3.connect(DB_PATH)
    conn.text_factory=str
    c=conn.cursor()
    db_open = True
    try:
        data = request.get_json()
        volumeId = data.get("volumeId")
        if volumeId != str(0):
            query=""" SELECT v.id,v.name,hp.id ,v.multi_device_id,e.host_id,e.lun,e.port_id,v.size,
                    ep.name portName,h.name hostName,hp.name protocolName,md.system_name poolName,v.deduplication,v.compression,v.state,'Native',date(v.cr_date) createdDate,v.cr_date,'Volume',
                    v.backup_device, v.type, v.thin, md.name,v.sds_group,md.sds_controller_id,v.priority,v.computeId,GROUP_CONCAT(cvm.compute_node_id) AS compute_node_ids  
                    from volume v  
                    join export e on e.vol_id=v.id 
                    join eth_ports ep on ep.id = e.port_id
                    join host h on h.id = e.host_id
                    join protocol hp on hp.id = (select  protocol from host where host.id = e.host_id limit 1)
                    join multi_device md on md.id = v.multi_device_id 
                    join compute_volume_mapping cvm on cvm.sds_volume_id = v.id
                    where h.host_type = 'Compute Node Group' and v.id=""" +str(volumeId)+""" GROUP BY v.id"""
        else:
            query=""" SELECT v.id,v.name,hp.id ,v.multi_device_id,e.host_id,e.lun,e.port_id,v.size,
                    ep.name portName,h.name hostName,hp.name protocolName,md.system_name poolName,v.deduplication,v.compression,v.state,'Native',date(v.cr_date) createdDate,v.cr_date,'Volume',
                    v.backup_device , v.type, v.thin, md.name,v.sds_group,md.sds_controller_id,v.priority,v.computeId, GROUP_CONCAT(cvm.compute_node_id) AS compute_node_ids 
                    from volume v
                    join export e on e.vol_id=v.id 
                    join eth_ports ep on ep.id = e.port_id
                    join host h on h.id = e.host_id
                    join protocol hp on hp.id = (select  protocol from host where host.id = e.host_id limit 1)
                    join multi_device md on md.id = v.multi_device_id
                    join compute_volume_mapping cvm on cvm.sds_volume_id = v.id
                    where h.host_type = 'Compute Node Group'
                    GROUP BY v.id 
                    
                    union all
                    
                    SELECT vsn.id,vsn.name,hp.id ,v.multi_device_id,e.host_id,e.lun,e.port_id,v.size,
                    ep.name portName,h.name hostName,hp.name protocolName,md.system_name poolName,v.deduplication,v.compression,vsn.state,'Local',date(v.cr_date) createdDate,vsn.cr_date,'Volume',
                    v.backup_device, v.type, v.thin, md.name ,v.sds_group,md.sds_controller_id,v.priority,v.computeId, GROUP_CONCAT(cvm.compute_node_id) AS compute_node_ids  
                    from volume v 
                    join export e on e.vol_id=v.id 
                    join eth_ports ep on ep.id = e.port_id
                    join host h on h.id = e.host_id
                    join protocol hp on hp.id = (select  protocol from host where host.id = e.host_id limit 1)
                    join multi_device md on md.id = v.multi_device_id
                    join volume_snapshot vsn on vsn.vol_id = v.id
                    join compute_volume_mapping cvm on cvm.sds_volume_id = v.id
                    GROUP BY v.id 
                                            
                    union all
                    
                    SELECT v.id,v.name,0 ,v.multi_device_id,vm.id,'-' lun,0 portid,v.size,
                    '-' portName,vm.name hostName,'-' protocolName,md.system_name poolName,v.deduplication,v.compression,ifnull(v.state,4),'Native',date(v.cr_date) createdDate,v.cr_date,'App',
                    v.backup_device, v.type, v.thin, md.name  ,v.sds_group,md.sds_controller_id,v.priority,v.computeId, GROUP_CONCAT(cvm.compute_node_id) AS compute_node_ids  
                    from volume v 
                    join vm_storage vs on vs.volume_id = v.id
                    join virtualmachine vm on vm.id=vs.vm_id
                    join multi_device md on md.id = v.multi_device_id
                    join compute_volume_mapping cvm on cvm.sds_volume_id = v.id
                    group by v.id
                    order by v.id desc
                    """
        c.execute(query)
        row = c.fetchall()

        c.close()
        conn.close()
        db_open = False
        return jsonify(row)
    except Exception as e:
        sprint(f"Exception in readVolumeBySDSDB: {str(e)}")
        if db_open:
            c.close()
            conn.close()
        return jsonify([])

@app.route("/readHostDetailBySDSDB", methods=["POST"])
def readHostDetailBySDSDB():
    conn=sqlite3.connect(DB_PATH)
    conn.text_factory=str
    c=conn.cursor()
    db_open = True
    try:
        data = request.get_json()
        protocolId = data.get("protocolId")
        query="SELECT id,name,protocol,user_name,iqn,pw,wwn,host_type from host where controller_id IS NULL and host_type in ('SDS Group','Compute Node Group') and protocol="+str(protocolId)
        query1 = c.execute(query)
        row = c.fetchall()

        c.close()
        conn.close()
        db_open = False
        return row
    except Exception as e:
        if db_open:
            c.close()
            conn.close()
        sprint(f"Exception in readHostDetailBySDSDB: {str(e)}")
        return []


@app.route("/readSDSVolumeInfo", methods=["POST"])
def readSDSVolumeInfo():
    gVolOff=4
    gVolOn=6
    gVolStarting=5
    gVolSuspended=7

    IQN="iqn.2018-04.com.quantum:vdisk"

    data = request.get_json()
    volumeId = data.get("volumeId")
    conn=sqlite3.connect(DB_PATH)
    conn.text_factory=str
    c=conn.cursor()
    try:
        dbquery="SELECT name,size,state, backup_device,priority from volume where id="+str(volumeId)
        query = c.execute(dbquery)
        conn.commit()
        for col in c:
            VolumeName = col[0]
            size= col[1]
            state = col[2]
            backup_device = col[3]
            priority = col[4]

        query=c.execute("select host_id from export where vol_id='"+ str(volumeId)+"'")
        hostId= c.fetchone()[0]
        
        query=c.execute("select name,iqn,protocol from host where id='"+ str(hostId)+"'")
        conn.commit()
        for col in c:
            HostName = col[0]
            iqn= col[1]
            protocol = col[2]
            
        if state==gVolOff:
            VolState="OFF"
        elif state==gVolOn:
            VolState="ON"
        elif state==gVolStarting:
            VolState="Volume starting"
        elif state==gVolSuspended:
            VolState="Volume suspended"
        else:
            VolState="UN-DEFINED"

        if int(protocol)==int(iSCSI_Chap):
            TargetName = IQN+str(VolumeName)
            TargetType= "iSCSI_Chap"
        elif int(protocol)==int(iSCSI_NoChap):
            TargetName = IQN+str(VolumeName)
            TargetType= "iSCSI_NoChap"
        elif int(protocol)==int(iSER_Chap):
            TargetName = IQN+str(VolumeName)
            TargetType= "iSER_Chap"
        elif int(protocol)==int(iSER_NoChap):
            TargetName = IQN+str(VolumeName)
            TargetType= "iSER_NoChap"
        elif int(protocol)==int(2):
            TargetName="/mnt/"+VolumeName
            TargetType= "File share"
        else:
            TargetName="/cifs/"+VolumeName
            TargetType= "File share"
            

        gb_size=str(size)+" gb"
        #This function should return data in below format.
                    #{"propertyName":"Free","propertyValue":"150 GB"},
                    #{"propertyName":"Compressed","propertyValue":"1.5X"},
                    #{"propertyName":"Dedup","propertyValue":"2.3X"}, 
        priority_key = {
            "0" : "Low",
            "1" : "Medium",
            "2" : "High"
        }            
        mockdata    = [{"propertyName":"Volume name","propertyValue":VolumeName},
                    {"propertyName":"Volume size","propertyValue":gb_size},
                    {"propertyName":"Volume state","propertyValue":VolState},
                    {"propertyName":"Target type","propertyValue":TargetType},
                    {"propertyName":"Target name","propertyValue":TargetName},
                    {"propertyName":"Host name","propertyValue":HostName},
                    {"propertyName":"Host iqn","propertyValue":iqn},
                    {"propertyName":"Priority","propertyValue":priority_key[priority] if priority in priority_key else "N/A"}
                    ]
        return mockdata
    except Exception as e:
        c.close()
        conn.close()
        return []

@app.route("/getPoolStorageBySDS", methods=["POST"])
def getPoolStorageBySDS():
    dbdata = {}
    conn = sqlite3.connect(DB_PATH)
    conn.text_factory = str
    c = conn.cursor()
    db_open = True
    try:
        AllocatedSDS = 0
        dbquery=c.execute("select sum(calculatedRaw) from multi_device where sds_controller_id IS NOT NULL and sds_controller_id <> ''")
        resp=c.fetchone()[0]
        if (isinstance(resp, int))==True:
            AllocatedSDS=int(resp)
        dbdata = {
            "availableSDSStorage": getAvailableSDSStorage() - AllocatedSDS,
            "availableDisk" : 10
        }
        c.close()
        conn.close()
        db_open = False
        return dbdata
    except Exception as e:
        if db_open:
            c.close()
            conn.close()
            db_open = False
        return dbdata

@app.route("/readAllDetails",methods=["POST"])
def read_all_data():
    try:
        data = request.get_json()
        node_ip = data.get("node_ip")
        element = data.get("element")
        if element in ["controller", "system","ethPorts","disks"]:
            data = read_SN_system_controller(node_ip,element)
        # elif element == "ethPorts":
        #     data = read_SN_eth_ports(node_ip)
        elif element == "pool":
            data = read_SN_Pools(node_ip)
        elif element == "host":
            data = read_SN_Hosts(node_ip)
        elif element == "volume":
            data = read_SN_Volumes(node_ip)

        return jsonify(data)
    except Exception as e:
        return jsonify({"error" : str(e)})

@app.route("/getPoolId",methods=["GET"])
def get_pool_id():
    try:
        data = request.get_json()
        node_ip = data.get("node_ip")
        poolName = data.get("poolName")
        URL = create_url(node_ip)
        pools = (requests.get(URL+f"cgi_Pool_Get.py?requestType=read_pool")).json()
        result = [pool_id for pool_id in pools if pool_id['systemName'] == poolName]
        if(len(result) > 0):
            poolId = result[0]["id"]
            return jsonify({"poolId": poolId})
        else:
            return jsonify({"poolId": 0})
    except Exception as e:
        sprint(f"Exception in get_pool_id: {str(e)}")
        return jsonify({"error" : str(e),"poolId" : 0})

@app.route("/get_SN_HostId",methods=["GET"])
def get_host_id():
    try:
        data = request.get_json()
        node_ip = data.get("node_ip")
        hostname = data.get("hostname")
        protocol = data.get("protocol")
        URL = create_url(node_ip)
        all_host = (requests.get(URL+f"cgi_HostManager.py?requestType=read_Host&hostId=0")).json()
        result = [item for item in all_host if item['name'] == hostname and item["protocol_id"]==int(protocol)]
        if result:
            hostId = result[0]["id"]
            return jsonify({"hostId": hostId})
        else:
            return jsonify({"hostId": 0})
    except Exception as e:
        return jsonify({"error" : str(e),"hostId" : 0})

@app.route("/getEthPortId",methods=["GET"])
def get_eth_port_id():
    try:
        data = request.get_json()
        node_ip = data.get("node_ip")
        portName = data.get("portName")
        URL = create_url(node_ip)
        read_ports = (requests.get(URL+f"cgi_VolumeManager.py?requestType=read_Ethernet_ports")).json()
        result = [port_id for port_id in read_ports if port_id['name'] == portName]
        portId = result[0]["id"]
        return jsonify({"portId": portId})
    except Exception as e:
        return jsonify({"error" : str(e),"portId" : 0})

@app.route('/getAllVolume',methods=["GET"])
def get_all_volume():
    try:
        data = request.get_json()
        node_ip = data.get("node_ip")
        URL = create_url(node_ip)
        volume_result = requests.get(URL+f"cgi_VolumeManager.py?requestType=read_Volume&volumeId=0").json()
        return jsonify(volume_result)
    except Exception as e:
        return jsonify({"error" : str(e)})

@app.route('/getAllHost',methods=["GET"])
def get_all_host():
    try:
        data = request.get_json()
        node_ip = data.get("node_ip")
        URL = create_url(node_ip)
        host_result = requests.get(URL+f"cgi_HostManager.py?requestType=read_Host&hostId=0").json()
        return jsonify(host_result)
    except Exception as e:
        return jsonify({"error" : str(e)})

@app.route('/getAllPool',methods=["GET"])
def get_all_pool():
    try:
        data = request.get_json()
        node_ip = data.get("node_ip")
        URL = create_url(node_ip)
        pools_result = (requests.get(URL+f"cgi_Setup_Pool_Manager.py?RequestType=read_pool&PoolType=Select+Pool")).json()
        return jsonify(pools_result)
    except Exception as e:
        return jsonify({"error" : str(e)})
    

@app.route("/compute-nodes", methods=["POST"])
def saveComputeNode():
    conn=sqlite3.connect(DB_PATH)
    conn.text_factory=str
    c=conn.cursor()
    db_open = True
    try:
        data = request.get_json()
        name = data.get("name")
        address = data.get("address")
        status = data.get("status")
        isExist = c.execute("select active from compute_node where name = ?", [name]).fetchall()
        if len(isExist) == 0:
            c.execute("insert into compute_node (name, compute_node_ip,cr_date,active) values(?,?,datetime(),?)",[name,address,status])
            conn.commit()
            response = {"message" : "compute inserted successfully!"}
        else:
            c.execute("update compute_node set compute_node_ip=?, active=? where name = ?",[address,status,name])
            conn.commit()
            response = {"message" : "Compute node updated"}

        if len(isExist) > 0 and status != isExist[0][0]:
            sprint(f"Compute Node IP {address} is {'UP' if status == 'yes' else 'DOWN'}")

        return jsonify(response)
    except Exception as e:
        if db_open:
            c.close()
            conn.close()
        return jsonify({"error" : f"Exception to insert data into compute node table : {e}"})
    finally:
        if db_open:
            c.close()
            conn.close()
            db_open = False

@app.route("/getComputeNodesDetails", methods=["POST"])
def getComputeNodesDetails():
    conn=sqlite3.connect(DB_PATH)
    conn.text_factory=str
    c=conn.cursor()
    db_open = True
    response = []
    try:

        data = c.execute("select id,name,compute_node_ip,active from compute_node").fetchall()
        for col in data:
            response.append({"id" : col[0], "name" : col[1]+"@"+col[2], "value" : col[2],"active" : col[3]})
        if db_open :
            c.close()
            conn.close()
            db_open = False

        return jsonify(response)
    except Exception as e:
        if db_open:
            c.close()
            conn.close()
        return jsonify(response)

@app.route("/create_SN_Host",methods=["POST"])
def create_sn_host():
    try:
        data = request.get_json()
        node_ip = data.get("node_ip")
        hostType=data.get('hostType')
        hostName=data.get("name")
        protocol=data.get('protocol') or ""
        user=data.get('user') or ""
        password=data.get('password') or ""
        iqn=data.get('iqn') or ""
        wwn	=data.get('wwn') or ""
        url	=data.get('url') or ""
        URL = create_url(node_ip)
        result = requests.get(URL+f"cgi_HostManager.py?requestType=create_Host&hostType={hostType}&hostName={hostName}&protocol={protocol}&user={user}&password={password}&iqn={iqn}&wwn={wwn}&url={url}")
        return jsonify(result.json())

    except Exception as e:
        sprint(f"Exception in create_sn_host: {str(e)}")
        return jsonify({"status" : "fail"  , "description" : f"Exception in save SN host {str(e)}"})

@app.route("/update_SN_Host",methods=["PUT"])
def update_sn_host():
    try:
        data = request.get_json()
        node_ip = data.get("node_ip")
        hostId=data.get('hostId')
        hostType=data.get('hostType')
        hostName=data.get("name")
        protocol=data.get('protocol')
        user=data.get('user') or ""
        password=data.get('password') or ""
        iqn=data.get('iqn') or ""
        wwn	=data.get('wwn') or ""
        url	=data.get('url') or ""
        URL = create_url(node_ip)
        result = requests.get(URL+f"cgi_HostManager.py?requestType=update_Host&hostType={hostType}&hostName={hostName}&protocol={protocol}&user={user}&password={password}&iqn={iqn}&wwn={wwn}&url={url}&hostId={hostId}")
        return jsonify(result.json())
    except Exception as e:
        return jsonify({"status" : "fail" , "description" : f"Exception in update SN host {str(e)}"})

@app.route("/delete_SN_Host",methods=["DELETE"])
def delete_sn_host():
    try:
        data = request.get_json()
        node_ip = data.get("node_ip")
        hostId=data.get('hostId')
        
        URL = create_url(node_ip)
        result = requests.get(URL+f"cgi_HostManager.py?requestType=delete_Host&hostId={hostId}")
        return jsonify(result.json())
    except Exception as e:
        return jsonify({"status" : "fail" , "description" : f"Exception in delete SN host {str(e)}"})

@app.route("/create_SN_CN_HostGroup",methods=["POST"])
def create_sn_cn_host():
    try:
        data = request.get_json()
        hostType=data.get('hostType')
        hostName=data.get("name")
        protocol=data.get('protocol') or ""
        iqn=data.get('iqn') or ""
        user=data.get('user') or ""
        password=data.get('password') or ""
        wwn=data.get('wwn') or ""
        url=data.get('url') or ""

        if user == "None":
            user = ""
        if password == "None":
            password = ""
        if wwn == "None":
            wwn = ""
        if url == "None":
            url = ""

        conn = sqlite3.connect(DB_PATH)
        conn.text_factory = str
        c = conn.cursor()
        db_open = True

        c.execute("select name from host where name = ? and host_type in('SDS Group','Compute Node Group')",[hostName])
        row = c.fetchone()
        if row:
            return {"status" : "fail", "description" : "Host Group name already exist"}

        query_SP=c.execute("insert into host(name,host_type,protocol,iqn,user_name,pw,wwn,url,cr_date) values(?,?,?,?,?,?,?,?,datetime())",[hostName,hostType,protocol,"",user,password,wwn,url])
        conn.commit()
        inserted_host_id = c.lastrowid

        for controller_id in ast.literal_eval(iqn):
            if hostType == "SDS Group":
                c.execute("insert into sds_host_group (host_id,controller_id,cr_date) values(?,?,datetime())",[inserted_host_id,controller_id])
                conn.commit()
            elif hostType == "Compute Node Group":
                c.execute("insert into compute_host_group (host_id,compute_node_id,cr_date) values(?,?,datetime())",[inserted_host_id,controller_id])
                conn.commit()
        if db_open :
            c.close()
            conn.close()
            db_open = False

        return {"status" : "success", "description" : "Host Created successfully"}
    except Exception as e:
        sprint(f"Exception in create_sn_cn_host: {str(e)}")
        return jsonify({"status" : "fail"  , "description" : f"Exception in save host {str(e)}"})

@app.route("/update_SN_CN_HostGroup", methods=["PUT"])
def update_sn_cn_host():
    try:
        data = request.get_json()
        hostId = data.get('hostId')
        hostType = data.get('hostType')
        hostName = data.get("name")
        protocol = data.get('protocol') or ""
        user = data.get('user') or ""
        password = data.get('password') or ""
        iqn = data.get('iqn') or ""
        wwn = data.get('wwn') or ""
        url = data.get('url') or ""

        if user == "None":
            user = ""
        if password == "None":
            password = ""
        if wwn == "None":
            wwn = ""
        if url == "None":
            url = ""

        conn = sqlite3.connect(DB_PATH)
        conn.text_factory = str
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        db_open = True


        c.execute("select id from host where name = ? and host_type in ('SDS Group','Compute Node Group')", [hostName])
        row = c.fetchone()

        if row and row["id"] != int(hostId):
            return {"status": "fail", "description": "Host Group name already exists"}

        c.execute("SELECT host_type FROM host WHERE id = ?", [hostId])
        existing_host = c.fetchone()
        existing_host_type = existing_host["host_type"] if existing_host else None

        # Update host table
        c.execute("""
            UPDATE host 
            SET name = ?, host_type = ?, protocol = ?, iqn = ?, user_name = ?, pw = ?, wwn = ?, url = ?
            WHERE id = ?
        """, [hostName, hostType, protocol, iqn, user, password, wwn, url, hostId])
        conn.commit()

        # If host_type is updated:
        if existing_host_type and existing_host_type != hostType:
            # Remove old mappings
            if existing_host_type == "SDS Group":
                c.execute("DELETE FROM sds_host_group WHERE host_id = ?", [hostId])
            elif existing_host_type == "Compute Node Group":
                c.execute("DELETE FROM compute_host_group WHERE host_id = ?", [hostId])
            conn.commit()

        # Insert the new mapping in SDS and Compute group
        if iqn:
            try:
                iqn_list = ast.literal_eval(iqn)
            except:
                return {"status": "fail", "description": "Invalid IQN list format"}

            # Always remove existing mapping before inserting new
            if hostType == "SDS Group":
                c.execute("DELETE FROM sds_host_group WHERE host_id = ?", [hostId])
            else:
                c.execute("DELETE FROM compute_host_group WHERE host_id = ?", [hostId])
            conn.commit()

            for controller_id in iqn_list:
                if hostType == "SDS Group":
                    c.execute("INSERT INTO sds_host_group (host_id, controller_id, cr_date) VALUES (?, ?, datetime())",
                              [hostId, controller_id])
                elif hostType == "Compute Node Group":
                    c.execute("INSERT INTO compute_host_group (host_id, compute_node_id, cr_date) VALUES (?, ?, datetime())",
                              [hostId, controller_id])
                conn.commit()


        return {"status": "success", "description": "Host Updated successfully"}

    except Exception as e:
        sprint(f"Exception in update_sn_cn_host: {str(e)}")
        return jsonify({"status": "fail", "description": f"Exception in update host group {str(e)}"})
    finally:
        if db_open:
            c.close()
            conn.close()
            db_open = False

    
@app.route('/delete_SN_CN_HostGroup',methods=["DELETE"])
def delete_sn_cn_host():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.text_factory = str
        c = conn.cursor()
        db_open = True

        data = request.get_json()
        hostId = data.get("hostId")

        c.execute("select host_type from host where id = ?",[hostId])
        host_data = c.fetchone()
        host_type = host_data[0] if host_data else None
        if not host_data:
            return {"status" : "fail"  , "description" : "Host does not exist"}

        if host_type == "SDS Group":
            c.execute("select controller_id from sds_host_group where host_id = ?",[hostId])
            host_group_data = c.fetchall()
            if host_group_data:
                controller_ids_list = [str(row[0]) for row in host_group_data]  # ensure strings
                controller_ids = ",".join(controller_ids_list)
                if len(controller_ids_list) > 0:
                    c.execute(f"""
                        SELECT count(DISTINCT v.id) 
                        from volume v  
                        join export e on e.vol_id=v.id 
                        join eth_ports ep on ep.id = e.port_id
                        join host h on h.id = e.host_id
                        join protocol hp on hp.id = (select  protocol from host where host.id = e.host_id limit 1)
                        join multi_device md on md.id = v.multi_device_id 
                        join compute_volume_mapping cvm on cvm.sds_volume_id = v.id
                        where h.host_type = 'SDS Group' and v.controller_id in ({controller_ids}) group by v.id;
                    """)
                    count = c.fetchone()
                    if count and count[0] > 0:
                        return {"status" : "fail"  , "description" : "SDS Group host has dependent volumes"}

                    c.execute("delete from sds_host_group where host_id = ?",[hostId])
                    conn.commit()
        if host_type == "Compute Node Group":
            c.execute("select count(*) from volume where computeId = ?", [hostId])
            volume_count = c.fetchone()

            if volume_count and volume_count[0] > 0:
                return {"status" : "fail"  , "description" : "Compute Node Group host has dependent volumes"}
            
            c.execute("delete from compute_host_group where host_id = ?",[hostId])
            conn.commit()

        query = "Delete from Host where id in ("+str(hostId)+")"
        query_FT=c.execute(query)
        conn.commit()
        
        c.close()
        conn.close()
        db_open = False

        return jsonify({"status" : "success", "description" : "Host Deleted Successfully"})
    except Exception as e:
        if db_open:
            c.close()
            conn.close()
        return jsonify({"status" : "fail" , "description" : f"Exception in delete host {str(e)}"})

@app.route("/sn_pool",methods=["POST"])
def create_sn_pool():
    try:
        data = request.get_json()
        node_ip = data.get("node_ip")
        PoolName = data.get("PoolName")
        PoolLevel = data.get("PoolLevel")
        Compression = data.get("Compression")
        Deduplication = data.get("Deduplication")
        systemName = data.get("systemName")
        AccelerationPercent = data.get("AccelerationPercent")
        Percentage = data.get("Percentage")
        AvailableStorage = data.get("AvailableStorage")
        availableSSD = data.get("availableSSD")
        URL = create_url(node_ip)
        result = requests.get(URL+f"cgi_Setup_Pool_Manager.py?RequestType=create_pool&PoolName={PoolName}&PoolLevel={PoolLevel}&Compression={Compression}&Deduplication={Deduplication}&systemName={systemName}&Percentage={Percentage}&AccelerationPercent={AccelerationPercent}&availableSSD={availableSSD}&AvailableStorage={AvailableStorage}")

        # if result["status"] == "success":
        #     save_pools_into_sds_db(data)
        return result.json()
    except Exception as e:
        return jsonify({"status" : "fail", "description" : f"Exception in save pool : {str(e)}"})


@app.route("/sn_pool",methods=["PUT"])
def update_sn_pool():
    try:
        data = request.get_json()
        node_ip = data.get("node_ip")
        PoolName = data.get("PoolName")
        Compression = data.get("Compression")
        Deduplication = data.get("Deduplication")
        systemName = data.get("systemName")
        AccelerationPercent = data.get("AccelerationPercent")
        URL = create_url(node_ip)
        result = requests.get(URL+f"cgi_Setup_Pool_Manager.py?RequestType=update_pool&PoolName={PoolName}&Compression={Compression}&Deduplication={Deduplication}&systemName={systemName}&AccelerationPercent={AccelerationPercent}").json()

        # if 'success' in result["status"]:
        #     update_pool_from_sds_db(data)
        return result
    except Exception as e:
        return jsonify({"status" : "fail", "description" : f"Exception in update pool : {str(e)}"})

@app.route("/sn_pool",methods=["DELETE"])
def delete_sn_pool():
    try:
        data = request.get_json()
        name = data.get("name")
        PoolType = data.get("PoolType")
        node_ip = data.get("node_ip")
        URL = create_url(node_ip)
        result = requests.get(URL+f"cgi_Setup_Pool_Manager.py?RequestType=delete_pool&PoolName={name}&PoolType={PoolType}").json()
        # if 'success' in result["status"]:
        #     delete_pool_from_sds_db(data)
        return result
    except Exception as e:
        return jsonify({"status" : "fail", "description" : f"Exception in delete pool : {str(e)}"})


@app.route('/sn_volume',methods=["POST"])
def create_sn_sds_volume():
    steps_info = {
        "status" : True
    }
    try:
        data = request.get_json()
        volumeName=data.get("volumeName")
        size=data.get('size') 
        poolId=data.get('poolId')
        protocolId = data.get('protocolId')
        # hostId=data.get('hostId')
        dedup=data.get('dedup',"false") 
        compression=data.get('compression',"false")
        backup_device=data.get('backup_device',"false")
        thin=data.get('thin')
        computeId=data.get('computeId')

        pools_info = [] # containing details of pools information

        is_protocol_support = check_protocol_support(protocolId)

        if not is_protocol_support:
            return {"steps_info" : {"status" : False, "volume" : {"message" : "Protocol Not Supported", "status" : False}}}
            

        storage_node_ip = get_storage_ip_by_controller(1)

        if storage_node_ip:
            pools_read = get_SN_PoolsStorage(storage_node_ip)
            # check size is less then pools size
            result = [item for item in pools_read if int(item["remaining"]) >= int(size)]
            if result:
                result = result[0]
                if 'controller_id' in result and result["controller_id"] and int(result["controller_id"]) > 0 :
                    pass
                else:
                    pools_info.append({"pool": result})

        if len(pools_info) == 0:
            return {"steps_info" : {"status" : False, "volume" : {"message" : "Pool Not Found with given size", "status" : False}}}
        
        max_pool_info = random.choice(pools_info)
        # max_pool_info = max(pools_info, key=lambda x: x["pool"]["remaining"])
        node_ip = storage_node_ip
        poolId = max_pool_info["pool"]["id"]
        poolName = max_pool_info["pool"]["systemName"]

        sprint("\nSelect Node Details\n")
        sprint(f"Node IP : {storage_node_ip}")
        sprint(f"Pool Name : {max_pool_info['pool']['systemName']}")
        sprint(f"Pool Size : {max_pool_info['pool']['remaining']}")

        steps_info["pool"] = max_pool_info

        try:
            user = ""
            password = ""
            parts = storage_node_ip.split(".")
            iqn = f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
            if int(protocolId) == 1:
                user = "admin"
                password = "Naveen@123"
            elif int(protocolId) == 3:
                user = "admin"
                password = "Naveen@123"
            
            sds_host = read_sds_host_details("SELECT * from host where id = "+str(computeId))
            if sds_host and len(sds_host) > 0:
                user = sds_host[0][6]
                password = sds_host[0][9]
            
            # Check Host or Create New
            all_Node_Hosts = read_SN_Hosts(node_ip)
            if all_Node_Hosts and len(all_Node_Hosts) > 0:
                if int(protocolId) in [2,4]:
                    hosts = [item for item in all_Node_Hosts if (item["protocol_id"] == int(protocolId) and item["iqn"] == iqn and item["host_type"] == "Single Host") ]
                elif int(protocolId) in [1,3]:
                    hosts = [item for item in all_Node_Hosts if (item["protocol_id"] == int(protocolId) and item["user_name"] == user and item["pw"] == password and item["host_type"] == "Single Host")]

                if len(hosts) > 0:
                    host_name = random.choice(hosts)["name"]
                else:
                    host_name = "host" + str(len(all_Node_Hosts)+1)
            else:
                host_name = "host1"
                
            # Check LUN From volumes
            all_Node_Volumes = read_SN_Volumes(node_ip)
            if all_Node_Volumes and len(all_Node_Volumes) > 0:
                used_luns = [item["lun"] for item in all_Node_Volumes]
            else:
                used_luns = []

            max_lun_range = 128
            lun = 1

            for i in range(1,max_lun_range):
                if i not in used_luns:
                    lun = i
                    break
            
            # Port Id from Node
            all_Node_Ports = read_SN_volume_eth_ports(node_ip)
            if all_Node_Ports and len(all_Node_Ports) > 0:
                portId = random.choice(all_Node_Ports)["id"]
            else:
                return jsonify({"status" : "failure", "description" : "No ports found"})

            data["host_name"] = host_name
            data["portId"] = portId
            data["lun"] = lun

  
            host_result = requests.post(f"http://127.0.0.1:{PORT}/create_SN_Host", json={"node_ip" : node_ip,"name" : host_name, "hostType" : "Single Host", "protocol" : protocolId, "iqn" : iqn, "user" : user, "password" : password})
            host_result = host_result.json()
            if host_result["status"] == "success" or host_result["description"] == "Host Name Already Exists":
                host_read = requests.get(f"http://127.0.0.1:{PORT}/get_SN_HostId", json={"node_ip" : node_ip,"hostname" : host_name, "protocol" : protocolId})
                host_read = host_read.json()
                hostId=host_read['hostId']
                steps_info["host"] = {
                    "status" : True
                }
            else:
                steps_info["status"] = False
                steps_info["host"] = {
                    "status" : False,
                    "message" : host_result
                }
                return jsonify({"steps_info" : steps_info})
        except Exception as e:
            sprint("Error in Create Volume on Storage Node",e)
            steps_info["status"] = False
            steps_info["host"] = {
                "status" : False,
                "message" : str(e)
            }
            return steps_info
            
        URL = create_url(node_ip)
        result = requests.get(URL+f"cgi_VolumeManager.py?requestType=create_Volume&volumeName={volumeName}&size={size}&poolName={poolName}&hostId={hostId}&dedup={dedup}&compression={compression}&backup_device={backup_device}&thin={thin}&protocolId={protocolId}&lun={lun}&portId={portId}").json()
        if 'status' in result and result['status'] == "fail":
            steps_info["status"] = False
            steps_info["volume"] = {
                "status" : False,
                "message" : result
            }
        else:
            steps_info["volume"] = {
                "status" : True,
                "message" : result
            }
            controller_id = getControllerIdByStorageIp(node_ip)
            poolId = get_id_by_remote_id("multi_device", controller_id, poolId)
            DB_Create_SN_VolumeDB(data,poolId,node_ip, controller_id)

        return {"steps_info" : steps_info , "pool_info" : max_pool_info}
    except Exception as e:
        sprint(f"Exception in save volume : {str(e)}")
        steps_info["status"] = False
        steps_info["volume"] = {
            "status" : False,
            "message" : str(e)
        }
        return jsonify({"message" : f"Exception in save volume : {str(e)}", "steps_info" : steps_info})


@app.route('/sn_volume',methods=["PUT"])
def update_sn_sds_volume():
    try:
        data = request.get_json()
        volumeName=data.get("volumeName")
        size=data.get('size') 
        poolId=data.get('poolId')
        protocolId = data.get('protocolId')
        hostId=data.get('hostId')
        dedup=data.get('dedup') 
        compression=data.get('compression')
        backup_device=data.get('backup_device')
        thin=data.get('thin')
        lun=data.get('lun') 
        portId=data.get('portId')
        volumeId=data.get('volumeId')
        
        node_ip = ""
        remote_pool_id = ""
        remote_host_id = ""
        remote_vol_id = ""

        node_ip = get_storage_ip_by_controller(1)
        remote_pool_id = get_remote_id_by_local_id('multi_device',poolId)
        remote_host_id = get_remote_id_by_local_id('host',hostId)
        remote_vol_id = get_remote_id_by_local_id('volume',volumeId)
        
        URL = create_url(node_ip)
        result = requests.get(URL+f"cgi_VolumeManager.py?requestType=update_Volume&volumeName={volumeName}&size={size}&poolId={remote_pool_id}&hostId={remote_host_id}&dedup={dedup}&compression={compression}&backup_device={backup_device}&thin={thin}&protocolId={protocolId}&lun={lun}&portId={portId}&volumeId={remote_vol_id}")
        return result.json()
    except Exception as e:
        return jsonify({"status" : "fail", "description" : f"Exception in save volume : {str(e)}"})


@app.route('/onOff_SN_Volume',methods=["PUT"])
def onOff_sn_sds_volume():
    steps_info = {
        "status" : True
    }
    try:
        data = request.get_json()
        # node_ip = data.get("node_ip")
        volumeState=data.get('state') 
        volumeId = data.get('volumeId')
        # remote_vol_id = data.get('remote_vol_id')
        controller_id = data.get('controller_id')
        volumeType = data.get('volumeType')

        node_ip = get_storage_ip_by_controller(1)
        remote_vol_id = get_remote_id_by_local_id('volume',volumeId)

        URL = create_url(node_ip)
        onOff_volume = requests.get(URL+f"cgi_VolumeManager.py?requestType=onOff_Volume&volumeId={remote_vol_id}&volumeType={volumeType}&state={volumeState}").json()
        if 'status' in onOff_volume and onOff_volume["status"] == "fail":
            steps_info["status"] = False
            steps_info["volume_on"] = {
                "status" : False,
                "message" : onOff_volume["description"]
            }
        else:
            steps_info["volume_on"] = {
                "status" : True,
            }
    
            volumes = read_SN_Volumes(node_ip)
            volume= [volume for volume in volumes if volume["id"] == int(remote_vol_id)][0]

            # Protocol Details
            hostId = volume["hostId"]

            controller_id = getControllerIdByStorageIp(node_ip)

            try:
                host_id = get_id_by_remote_id("host",controller_id,hostId)
                if host_id == 0:
                    steps_info["status"] = False
                    steps_info["volume_on"] = {
                        "status" : False,
                        "message" : "Host not found"
                    }
                    return steps_info

                host = getSDSHostDetailsById(host_id)

                host_name = host[1]
                user_name = host[3]
                iqn = host[4]
                pw = host[5]
                wwn = host[6]
                url = host[7]
                protocol_name = host[8]

            except Exception as e:
                sprint(f"exception in host read {e}")
                steps_info["status"] = False


            controller_id = get_controller_id_by_volume_id(volumeId)
            steps_info["compute"] = []
            if int(volumeState) == 6:           
                try:
                    compute_node_ips = get_compute_node_ip(volumeId,volume["name"], node_ip, controller_id)
                    isNew = False
                    if not compute_node_ips:
                        compute_node_ips = read_SN_ComputeNodes(volumeId)
                        isNew = True
                    thrds = []
                    for compute_node_ip in compute_node_ips:
                        thrd = threading.Thread(
                            target=mount_volumes,
                            args=(compute_node_ip, volume, protocol_name, node_ip, host_name, user_name, iqn, pw, wwn, url, steps_info,isNew,volumeId,controller_id,volume["name"],node_ip),
                        )
                        thrd.start()
                        thrds.append(thrd)
                    

                    for thrd in thrds:
                        thrd.join()

                except Exception as e:
                    steps_info["status"] = False
                    steps_info["compute"].append({"mount" : {"status" : False, "message" : str(e)}})
            elif int(volumeState) == 4:          
                try:
                    compute_node_ips = get_compute_node_ip(volumeId,volume["name"], node_ip, controller_id)
                    if compute_node_ips:
                        thrds = []
                        for compute_node_ip in compute_node_ips:
                            thrd = threading.Thread(
                                target=unmount_volumes,
                                args=(compute_node_ip, volume, node_ip, protocol_name, user_name, pw, iqn, steps_info),
                            )
                            thrd.start()
                            thrds.append(thrd)
                        

                        for thrd in thrds:
                            thrd.join()

                    else:
                        sprint(f"No Compute found for volume name : {volume['name']}, and Remote Node IP : {node_ip}")
                        steps_info["status"] = False
                        steps_info["compute"].append({"mount" : {"status" : False, "message" : f"No Compute found for volume name : {volume['name']}, and Remote Node IP : {node_ip}"}})

                except Exception as e:
                    steps_info["status"] = False
                    steps_info["compute"].append({"mount" : {"status" : False, "message" : str(e)}})
            else:
                steps_info["status"] = False
                steps_info["compute"].append({"mount" : {"status" : False, "message" : "Invalid volume state"}})
            onOff_volume_into_sdsDB(data)

        return steps_info
    except Exception as e:
        print("Exception in onOff_sn_sds_volume",str(e))
        steps_info["status"] = False
        steps_info["volume_on"] = {
            "status" : False,
            "message" : str(e)
        }
        return steps_info

@app.route('/sn_volume',methods=["DELETE"])
def delete_sn_sds_volume():
    try:
        data = request.get_json()
        volumeId = data.get("volumeId")
        controller_id = data.get("controller_id")
        volumeType = data.get("volumeType")

        node_ip = get_storage_ip_by_controller(1)
        remote_vol_id = get_remote_id_by_local_id('volume',volumeId)
        
        URL = create_url(node_ip)
        volumes = read_SN_Volumes(node_ip)
        matching= [volume for volume in volumes if volume["id"] == int(remote_vol_id)]
        if not matching:
            return {"status": "fail", "description": "Volume not found on storage node"}

        volume = matching[0]
        
        result = requests.get(URL+f"cgi_VolumeManager.py?requestType=delete_Volume&volumeId={remote_vol_id}&volumeType={volumeType}&controller_id=0").json()
        if result["status"] == "fail":
            return result
        else:
            controller_id = get_controller_id_by_volume_id(volumeId)
            compute_node_ips = get_compute_node_ip(volumeId,volume["name"], node_ip, controller_id)

            delete_volume_from_storage_compute_vol(volumeId)

            hostId = volume["hostId"]

            try:
                host_id = get_id_by_remote_id("host",controller_id,hostId)
                if host_id == 0:
                    return {"status": "fail", "description": "Host not found"}

                host = getSDSHostDetailsById(host_id)

                host_name = host[1]
                user_name = host[3]
                iqn = host[4]
                pw = host[5]
                wwn = host[6]
                url = host[7]
                protocol_name = host[8]

            except Exception as e:
                sprint(f"exception in host read {e}")
                return {"status": "fail", "description": "Host not found on storage node"}

            thrds = []
            for compute_node_ip in compute_node_ips:
                thrd = threading.Thread(
                    target=deleteFolderFromComputeNode,
                    args=(compute_node_ip, volume["name"],node_ip,iqn,user_name, pw, protocol_name,result),
                )
                thrd.start()
                thrds.append(thrd)

            for thrd in thrds:
                thrd.join()
            

            delete_volume_from_sdsDB(data)
            
        return result
    except Exception as e:
        return {"status" : "fail", "description" : "Volume not deleted, Error :" + str(e)}


@app.route("/mountVolume", methods=["POST"])
def mount_volume():
    try:
        data = request.get_json()
        volumeName = data.get("volumeName")
        protocol_name = data.get("protocol_name")
        remote_ip = data.get("remote_ip")
        compute_node_ip = data.get("compute_node_ip")
        host_name = data.get("host_name")
        user_name = data.get("user_name")
        ip = data.get("ip")
        password = data.get("password")
        wwn = data.get("wwn")
        url = data.get("url")


        # Send data to client server
        data_to_send = {
            "volumeName": volumeName,
            "protocol_name": protocol_name,
            "remote_ip": remote_ip,
            "host_name" : host_name, 
            "user_name" : user_name, 
            "ip" : ip, 
            "password" : password, 
            "wwn" : wwn, 
            "url" : url
        }
        CLIENT_API_URL = f"http://{compute_node_ip}:{CLIENT_PORT}"
        response = requests.post(CLIENT_API_URL+"/mountVolume",json=data_to_send).json()

        if response and response["status"] == "success":
            return jsonify({"message" : response["error_message"] if response.get("error_message") else "Volume successfully mounted", "status" : True, "mount_path" : response["mount_path"]})
        else:
            return jsonify({"message" : response["error_message"] if response.get("error_message") else "Volume not mounted", "status" : False, "mount_path" : response["mount_path"]})


    except Exception as e:
        sprint(f"Exception in mount volume : {e}")
        return jsonify({"message" : "Volume not mounted", "status" : False, "mount_path" : "N/A"})

@app.route("/unmountVolume", methods=["POST"])
def unmount_volume():
    try:
        data = request.get_json()
        volumeName = data.get("volumeName")
        remote_ip = data.get("remote_ip")
        compute_node_ip = data.get("compute_node_ip")
        protocol_name = data.get("protocol_name")
        iqn = data.get("iqn")
        user_name = data.get("user_name")
        password = data.get("password")

        # Send data to client server
        data_to_send = {
            "volumeName": volumeName,
            "remote_ip": remote_ip,
            "protocol_name": protocol_name,
            "iqn" : iqn,
            "user_name" : user_name, 
            "password" : password

        }
        CLIENT_API_URL = f"http://{compute_node_ip}:{CLIENT_PORT}"
        response = requests.post(CLIENT_API_URL+"/unmountVolume",json=data_to_send).json()

        if response and response["status"] == "success":
            return jsonify({"message" : "Volume successfully unmounted", "status" : True, "unmount_path" : response["unmount_path"]})
        else:
            return jsonify({"message" : "Volume not unmounted", "status" : False, "unmount_path" : response["unmount_path"]})


    except Exception as e:
        sprint(f"Exception in unmount volume : {e}")
        return jsonify({"message" : "Volume not unmounted", "status" : False, "unmount_path" : "N/A"})


@app.route("/storage-nodes/status", methods=["PUT"])
def UpdateStorageNodeStatus():
    try:
        data = request.get_json()
        node_ip = data.get("node_ip")
        status = data.get("status")
        result = update_storage_node_status(node_ip, status)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status" : "fail" , "description" : f"Exception in UpdateStorageNodeStatus {str(e)}"})    

@app.route("/storage-nodes", methods=["POST"])
def CreateStorageNodeData():

    data = request.get_json()
    node_ip = data.get("node_ip")
    sprint(f"Received SNode Request: {node_ip}")

    try:
        elements = ["system","controller","ethPorts","pool","host","disks","volume"]
        results = {}
        SDS_Sys_id=1
        SDS_Cont_id=1
        not_updated = []

        for element in elements:
                                    
            res = fetch_SN_elements(node_ip, element)
            
            if element == "system" and "error" not in res:
                SDS_Sys_id = DB_Create_SN_Get_System(res[0])
                if SDS_Sys_id == -1:
                    not_updated.append("system")

            elif element == "controller" and ("error" not in res and SDS_Sys_id > 0):
                SDS_Cont_id = DB_Create_SN_Get_Controller(res[0],SDS_Sys_id,node_ip)
                if SDS_Cont_id == -1:
                    not_updated.append("controller")

            elif element == "disks" and ("error" not in res and SDS_Cont_id > 0):
                res = DB_Create_SN_Disks(res,SDS_Cont_id)
                if res == -1:
                    not_updated.append("disks")

            elif element == "ethPorts" and ("error" not in res and SDS_Cont_id > 0):
                res = DB_Create_SN_EthPorts(res,SDS_Cont_id)
                if res == -1:
                    not_updated.append("ethPorts")

            elif element == "pool" and ("error" not in res and SDS_Cont_id > 0):
                res = DB_Create_SN_Pool(res,SDS_Cont_id)
                if res == -1:
                    not_updated.append("pool")

            elif element == "host" and ("error" not in res and SDS_Cont_id > 0):
                res = DB_Create_SN_Host(res,SDS_Cont_id)
                if res == -1:
                    not_updated.append("host")       

            elif element == "volume" and ("error" not in res and SDS_Cont_id > 0):
                res = DB_Create_SN_Volume(res,SDS_Cont_id)
                if res == -1:
                    not_updated.append("Volume")

            elif "error" in res:
                not_updated.append(element)
                res = -2  # Indicate error in fetching data   

            results[element] = res
        if not not_updated:
            return jsonify({"message": "All "+node_ip+" data saved successfully into SDS database"}), 200
        else:
            return jsonify({
                "message": "Some elements were not updated",
                "not_updated": not_updated
            })
    except Exception as e:
        sprint(f"Exception in CreateStorageNodeData: {e}")
        return jsonify({"error": str(e)})  # Return error code on failure

@app.route("/getProtocolData", methods=["GET"])
def get_protocol_data():
    db_open = False
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.text_factory = str
        c = conn.cursor()
        db_open = True

        not_in_query = '(' +str(FC)+','+ str(iSER_Chap)+','+ str(iSER_NoChap)+','+ str(NFS_RDMA)+ ')'
        dbquery="SELECT id,name from protocol where id not in " + not_in_query
        query = c.execute(dbquery)
        dbdata = []
        conn.commit()
        for col in c:
            jsonschema = {"id":col[0],"name" : col[1]}
            dbdata.append(jsonschema)
        if db_open:
            c.close()
            conn.close()
            db_open = False
        return jsonify(dbdata)
    except Exception as e:
        if db_open:
            c.close()
            conn.close()
        return jsonify({"error" : f"Exception to read data from protocol table : {e}"})

@app.route("/getHostByProtocol", methods=["GET"])
def get_host_by_protocol():
    data = request.get_json()
    protocolId = data.get("protocolId")
    dbdata = []
    db_open = False
    try:
        conn=sqlite3.connect(DB_PATH)
        conn.text_factory=str
        c=conn.cursor()
        db_open = True

        query="SELECT id,name,protocol,user_name,iqn,pw,wwn,host_type from host where controller_id IS NULL and host_type in ('SDS Group','Compute Node Group') and protocol="+str(protocolId)
        query = c.execute(query)
        row = c.fetchall()
        
        conn.commit()
        for col in row:
            jsonschema = {"id":col[0],"name" : col[1],"protocol_id":col[2],"user_name":col[3],"iqn":col[4],"pw":col[5],"wwn":col[6],"host_type" :col[7]}
            dbdata.append(jsonschema)
        if db_open:
            c.close()
            conn.close()
            db_open = False
        return jsonify(dbdata)
    except Exception as e:
        if db_open:
            c.close()
            conn.close()
            db_open = False
        return jsonify({"error" : f"Exception to read data from host table : {e}"})

@app.route("/getComputeNodeByComputeGroup", methods=["GET"])
def get_compute_by_host():
    data = request.get_json()
    computeGroupId = data.get('computeGroupId')
    response = []
    db_open = False
    try:
        conn=sqlite3.connect(DB_PATH)
        conn.text_factory=str
        c=conn.cursor()
        db_open = True
        data = c.execute("select compute_node_id from compute_host_group where host_id = ?", [computeGroupId]).fetchall()
        if not data:
            return jsonify(response)
        
        compute_node_ids = [row[0] for row in data]
        placeholders = ','.join('?' * len(compute_node_ids))
        compute_data = c.execute(f"SELECT id,name,compute_node_ip FROM compute_node WHERE id IN ({placeholders})", compute_node_ids).fetchall()

        for col in compute_data:
            response.append({"id" : col[0], "name" : col[1]+"@"+col[2], "value" : col[2]})
        if db_open :
            c.close()
            conn.close()
            db_open = False
        return jsonify(response)
    except Exception as e:
        if db_open:
            c.close()
            conn.close()
            db_open = False
        return jsonify({"error" : f"Exception to read data from compute_node table : {e}"})


def cleanup():
    if os.path.exists("/tmp/db_ready.flag"):
        os.remove("/tmp/db_ready.flag")
        sprint("Cleaned up db_ready.flag")

atexit.register(cleanup)


def handle_exit_signal(signum, frame):
    cleanup()
    sys.exit(0)

signal.signal(signal.SIGTERM, handle_exit_signal)
signal.signal(signal.SIGINT, handle_exit_signal)

def sds_manager():
    checkDB()
    app.run(debug=False, port=PORT, host="0.0.0.0")


if __name__ == "__main__":
    sds_manager()
