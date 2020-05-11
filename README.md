## How to Implement GDPR Data Purging in AWS Data Lake

GDPR is an important aspect in today’s technology world and becoming a necessity when we implement solutions in AWS public cloud. There are several aspects of GDPR such as privacy, security, PII, right to be forgotten etc. Here we are trying to build a prototype or utility which will be a starting point and can give a reference architecture to customers, who wants to implement “Right to be forgotten” or “Data purging” use case in their data analytics solution. 

In AWS when we talk about data lake, most of the times we represent AWS S3 which is secure, and highly scalable object store. We might have millions or billions of objects in S3 data lake and if we need to delete data from the massive object store, then first thing we need to have is an index metastore which can help us identify the location of the data in S3 or other storage layers. Once we have identified the location/path, then the next action we can take is deleting the data from S3, either by deleting the complete object/file/record or by overwriting it.


## Design Considerations
So there are 2 aspects of the implementation.
1. Creating/updating index metastore, when an object is added/updated or deleted from the data lake
2. Once you have the index metastore, then we can have a manual approval flow implemented which will delete or purge data from the data lake

Now, there are 2 major questions we need to answer
1. How to create the index metastore, what to capture and in what format
2. What AWS technology stack we should use for the index metastore

To answer above 2 questions, we have evaluated various architecture design options and came up with below 4 options, which customers can choose from. Let's assume we have an use case which requires to purge data by customer ID or user ID, which acts as an unique identifier or primary key of our data

1. Scan every record of the data file to create index by row number:
--------------------------------------------------------------------
If the data volume is not too big to be scanned and the files are of managable size, then we can take this approach where as soon as file is uploaded to data lake, a Lambda or Glue based job will be triggered which will scan the whole file and create index for every record in metadata layer. So when we need to purge data, we can find the row number from the metastore, delete that from the S3 file and rewrite it again.


2. Scan only the file name to create metadata:
----------------------------------------------
Let's assume the file size is massive and customer feels, scanning every file to create row based index store is an costly operation, then they can go for this option, which suggests that customers should have a pre-processing step in their data pipeline, that can create output file by customer ID. They can still continue with their existing partitioning mechanism and just make sure the file they write to S3 partition is grouped by customer ID and the file name format can be like "<customerid>-<filename>.<extension>"

With this approach, your index metastore can capture the customer ID from the file name and save the path for it and delete the whole file/object during purging flow


3. Additional metadata file with the data file:
-----------------------------------------------
This might be a hybrid option of #1 and #2, where every file customer uploads to the data lake, will have a respective metadata file.

This additional metadata file might have information like what all customer IDs are there in the file, Or even row level information. Your index metastore should be structured accordingly to capture it.


4. Leverage tagging feature of AWS Services:
--------------------------------------------
This can be a simpler way of implementation, where you are relying in AWS tagging feature to capture additional metadata and use that for purging. This option might have limitations as you loose the flexibility of customizing metastore as per your need. But still customers can choose this, if they feel creating custom metastore adds complexity and they can live with the tag values. But they need to consider limitaions like maximum tags they can add per object, exposing customer ID or other information as part of tag value and custom solution to query or filter objects by tags.


After we answered our first question of how to store metadata or index, now let's see what all technology options we can consider. Please note, we considered below few AWS services but customers can go for other storage solutions as per their need.

- AWS S3: This is cost wise cheaper but involves complex operations to update/delete metadata
- RDS: It's easier to insert/update/delete index metadata records with easy SQL access for application layer
- DynamoDB: A key value based NoSQL managed service. Got better scalability, cross region replication and can support changing schema. But adds complexity while querying NoSQL data
- Elasticsearch: Great for searching through indexes and getting adhoc reports with Kibana

Please note, with Apache Hudi becoming popular, if customers don't have an existing data lake and starting from scratch then they can go with EMR + Hudi based data lake, which eases some of the burden of deleting/overwriting files. But we will still need an index metastore to capture data presence in other storage layers like RDS, DynamoDB or Redshift.

