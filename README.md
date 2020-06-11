## How to Implement Data Purging in AWS Data Lake

Data purging is an important aspect in today’s technology world and becoming a necessity when we implement solutions in AWS public cloud. Here we are trying to provide a reference architecture along with few sample scripts which will be a starting point for customers, who would like to implement “Data purging” use case in their data analytics solution. 

In AWS when we talk about Data Lake, most times we represent Amazon S3 which is a secure and highly scalable object store. In an enterprise after the raw data is available in Data Lake, for different business needs we apply various transformations and push the transformed output to different other storage layers like databases, data warehousing systems etc. which helps solving different use cases of the organization. Now if we need to identify what all data is there across what all storage layers, so that we can take action for deletion, then we can have a Metastore which captures that information and becomes the input to the data purging process. What the Metastore will capture as metadata might vary from organization to organization. The Metastore approach is one of the possible approaches and customers can look for other approaches as it fits their use case.

Through this guide, we will explain how we have integrated the Metastore and how it captures metadata to identify data presence in different storage layers. Also will explain how customers can integrate manual approval process, before the final data purging happens. To explain the flow, we have taken example of Amazon S3 storage layer and the approach can be extended to delete data from other storage layers. 


## Design Considerations
So there are 2 aspects of the implementation.
1. Creating/updating index Metastore, when an object is added/updated or deleted from the Data Lake
2. Once you have the metadata available in the index Metastore, then we can have a manual approval flow implemented which will delete or purge data from the Data Lake

Now, there are 2 major questions we need to answer
1. How to create the index Metastore, what to capture and in what format
2. What AWS technology stack we should use for the index Metastore

To answer above 2 questions, we have evaluated various architecture design options and came up with below 4 options. Please note, these are few of the options we have included here to give a starting point, which customers can choose from or reference to come up with their own design that fits their organization use case better. Let's assume we have a use case which requires to purge data by customer ID or user ID that acts as a unique identifier or primary key of our data.

1. Scan every record of the data file to create index by row number:
--------------------------------------------------------------------
If the data volume is not too big to be scanned and the files are of manageable size, then we can take this approach where as soon as a file is uploaded to the Data Lake, an AWS Lambda or AWS Glue based job will be triggered which will scan the whole file and create an index for every record in the metadata layer. So when we need to purge data, we can find the row number from the Metastore, delete that from the Amazon S3 object and create a new version of it.


2. Scan only the file name to create metadata:
----------------------------------------------
Let's assume the file size is massive and customer feels, scanning every file to create row based index store is a costly operation, then they can go for this option, which suggests that customers should have a pre-processing step in their data pipeline, that can create output file by customer ID. They can still continue with their existing partitioning mechanism and just make sure that the file they write to Amazon S3 partition is grouped by customer ID and the file name format can be like "<customerid>-<filename>.<extension>"

With this approach, your index Metastore can capture the customer ID from the file name, save the file path in Metastore and refer same to delete the whole file/object during purging flow.


3. Additional metadata file with the data file:
-----------------------------------------------
This might be a hybrid approach of #1 and #2, where every file customer uploads to the Data Lake, will have a respective metadata file.

This additional metadata file might have information like what all customer IDs are there in the file, or even row level information. Your index Metastore should be structured accordingly to capture it.


4. Leverage tagging feature of AWS Services:
--------------------------------------------
This can be a simpler way of implementation, where you are relying on AWS tagging feature to capture additional metadata and use that for purging. This option might have limitations as you miss the flexibility of customizing Metastore as per your need. But still customers can choose this, if they feel creating custom Metastore adds complexity and they can live with the tag values. But they need to consider limitations like maximum tags they can add per object, exposing customer ID or other information as part of tag value and a custom solution to query or filter objects by tags.


After we answered our first question of how to store metadata or index, now let's see what all technology options we can consider. Please note, we considered below few AWS services but customers can go for other storage solutions as per their need.

- Amazon S3: This is cost wise cheaper but involves complex operations to update/delete metadata
- Amazon RDS: It's easier to insert/update/delete index metadata with easy SQL access for application layer
- Amazon DynamoDB: A key value based NoSQL managed service. Got better scalability, cross region replication and can support changing schema. But adds complexity while querying NoSQL data
- Amazon Elasticsearch Service (Amazon ES): Great for searching through indexes and getting ad hoc reports with Kibana

Please note, with Apache Hudi becoming popular, if customers don't have an existing Data Lake and starting from scratch then they can go with Amazon EMR + Hudi based Data Lake, which eases some of the burden of deleting files. But we will still need an index Metastore to capture data presence in other storage layers like Amazon RDS, Amazon DynamoDB or Amazon Redshift.

