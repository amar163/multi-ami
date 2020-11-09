from __future__ import print_function
import boto3
import json
import datetime
import urllib
import os
from botocore.exceptions import ClientError
import time
import uuid

sns = boto3.client('sns')
inspector = boto3.client('inspector')
s3 = boto3.client('s3')
ec2_client = boto3.client('ec2')
ssm_client = boto3.client('ssm')

currentRegion = os.environ['AWS_REGION']

# Get Account ID
account_id = boto3.client('sts').get_caller_identity().get('Account')

# SNS topic
SNS_TOPIC = os.environ['SNS_TOPIC']

# assesment report name
reportFileName = "assesmentReport.pdf"

# S3 Bucket Name
BUCKET_NAME = os.environ['BUCKET_NAME']

# finding results number
max_results = 250000

# list for no. of High severity incidents
high_severities_list = []

# setting up paginator for the listing findings
paginator = inspector.get_paginator('list_findings')

# filter for searching findings
finding_filter = {'severities': ['High']}

# Destination lambda
dest_lambda = "dist-ami"



def lambda_handler(event, context):
    # extract the message that Inspector sent via SNS
    message = event['Records'][0]['Sns']['Message']
    print(message)
    
    # getting template arn 
    template_arn = json.loads(message)['template']

    # get inspector notification type
    notificationType = json.loads(message)['event']

    targetArn = json.loads(message)['target']

    # checking for the event type
    if notificationType == "ASSESSMENT_RUN_COMPLETED":

        # getting arn for the assement run
        runArn = json.loads(message)['run']

        # generating the report
        while True:
            reportResponse = inspector.get_assessment_report(
                assessmentRunArn=runArn,
                reportFileFormat='PDF',
                reportType='FULL'
            )
            if reportResponse['status'] == 'COMPLETED':
                break
            time.sleep(5)

        # downloading the report
        file_status = urllib.request.urlretrieve(reportResponse['url'],
                                                 '/tmp/' + reportFileName)

        # uploading assessment report to s3
        upload_file('/tmp/' + reportFileName, BUCKET_NAME,
                    runArn.split(":")[5] + "/" + reportFileName)

        # getting the findings for the run Arn
        for findings in paginator.paginate(
                maxResults=max_results,
                assessmentRunArns=[
                    runArn,
                ],
                filter=finding_filter):
            for finding_arn in findings['findingArns']:
                high_severities_list.append(finding_arn)

        
        # Extracting the Latest AMI id from findings
        findings = inspector.list_findings(assessmentRunArns=[runArn])
        AMI_id = inspector.describe_findings(findingArns=[findings['findingArns'][0]])
        ssmValue = ''
        if AMI_id != '':

            # sending emails if no. of high severity issues are more than 1
            if len(high_severities_list) > 1:
    
                subject = "There is High Severity Issue in the assement run"
                messageBody = ("High severity issue is reported in assesment run" + runArn + "\n\n" +
                              "Please check the  detailed report here : " +
                              "s3://" + BUCKET_NAME + "/" + runArn.split(":")[5] + "/" + reportFileName)
    
                snsTopicArn = ":".join(["arn", "aws", "sns", currentRegion, account_id, SNS_TOPIC])
    
                # publish notification to topic
                response = sns.publish(
                    TopicArn=snsTopicArn,
                    Message=messageBody,
                    Subject=subject
                )
    
            else:
                # Creating trigger for initiating distribution phase
                trigger_lambda()
                
                # Getting SSM value
                ssmValue = ssm_name(template_arn)
                
                # Creating/Updating the AMI id in parameter store
                ssm_client.put_parameter(
                    Name="-".join(["approved", ssmValue]),
                    Value=str(AMI_id['findings'][0]['assetAttributes']['amiId']),
                    Description='Cutom_AMI_ID',
                    Type='String',
                    Overwrite=True
                )
    
                # Updating the security APPROVED tag
                ssm_client.add_tags_to_resource(
                    ResourceType='Parameter',
                    ResourceId="-".join(["approved", ssmValue]),
                    Tags=[
                        {
                            'Key': 'status',
                            'Value': 'Security_Approved'
                        },
                    ]
                )
            
            snsNotify(ssmValue,200)
            print("approved-"+ssmValue+" SSM parameter created/updated")
                
            # Deleting resources created for assessment run    
            delete_resources(AMI_id, targetArn)
            # return {
            #     'statusCode': 200,
            #     'body': json.dumps('approved-'+ssmValue+' SSM parameter created/updated')
            # }
        else:
            snsNotify(ssmValue,400)
            print("Assessment run failed")
            # return {
            #     'statusCode': 400,
            #     'body': json.dumps('Assessment run failed')
            # }



