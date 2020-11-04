from __future__ import print_function
import json
import boto3
import os
from botocore.exceptions import ClientError

BUCKET_NAME = 'demos-s3-lambda11'
currentRegion = os.environ['AWS_REGION']
account_id = boto3.client('sts').get_caller_identity().get('Account')
SNS_TOPIC = 'assesment_complete_trigger'

def snsNotify(errorCode):
    snsTopicArn = ":".join(["arn", "aws", "sns", currentRegion, account_id, SNS_TOPIC])
    subject = "Build phase trigger status"
    messageBody =  errorCode 
    client = boto3.client('sns')
    client.publish(
            TopicArn = snsTopicArn,
            Message = messageBody,
            Subject = subject
    )

def download_file(BUCKET_NAME, ssmKey, ssmValue): 
    s3 = boto3.resource('s3')
    s3Client = boto3.client('s3')

    try:
        if ssmKey == 'linux-base-image':
            folderName = 'linux'
        else:
            folderName = 'windows'    
        filesResponse = s3Client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=folderName)
        if filesResponse['KeyCount'] > 0:
            configFileCount = 0    
            for s3_object in filesResponse['Contents']:
                if s3_object['Key'].endswith(("config.json", "_files")): 
                    filename = s3_object['Key']
                    s3object = s3.Object(BUCKET_NAME, filename)   
                    body = s3object.get()['Body'].read()
                    configData = json.loads(body)

                    for amiConfig in configData['regionConfig']:                    
                        amiConfig['amiConfig']['amiId'] = ssmValue

                    s3object.put(
                        Body=(bytes(json.dumps(configData).encode('UTF-8')))
                    ) 
            configFileCount += 1
            if configFileCount > 0:
                snsNotify('trigger.py lambda has completed and updated'+ ' ' + str(configFileCount) + ' '+ 'config files')         
        else:
            snsNotify('The folder' + ' ' + folderName +' '+'is not found or config files doesnot exist in this folder')              
    except ClientError as e:
        err = e.response
        snsNotify('The S3 bucket'+' '+ BUCKET_NAME + ' ' + 'is not found or cannot be accessed and the error code is:'+ ' ' +str(err))
        return False


def lambda_handler(event, context):
    ssmKey = event['detail']['name']
    ssm = boto3.client('ssm')
    ssm_parameter = ssm.get_parameter(Name=ssmKey, WithDecryption=True)
    ssmValue = ssm_parameter['Parameter']['Value']
    print(ssmKey) 
    print(ssmValue)
    download_file(BUCKET_NAME, ssmKey, ssmValue)
