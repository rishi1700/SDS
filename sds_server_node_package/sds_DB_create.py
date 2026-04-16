#!/usr/bin/python

#import modules

import sqlite3
import json
import os
from sds_globalSettings import DEFAULT_PATH_TO_DB_CONFIG
#function to create tables.
#function for default values

from sds_defaultDB_Data import default_data
DEFAULT_IS_DB_PRESENT = False
DEBUGGING = True

def sprint(*args):
    if DEBUGGING:
        for arg in args:
            print(arg)

def read_db_config(path_to_db_config):
    data = {}
    with open(path_to_db_config) as f:
        data = json.load(f)
    return data

def create_table(dbFileName, path_to_db_config=DEFAULT_PATH_TO_DB_CONFIG, isDBPresent=DEFAULT_IS_DB_PRESENT):
    tables_info = read_db_config(path_to_db_config)
    conn=sqlite3.connect(dbFileName)
    conn.execute('pragma foreign_keys=ON')
    c=conn.cursor()
    sprint("Creating Tables/columns if not exist")
    for table_info in tables_info:
        table_name = table_info["table_name"]
        primary_key_column_query = "(id INTEGER PRIMARY KEY)" # Every table will have id column by default
        for primary_key in table_info["table_primary_key"]:
            primary_key_column_query = "({} {} {})".format(primary_key["column_name"], primary_key["datatype"], primary_key["constraints"])
        create_table_query = """
            CREATE TABLE IF NOT EXISTS {table_name} {primary_key_column}
        """.format(table_name=table_name, primary_key_column=primary_key_column_query)
        c.execute(create_table_query)
        columns = table_info["columns"]
        all_column_names = table_info["all_column_names"]
        existing_columns = []
        c.execute("PRAGMA table_info('{}')".format(table_name)) # Gives cid, name, type, notnull, default_value, primary_key
        for cols in c:
            existing_columns.append(str(cols[1]))
        
        for column in columns:
            column_name = column["column_name"]
            # Adding new columns
            if column_name not in existing_columns:
                #sprint("{} doesn't exits in table {}, so adding the column!".format(column_name, table_name))
                constraints = column["constraints"]
                datatype = column["datatype"]
                add_column_query = "ALTER TABLE {table_name} ADD COLUMN '{column_name}' {datatype} {constraints}".format(table_name=table_name, column_name=column_name, 
                                                                                                                        datatype=datatype, constraints=constraints)
                c.execute(add_column_query)
    
    conn.commit()
    conn.close()
    default_data(dbFileName)
            

def checkDb(dbFileName, version, path_to_db_config=DEFAULT_PATH_TO_DB_CONFIG):
    
    conn = sqlite3.connect(dbFileName)
    conn.text_factory = str
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master where type = 'table'")
    total_tables = cursor.fetchall()
    conn.close()
    
    create_table(dbFileName, path_to_db_config, False)
    
    conn = sqlite3.connect(dbFileName)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master where type = 'table'")
    updated_tables = cursor.fetchall()

    if len(updated_tables) > len(total_tables):
        sprint("new table added: {}".format(list(set(updated_tables) - set(total_tables))))
    else:
        sprint ("no new tables added")
    conn.commit()
    conn.close()


if __name__ == '__main__':
    checkDb("quantumDB.db", "sds_db_details.json")