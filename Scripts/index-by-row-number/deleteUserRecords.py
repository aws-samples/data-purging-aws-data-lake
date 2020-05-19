#!/usr/bin/env python

"""
Below are the 3rd parties this script includes
1. pg8000
(Github: https://github.com/mfenniak/pg8000,
License: https://github.com/mfenniak/pg8000/blob/master/LICENSE)
Lines no 28 to 33 use pg8000 to connect to RDS Postgres.
Lines no 43 to 54 use pg8000 to query to RDS Postgres.
"""

import os
import boto3
import pg8000
import botocore
from botocore.exceptions import NoCredentialsError, ClientError
from urllib.parse import urlparse

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

def get_user_files(userids):
    try:
        myConnection = get_connection()
        cur = myConnection.cursor()
        sql = """
            SELECT s3path,
                ARRAY_AGG(recordline)
                FROM user_objects
                WHERE userid in (%s)
                GROUP BY 1
                ;
            """ % ','.join('%s' for i in userids)
        cur.execute(sql, userids)
        myConnection.commit()
        return cur.fetchall()
    except Exception as e:
        print ("While connecting failed due to :{0}".format(str(e)))
        return []

def uploadToS3(client, content, bucket, key):
    try:
        client.put_object(Body=content, Bucket=bucket, Key=key)
    except FileNotFoundError:
        print("The file was not found")
        return False
    except NoCredentialsError:
        print("Credentials not available")
        return False

def updateFile(client, bucket, object_name, indexList):
    s3session = boto3.Session(
    ).resource('s3')
    s3_obj_body = s3session.Object(bucket_name=bucket, key=object_name).get()['Body']
    i = 0
    content = ''
    rowList = []
    for row in s3_obj_body._raw_stream:
        if i not in indexList:
            rowList.append(row)
        else:
            rowList.append(b'{}\n')
        i+=1
    content = b''.join(rowList)
    uploadToS3(client, content, os.environ.get("DestinationBucket"), object_name)

def lambda_handler(event, context):
    s3 = boto3.client('s3')
    userids = event['userids']
    useridsList = userids.split(",")
    res = get_user_files(useridsList)
    for row in res:
        parsedUri = urlparse(row[0])
        indexList = row[1]
        bucket = parsedUri.netloc
        s3object = parsedUri.path.lstrip('/')
        print('Updating file: ' + row[0] + '\n')
        updateFile(s3, bucket, s3object, indexList)
        print('File updated')