Also note that as part of this exercise we are considering data purging on Amazon S3 which is the Data Lake, but enterprise customers will also have other storage layers like Amazon RDS, Amazon DynamoDB and Amazon Redshift that might have dimensional data or aggregated tables of same customer ID. This architecture will suffice introduction of additional storage layers too, as your index Metastore will just have additional attributes to capture presence of data in other storage layers against the same customer ID. For example, if Amazon RDS has data for same customer ID, then your index Metastore can have an additional column with value as "database1.table2.column3", which your purging script can use to purge data from Amazon RDS easily.


## Reference Architecture for implementation
Below is the reference architecture we have created, which has 3 user flows.
1. Updating index Metastore as data is written to the storage layer 
2. AWS Step Functions based workflow for data purging that goes through manual email approval flow to delete
3. Updating index Metastore in batch mode, which will create metadata for past objects

<img src="https://github.com/aws-samples/data-purging-aws-data-lake/blob/master/Reference-Architecture-DataLake-DataPurging.JPG"/>

Below is the detail step for each user flow. Please note the dotted lines represents options. The first dotted line shows "Data Storage Layer Options" which can be either Amazon S3, Amazon RDS, Amazon DynamoDB etc. and in our sample implementation, we have just taken Amazon S3 Data Lake. The second dotted line represents "Index Metastore Options", where we have included either Amazon RDS, Amazon DynamoDB and you can include others like Amazon Elasticsearch Service too. 

1. Real time Metastore update with Amazon S3:
---------------------------------------
- User uploads object to Amazon S3 or deletes an existing object that triggers defined AWS Lambda function through Amazon S3 event
- AWS Lambda parses the object data/metadata to find existence of metadata in Metastore (Amazon RDS or Amazon DynamoDB) and take add/update/delete action to keep it up to date
- Same flow will be implemented if record added/updated to Amazon RDS or other storage layers that will trigger respective AWS Lambda event to update the Metastore
- As of now we have kept Amazon DynamoDB and Amazon RDS as the index metadata storage options, you can add Amazon ES or other storage solutions too
	
	
2. Data Purging
---------------
- This is the critical piece, which takes user input to identify which user records needs to be deleted and then triggers AWS Step Functions workflow through CloudWatch to orchestrate the flow
- First step of the workflow, triggers AWS Lambda function which scans metadata layer to find which all storage layers got that user record and generates a report which gets saved into Amazon S3 report bucket
- As a next step, AWS Step Functions activity created which is picked up by an AWS Lambda function worker, based on Node JS that sends email to approver through Amazon SES with Approve & Reject links
- User will have Approve and Reject links embedded in the email, which he can click that will invoke an Amazon API gateway endpoint that invokes the AWS Step Functions to resume the workflow
- If user clicked the approve link, then AWS Step Functions will trigger a AWS Glue or AWS Lambda job, which takes the report bucket as input and deletes objects/records from the storage layer and also updates the index Metastore
- Post AWS Glue/AWS Lambda job completion, it invokes Amazon SNS to send success/failure notification to the user


3. Batch Index update
---------------------
- Here user will provide metadata file, which will do batch index update for all the past objects for which metadata does not exists
- Here AWS Step Functions can be invoked that will trigger Glue job to update metadata

Note: This particular user flow is not implemented as part of this exercise and customers can implement it as per their need
	

## Scope Covered as part of this Architecture
Knowing we have 4 design options for the index Metastore and different AWS services for Metastore, as part of this implementation, we have considered below 2 design options

Option 1: Scan every record of the data file in Amazon S3 to create index, with Amazon RDS as index Metastore:
---------------------------------------------------------------------------------------------------
As files/objects are uploaded to the S3 Data Lake, an AWS Lambda based job will scan the file to create index with row number and add Amazon S3 path of the file to Amazon RDS database table (Columns: customer_id, Amazon S3_file_path, row_number). This Amazon RDS table will act as input to the purge process, to take delete action on Amazon S3 object

Below AWS Lambda script is used to update the Amazon RDS Metastore, by scanning the whole file.