# uploading assessment report to s3
def upload_file(file_name, bucket, object_name=None):
    # If S3 object_name was not specified, use file_name
    if object_name is None:
        object_name = file_name

    # Upload the file
    s3_client = boto3.client('s3')
    try:
        response = s3_client.upload_file(file_name, bucket, object_name)
    except ClientError as e:
        logging.error(e)
        return False
    return True


# Getting SSM value    
def ssm_name(template_arn):
    try:
        # getting tag value of assessment template
        run_tags = inspector.list_tags_for_resource(
                resourceArn=template_arn
        )
        
        ssmValue = run_tags['tags'][0]['value']
        print("ssmValue : ",ssmValue)
        return ssmValue
    except ClientError as e:
        return logging.error(e)
    
    
# Creating trigger for initiating distribution phase
def trigger_lambda():
    id = uuid.uuid1()
    
    dest_lambda_arn = ":".join(["arn", "aws", "lambda", currentRegion, account_id, "function", dest_lambda])
    
    print("Lambda trigger created")
    
    # SSM update cloudwatch rule creation
    client = boto3.client('events')
    rule_name = 'ssm_update_dist'
    rule_res = client.put_rule(Name=rule_name, 
                    EventPattern= '''
                                    { 
                                    "source": [
                                        "aws.ssm"
                                    ],
                                    "detail-type": [
                                        "Parameter Store Change"
                                    ],
                                    "detail": {
                                        "name": [
                                            { "prefix": "approved-" }
                                        ],
                                        "operation": [
                                            "Create",
                                            "Update"
                                        ]
                                    }
                                   }
                                   '''
                                   ,
                                   State='ENABLED',
                    Description="Find the event changes for SSM")
                    
    # Adding trigger to current lambda    
    lambda_client = boto3.client('lambda')
    lambda_client.add_permission(
        FunctionName=dest_lambda_arn,
        StatementId=str(id),
        # StatementId=custom_app,
        Action='lambda:InvokeFunction',
        Principal='events.amazonaws.com',
        SourceArn=rule_res['RuleArn']
    )

    # adding target for trigger
    response = client.put_targets(Rule='ssm_update_event',
                                   Targets=[
                                       {"Arn": dest_lambda_arn,
                                        "Id": '1'
                                        }])


# Deleting resources created for assessment run
def delete_resources(AMI_id, targetArn):
        instance_id = ''
        sg_name = ''
        # Extracting Instance details
        instance_details = ec2_client.describe_instances(Filters=[
            {
                'Name': 'image-id',
                'Values': [AMI_id['findings'][0]['assetAttributes']['amiId']]
            }]
        )

        # Extracting Instance id and security group details
        for reservation in instance_details['Reservations']:
            for instance in reservation['Instances']:
                if instance['State']['Name'] == 'running':
                    for securityGroup in instance['SecurityGroups']:
                        sg_name = securityGroup['GroupName']
                        instance_id = instance['InstanceId']
        print(instance_id)
        print(sg_name)
        # Terminating instance
        ec2_client.terminate_instances(
            InstanceIds=[instance_id]
        )

        # Destroying assessment
        inspector.delete_assessment_target(
            assessmentTargetArn=targetArn
        )

        time.sleep(120)
        # Deleting Security group
        ec2_client.delete_security_group(GroupName=sg_name)
        
        
# SNS Notification
def snsNotify(ssmValue, statusCode):
    snsTopicArn = ":".join(["arn", "aws", "sns", currentRegion, account_id, SNS_TOPIC])
    if statusCode == 200:
        subject = "Validation Phase 2 completed successfully"
        messageBody = "approved-" + ssmValue + " SSM parameter created/updated"
    elif statusCode == 400:
        subject = "Validation phase 2 did not complete successfully"
        messageBody = "Assessment run failed"
    client = boto3.client('sns')
    client.publish(
            TopicArn = snsTopicArn,
            Message = messageBody,
            Subject = subject
    ) 