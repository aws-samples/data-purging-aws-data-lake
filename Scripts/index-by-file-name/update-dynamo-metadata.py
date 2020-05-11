from __future__ import print_function

import json
import boto3
import time
import urllib
import decimal
from botocore.exceptions import ClientError

class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            if o % 1 > 0:
                return float(o)
            else:
                return int(o)
        return super(DecimalEncoder, self).default(o)
        
# This Lambda function receives the file name which is added/deleted from S3 and gets the customer ID or user ID from file name to create Dynamo index record
def lambda_handler(event, context):
    source_bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'])
    s3FilePath = 's3://'+source_bucket+'/'+key
    allKeys = key.split("/")
    userid = str((allKeys[len(allKeys)-1].split("-"))[0])+''
    s3EventType = event['Records'][0]['eventName']

    client = boto3.resource('dynamodb')
	
	# Please change the dynamoDB table name
    table = client.Table("data-metadata")
  
    
    try:
		# Please change the Key to your row key attribute
        response = table.get_item(
            Key={
                'userid': userid
            }
        )
        
		# Check if userid rowkey exists or not in dynamo DB. Based on that take add/update/delete action
        if response.get("Item") != None:
            print("GetItem succeeded. Item Found!")
            
            allItems = response['Item']
            
            if allItems.get('S3') != None:
                if s3FilePath in allItems["S3"]:
                    print("Yes S3Key exists in Dynamo Metadata!")
                    
                    if "Delete" in s3EventType:
                        response = table.update_item(
                            Key={
                                'userid': userid
                            },
                            UpdateExpression="DELETE S3 :val",
                            ExpressionAttributeValues={
                                ':val': set([s3FilePath])
                            },
                            ReturnValues="ALL_NEW"
                        )
                        print("Delete metadata successful for S3 Key:"+s3FilePath)
                    
                else:
                    print("No S3Key does not exsts in Dynamo Metadata!")
    
                    response = table.update_item(
                        Key={
                            'userid': userid
                        },
                        UpdateExpression="ADD S3 :val",
                        ExpressionAttributeValues={
                            ':val': set([s3FilePath])
                        },
                        ReturnValues="UPDATED_NEW"
                    )
                    print("Metadata updated successfully for S3 Key:"+s3FilePath)
            else:
                print("S3 attribute does not exists")
                response = table.update_item(
                    Key={
                        'userid': userid
                    },
                    UpdateExpression="ADD S3 :val",
                    ExpressionAttributeValues={
                        ':val': set([s3FilePath])
                    },
                    ReturnValues="UPDATED_NEW"
                )
                print("Metadata updated successfully for S3 Key:"+s3FilePath)
        else:
            if "Create" in s3EventType:
                print("Item not found! Inserting new record!")
                newPath = {s3FilePath}
                table.put_item(Item= {'userid': userid,'S3': newPath})
                print("Item inserted successfully!)")
        
    except ClientError as e:
        print("Sorry userid not found!")
        print(e.response['Error']['Message'])
    else:
        print("NO error occured!")

    return {
        'statusCode': 200,
        'body': json.dumps('Meta data created successfully!')
    }