Please note, below are the 3rd parties included into this AWS Lambda script, which is listed under requirements.txt
- pg8000 (Github: https://github.com/mfenniak/pg8000, License: https://github.com/mfenniak/pg8000/blob/master/LICENSE)


1. /Scripts/index-by-row-number/lambda_function.py (Lines no 28 to 33 use pg8000 to connect to Amazon RDS Postgres.
Lines no 43 to 54 use pg8000 to query to Amazon RDS Postgres.)
2. /Scripts/index-by-row-number/updateIndex.py (Lines no 30 to 35 use pg8000 to connect to Amazon RDS Postgres. Lines no 46 to 39 use pg8000 to insert data to Amazon RDS Postgres.)


Option 2: Scan file name to find metadata and use Amazon DynamoDB as index Metastore:
---------------------------------------------------------------------------
As files/objects are uploaded to the S3 Data Lake, an AWS Lambda based job will look at file name (e.g. 1001-<guid>.csv) to find customer ID and populate Amazon DynamoDB metadata table where customer_id acts as row key and S3 might be the attribute to capture the paths. (e.g. {"customer_id:": 1001, "S3":{"s3://path1", "s3://path2"}, "RDS":{"db1.table1.column1"}}). This Amazon DynamoDB table will act as input to the purge process, which will find in what all storage layers the data is present and take delete/purge action accordingly.

Below AWS Lambda script is used to update the Amazon DynamoDB Metastore as files are added/deleted from Amazon S3 and is invoked through Amazon S3 events.

1. Python AWS Lambda Script: /Scripts/index-by-file-name/update-dynamo-metadata.py
This AWS Lambda script gets invoked when a file is added/deleted from Amazon S3 and updates Amazon DynamoDB Metastore for it

Purging flow is implemented through AWS Step Functions workflow and AWS Lambda scripts

1. AWS Step Functions Definition: /Scripts/index-by-file-name/step-function-definition.json
This AWS Step Functions definition implements the purge flow of the architecture which goes through manual workflow approval using AWS Step function's activity worker & wait for callback feature.

2. Python AWS Lambda Script: /Scripts/index-by-file-name/generate-purge-report.py
- This is the first step of the AWS Step Functions, which gets triggered when user uploads CSV into input bucket, that includes customer IDs as comma separated values (e.g. 1001,1002,1003), whose record needs to be deleted
- This scans Amazon DynamoDB Metastore, generates a report and writes to report bucket in Amazon S3

3. Node JS AWS Lambda script: /Scripts/index-by-file-name/ManualStepActivityWorker.js
- This AWS Lambda function gets invoked by CloudWatch every 1 minute to capture any instance of AWS Step function which is waiting for call back and then gets its task token to form Approve/Reject link that sends email to the approver with Amazon S3 report file path.

4. Python AWS Lambda Script: /Scripts/index-by-file-name/purge-data.py
- This AWS Lambda function gets invoked, after user provides approval (by clicking approve link from email), which reads the report bucket input and deletes data from Amazon S3 Data Lake and updates the Metastore too

## Additional References
- This repository does include some sample CSV data which is under "Sample-Data" folder that can be used by users to test the flow

- To implement the manual approval flow through API Gateway and AWS Step Functions Activity / Callback feature, you can refer below blog which outlines detail steps on how to configure it
https://aws.amazon.com/blogs/compute/implementing-serverless-manual-approval-steps-in-aws-step-functions-and-amazon-api-gateway/

- To trigger AWS Step Functions flow, based on Amazon S3 file arrival you can follow steps described in below AWS documentation
https://docs.aws.amazon.com/step-functions/latest/dg/tutorial-cloudwatch-events-Amazon S3.html


## Purging Flow Execution Snapshots

Below is a snapshot of the AWS Step Functions flow, which will give you an idea of how the purge flow works

1. AWS Step Functions flow, generated purge report and waiting for approval
<img width="400px" src="https://github.com/aws-samples/data-purging-aws-data-lake/blob/master/stepfunctions_graph_waiting_for_approval.png"/>

2. Email Received by Approver
<img width="400px" src="https://github.com/aws-samples/data-purging-aws-data-lake/blob/master/stepfunctions_approval_email.png"/>

3. Approver approved purge request and purge flow completed
<img width="400px" src="https://github.com/aws-samples/data-purging-aws-data-lake/blob/master/stepfunctions_purge_flow.png"/>

4. Approver rejected the purge request
<img width="400px" src="https://github.com/aws-samples/data-purging-aws-data-lake/blob/master/stepfunctions_graph_purge_flow_rejected.png"/>


## Conclusion 
I am sure, this reference architecture, design options and sample scripts will give you a great start and thought process to implement data purging requirement in AWS Data Lake. When customers implement data purging in production, they will look for additional features like delete from other storage layers, or delete data older than specific date etc. This can be a starting point and you can customize it with more features and choosing/introducing additional design options to make it production ready.  

Also in the architecture we have integrated AWS Lambda to purge data from the Data Lake, you can replace it with AWS Glue if the data volume is massive and you need distributed processing.

Please do let us know your feedback in comments and how did you really implement it in your organization, so that others can learn from it. Happy Learning!

## License

This library is licensed under the MIT-0 License. See the LICENSE file.
