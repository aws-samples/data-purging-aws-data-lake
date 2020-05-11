from __future__ import print_function

import json
import boto3
import time
import urllib
import decimal
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key, Attr

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
    listKeys = sAllKeys.split(",")
    dynamoKeys = []
    for iKey in listKeys:
        sKeyDict = {columnKey: {"S": iKey}}
        dynamoKeys.append(sKeyDict)
        
    return dynamoKeys
    
    
def lambda_handler(event, context):
    try:
        # Receive input from step functions input data
        source_bucket = event['Input']['bucket'] 
        file_key = event['Input']['key']  
        
		# Get customer IDs from input CSV and convert to List to be used in dynamodb batch_get_item API
        s3client = boto3.client('s3')
        csvfile = s3client.get_object(Bucket=source_bucket, Key=file_key)
        userIDs = csvfile['Body'].read().decode('utf-8')
        dynamoBatchGetKeys = convertToDynamoKeys(userIDs,"userid")    
    
        dynamoclient = boto3.client('dynamodb')        
        response = dynamoclient.batch_get_item(
            RequestItems = {
                "data-metadata": {
                    "Keys": dynamoBatchGetKeys
                }
            }
        )
        
        # Loop through the DynamoDB API response to generate report for the approver
        ReportContent = ""
        
        if response['ResponseMetadata']['HTTPStatusCode'] == 200:
            for userdata in response['Responses']['data-metadata']:
                ReportContent += ">> User ID:"+userdata['userid']['S']
                if userdata.get('S3') != None:
                    ReportContent += "\r\n> S3 Objects to be deleted:"
                    for users3data in userdata['S3']['SS']:
                        ReportContent += "\r\n"+users3data
                else:
                    ReportContent += "\r\n> No S3 Objects to be deleted!"
                    
                
                if userdata.get('RDS') != None:
                    ReportContent += "\r\n\r\n> RDS Records to be deleted:"
                    for userRDSdata in userdata['RDS']['SS']:
                        ReportContent += "\r\n"+userRDSdata
                else:
                    ReportContent += "\r\n\r\n> No RDS Records to be deleted!"
                    
                
                if userdata.get('DynamoDB') != None:
                    ReportContent += "\r\n\r\n> Dynamo Records to be deleted:"
                    for userDynamodata in userdata['DynamoDB']['SS']:
                        ReportContent += "\r\n"+userDynamodata
                else:
                    ReportContent += "\r\n\r\n> No Dynamo Records to be deleted!"
                    
                ReportContent += "\r\n\r\n\r\n"
                    
			# Write the report content into report bucket/object for the approver to review
            s3OutKey = "report/report-out.txt"
            writeResponse1 = s3client.put_object(
                Bucket=source_bucket,
                Key=s3OutKey,
                Body=ReportContent
            )
            
			# Write Dynamo JSON response as it is to another file, which can be consumed by the purge flow
            s3JSONOutKey = "report/report-out-json.txt"
            writeResponse2 = s3client.put_object(
                Bucket=source_bucket,
                Key=s3JSONOutKey,
                Body=json.dumps(response)
            )
                    
        else:
            print("Sorry dynamo batch getitem returned error!")

        # Return both report and JSON file paths to step functions, so that purge flow state can take this as input
        return({"EmailKey":"s3://"+source_bucket+"/"+s3OutKey,"JSONValKey":s3JSONOutKey})
        
    except ClientError as e:
        print("Sorry something went wrong!")
        print(e.response['Error']['Message'])
    else:
        print("NO error occured!")

    return {
        'statusCode': 200,
        'body': json.dumps('Report created successfully!')
    }
