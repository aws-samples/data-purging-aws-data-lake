#!/usr/bin/env python

"""
Below are the 3rd parties this script includes
1. pg8000
(Github: https://github.com/mfenniak/pg8000,
License: https://github.com/mfenniak/pg8000/blob/master/LICENSE)
Lines no 30 to 35 use pg8000 to connect to RDS Postgres.
Lines no 46 to 39 use pg8000 to insert data to RDS Postgres.
"""

import os
import boto3
import json
import pg8000
import uuid
import botocore
from urllib.parse import unquote_plus

def get_connection():
    try:
        print ("Connecting to database")
        client = boto3.client("rds")
        DBEndPoint = os.environ.get("DBEndPoint")
        DatabaseName = os.environ.get("DatabaseName")
        DBUserName = os.environ.get("DBUserName")
        password = client.generate_db_auth_token(
            DBHostname=DBEndPoint, Port=5432, DBUsername=DBUserName
        )
        conn = pg8000.connect(
            host=DBEndPoint,
            user=DBUserName,
            database=DatabaseName,
            password=password,
            ssl={"sslmode": "verify-full"},
        )
        return conn
    except Exception as e:
        print ("While connecting failed due to :{0}".format(str(e)))
        return None

def insert_user_files(user_list):
    sql = """INSERT INTO user_objects (userid, s3path, recordline)
            VALUES(%s,%s,%s);"""
    try:
        myConnection = get_connection()
        cur = myConnection.cursor()
        cur.executemany(sql, user_list)
        myConnection.commit()
    except Exception as e:
        print ("While connecting failed due to :{0}".format(str(e)))

def lambda_handler(event, context):
    s3 = boto3.client('s3')
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = unquote_plus(event['Records'][0]['s3']['object']['key'])
    tmpkey = key.replace('/', '')
    download_path = '/tmp/{}{}'.format(uuid.uuid4(), tmpkey)
    s3.download_file(bucket, key, download_path)
    tupleList = []
    rowNumber = 0
    with open(download_path, 'r') as file:
        for row in file:
            parsed_row = json.loads(row)
            s3Uri = 's3://' + bucket + '/'  + key
            tupleList.append((parsed_row['user_id'], s3Uri, rowNumber,))
            rowNumber += 1
    insert_user_files(tupleList)
    print('Index updated')