Also note that as part of this exercise we are considering data purging on AWS S3 which is the data lake, but enterprise customers will also have other storage layers like RDS, DynamoDB, Redshift that might have dimensional data or aggregated tables of same customer ID. This architecture will suffice introduction of additional storage layers too, as your index metastore will just have additional attributes to capture presence of data in other storage layers against the same customer ID. For example, if RDS has data for same customer ID, then your index metastore can have an additional column with value as "database1.table2.column3", which your purging utility can use to purge data from RDS .


## Reference Architecture for implementation
Below is the reference architecture we have created, which has 3 user flows.
1. Updating index metastore as data is written to storage layer 
2. Step Functions based workflow for data purging, that goes through manual email approval flow to delete
3. Updating index metastore in batch mode, which will create metadata for past objects

<img src="https://github.com/aws-samples/gdpr-data-purging-in-aws-data-lake/blob/master/Reference-Architecture-DataLake-DataPurging.JPG"/>

Below is the detail step for each user flow. Please note the dotted lines represents options. The first dotted line shows "Data Storage Layer Options" which can be either S3, RDS or DynamoDB and in our case we have just taken S3 data lake. The second dotted line represents "Index Metastore Options", where we have included either RDS or DynamoDB and you can include others like Elasticsearch.

1. Real time meta store update with S3:
---------------------------------------
- User uploads objects to S3 or deletes an existing object that triggers defined Lambda function through S3 event
- Lambda parses the object data/meta data to find existence of metadata in meta store (RDS or Dynamo DB) and take add/update/delete action to keep it up to date
- Same flow will be implemented if records added/updated to RDS or other storage layers, that will trigger respective Lambda to update metastore
- As of now we have kept DynamoDB and RDS as the index metadata storage options, you can add ES or other storage solutions
	
	
2. Data Purging
---------------
- This is the critical piece, which takes user input to identify which user records needs to be deleted and triggers step functions through CloudWatch to orchestrate the workflow
- First step of the workflow, triggers Lambda function which scans metadata layer to find which all storage layers got that user record and generates a report which gets saved into S3 report bucket
- As a next step, Step Functions activity created which is picked up by a Lambda Node JS based worker, that sends email to approver through SES with Approve & Reject link
- User will have Approve and Reject links embedded in the email, which he can click that will invoke an API gateway endpoint that invokes the step functions to resume the workflow
- If user clicked the approve link, then step functions will trigger a Glue/Lambda job, which takes the report bucket as input and deletes objects/records from the storage layer and also updates the index metastore
- Post Glue/Lambda job, it invokes SNS to send success/failure email to the user


3. Batch Index update
---------------------
- Here user will provide metadata file, which will do batch index update for all the past objects for which metadata does not exists
- Here step functions will be invoked that will trigger Glue job to update metadata

Note: This particular user flow is not implemented as part of this exercise and customers can implement it as per their need
	

## Scope Covered as part of this Architecture or Utility
Knowing we have 4 design options for the index metastore and different AWS services for metastore, as part of this implementation, we have considered below 2 design options

Option 1: Scan every record of the data file in Amazon S3 to create index, with RDS as index metastore:
---------------------------------------------------------------------------------------------------
As files are uploaded to the data lake, a Lambda based job will scan the file and create index with row number and S3 path of the file in RDS database table (Columns: customer_id, s3_file_path, row_number). This RDS table will act as input to the purge utility, to take delete and overwrite action on S3 file

Below Lambda script is used to update the RDS metastore, by scanning the whole file. Please note, this integrates "psycopg2" Python library to make connection to RDS from Lambda.

