from __future__ import print_function

import json
import boto3
import time
import urllib
import decimal
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key, Attr

# Create global dynamodb and S3 clients, which can be used through multiple functions
dynamoClient = boto3.resource('dynamodb')

# Make sure, you change this to your dynamodb table name
dynamotable = dynamoClient.Table("data-metadata")

s3client = boto3.client('s3')


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            if o % 1 > 0:
                return float(o)
            else:
                return int(o)
        return super(DecimalEncoder, self).default(o)
        
# Convert CSV format to list, which can be used as input in dynamoDB API
def convertToDynamoKeys(sAllKeys, columnKey):
    #print(sAllKeys)
    listKeys = sAllKeys.split(",")
    dynamoKeys = []
    for iKey in listKeys:
        sKeyDict = {columnKey: {"S": iKey}}
        dynamoKeys.append(sKeyDict)
        
    return dynamoKeys
    
# Form S3 full path and invoke S3 delete_object
def deleteS3Object(userid, s3FilePath):
    print(s3FilePath)
    s3path = s3FilePath.replace("s3://","")
    print(s3path)
    slashIndex = s3path.find("/")
    print(slashIndex)
    if slashIndex > 0:
        s3bucket = s3path[0:slashIndex]
        print(s3bucket)
        s3Key = s3path[slashIndex+1:]
        print(s3Key)
        obj = s3client.delete_object(Bucket=s3bucket, Key=s3Key)
        #obj.delete()
        print("S3 Path:"+s3FilePath+", for customer:"+userid+" deleted successfully!")
    else:
        return
    
    
    
def deleteDynamoMetadata(userid, s3FilePath):
    # Delete API call of DynamoDB to delete a record by userid attribute
    response = dynamotable.delete_item(
        Key={
            'userid': userid
        }
    )
    print("Dynamo S3 Metadata path:"+s3FilePath+", for customer:"+userid+" deleted successfully!")
    
    
def lambda_handler(event, context):
    try:
		# Receive input from step functions input data
        source_bucket = event['Input']['bucket'] 
        file_key = event['Input']['ApprovedJSONValKey'] 
        
		# Read the JSON string from the report bucket object and convert to JSON object
        response = s3client.get_object(Bucket=source_bucket, Key=file_key)  
        JSONString = json.loads(response['Body'].read().decode('utf-8'))
        response = JSONString
         
        client = boto3.resource('dynamodb')
        table = client.Table("data-metadata")
        
		# Parse the JSON report data and loop it for every userid to delete data from S3 data lake and from metastore
        if JSONString.get('Responses') != None:
            for userdata in JSONString['Responses']['data-metadata']:
                sUserID = userdata['userid']['S']
                
                if userdata.get('S3') != None:
                    print("Starting to delete S3 Objects for User:"+sUserID)
                    for users3data in userdata['S3']['SS']:
                        deleteDynamoMetadata(sUserID, users3data)
                        deleteS3Object(sUserID, users3data)
                else:
                    print("No S3 Objects to be deleted!")
                    
       
    except ClientError as e:
        print("Sorry something went wrong!")
        print(e.response['Error']['Message'])
    else:
        print("NO error occured!")

    return {
        'statusCode': 200,
        'body': json.dumps('Report created successfully!')
    }
