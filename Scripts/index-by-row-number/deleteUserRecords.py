#!/usr/bin/env python

"""
Below are the 3rd parties this script includes
1. pg8000
(Github: https://github.com/mfenniak/pg8000,
License: https://github.com/mfenniak/pg8000/blob/master/LICENSE)
Line no 39 to 45 integrates pg8000 for making connectivity with RDS. 
"""

import os
import boto3
import pg8000
import botocore
from botocore.exceptions import NoCredentialsError, ClientError
from urllib.parse import urlparse

def get_connection():
    """
        Method to establish the connection.
    """
    try:
        print ("Connecting to database")
        # Create a low-level client with the service name for rds
        client = boto3.client("rds")
        # Read the environment variables to get DB EndPoint
        DBEndPoint = os.environ.get("DBEndPoint")
        # Read the environment variables to get the Database name
        DatabaseName = os.environ.get("DatabaseName")
        # Read the environment variables to get the Database username which has access to database.
        DBUserName = os.environ.get("DBUserName")
        # Generates an auth token used to connect to a db with IAM credentials.
        password = client.generate_db_auth_token(
            DBHostname=DBEndPoint, Port=5432, DBUsername=DBUserName
        )
        # Establishes the connection with the server using the token generated as password
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

def get_customer_files(customerids):
    try:
        myConnection = get_connection()
        cur = myConnection.cursor()
        sql = """
            SELECT s3path,
                ARRAY_AGG(recordline)
                FROM staging_customer_objects
                WHERE customerid in (%s)
                GROUP BY 1
                ;
            """ % ','.join('%s' for i in customerids)
        cur.execute(sql, customerids)
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
    customerids = event['customerids']
    customeridsList = customerids.split(",")
    res = get_customer_files(customeridsList)
    for row in res:
        parsedUri = urlparse(row[0])
        indexList = row[1]
        bucket = parsedUri.netloc
        s3object = parsedUri.path.lstrip('/')
        print('Updating file: ' + row[0] + '\n')
        updateFile(s3, bucket, s3object, indexList)
        print('File downloaded')