Please note, below are the 3rd parties included into this Lambda script, which is listed under requirements.txt
- pg8000 (Github: https://github.com/mfenniak/pg8000, License: https://github.com/mfenniak/pg8000/blob/master/LICENSE)


1. /Scripts/index-by-row-number/lambda_function.py (Line no 39 to 45 integrates pg8000 for making connectivity with RDS. This can be replaced with any other library for JDBC connection)



Option 2: Scan file name to find meta data and use DynamoDB as index metastore:
---------------------------------------------------------------------------
As files are uploaded to the data lake, a Lambda based job will look at file name (e.g. 1001-<guid>.csv) to find customer ID and populate dynamoDB metadata table where customer_id acts as row key and S3 might be the attribute to capture the paths. (e.g. {"customer_id:": 1001, "s3":{"s3://path1", "s3://path2"}, "RDS":{"db1.table1.column1"}}). This DynamoDB table will act as input to the purge utility, which will find in what all storage layers the data is present and take delete/purge action accordingly.

Below Lambda script is used to update the DynamoDB metastore as files are added/deleted from S3 and is invoked through S3 events.

1. Python Lambda Script: /Scripts/index-by-file-name/update-dynamo-metadata.py
This Lambda script gets invoked when a file is added/deleted to S3 and updates DynamoDB metastore for it

Purging flow is implemented through Step Functions workflow and Lambda scripts

1. Step Functions Definition: /Scripts/index-by-file-name/step-function-definition.json
This step functions definition implements the purge flow of the architecture which goes through manual workflow approval using Step function's activity worker & wait for callback feature.

2. Python Lambda Script: /Scripts/index-by-file-name/generate-purge-report.py
- This is the first step of the Step functions, which gets triggered when user uploads CSV into input bucket, that includes customer IDs as comma separated values (e.g. 1001,1002,1003), whose record needs to be deleted
- This scans DynamoDB metastore, generates a report and writes to report S3 bucket

3. Node JS Lambda script: /Scripts/index-by-file-name/ManualStepActivityWorker.js
- This Lambda function gets invoked by CloudWatch every 1 minute to capture any instance of Step function which is waiting for call back and then gets it's task token to form Approve/Reject link and send SES email to approver with S3 report path.

4. Python Lambda Script: /Scripts/index-by-file-name/gdpr-purge-data.py
- This Lambda function gets invoked, after user provides approval (by clicking approve link over email), which reads the report bucket report and deletes data from S3 bucket and updates the meta store too

## Additional References
- This repository does include some sample CSV data which is under "Sample-Data" folder, that can be used by users to test the utility

- To implement the manual approval flow through API Gateway and Step Functions Activity / Callback feature, you can refer below blog which outlines detail steps on how to configure it
https://aws.amazon.com/blogs/compute/implementing-serverless-manual-approval-steps-in-aws-step-functions-and-amazon-api-gateway/

- To trigger Step functions flow, based on S3 file arrival you can follow steps described in below AWS documentation
https://docs.aws.amazon.com/step-functions/latest/dg/tutorial-cloudwatch-events-s3.html


## Purging Flow Execution Snapshots

Below is a snapshot of the Step Functions flow, which will give you an idea of how the purge flow will work

1. Step Functions flow generated purge report and waiting for approval
<img width="400px" src="https://github.com/aws-samples/gdpr-data-purging-in-aws-data-lake/blob/master/stepfunctions_graph_waiting_for_approval.png"/>

2. Email Received by Approver
<img width="400px" src="https://github.com/aws-samples/gdpr-data-purging-in-aws-data-lake/blob/master/stepfunctions_approval_email.png"/>

3. Approver approved purge request and purge flow completed
<img width="400px" src="https://github.com/aws-samples/gdpr-data-purging-in-aws-data-lake/blob/master/stepfunctions_purge_flow.png"/>

4. Approver rejected purge request
<img width="400px" src="https://github.com/aws-samples/gdpr-data-purging-in-aws-data-lake/blob/master/stepfunctions_graph_purge_flow_rejected.png"/>


## Conclusion 
I am sure, this reference architecture, design options and sample scripts will give you a great start and thought process to implement GDPR right to be forgotten or data purging requirement. When customers implement data purging in production, they will look for additional features like delete from other storage layers, or delete data older than some date. This can be a starting point and you can customize it with more features and choosing/introducing additional design options to productionalize it.  

Also in the architecture we have integrated Lambda to purge data from the data lake, you can replace it with AWS Glue if the data volume is massive and we need distributed processing.

Please do let us know your feedback in comments and how did you really implement it in your organzation, so that other customers can learn from it. Happy Learning!

## License

This library is licensed under the MIT-0 License. See the LICENSE file.

