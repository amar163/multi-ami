from __future__ import print_function
import json
import boto3
from botocore.exceptions import ClientError

BUCKET_NAME = 'demos-s3-lambda'


def download_file(BUCKET_NAME, ssmKey, ssmValue): 
    s3 = boto3.resource('s3')
    s3Client = boto3.client('s3')

    try:
        if ssmKey == 'linux-base-image':
            folderName = 'linux'
        else:
            folderName = 'windows'    
        filesResponse = s3Client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=folderName)
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
    except ClientError as e:
        return False


def lambda_handler(event, context):
    ssmKey = event['detail']['name']
    ssm = boto3.client('ssm')
    ssm_parameter = ssm.get_parameter(Name=ssmKey, WithDecryption=True)
    ssmValue = ssm_parameter['Parameter']['Value']
    print(ssmKey) 
    print(ssmValue)
    download_file(BUCKET_NAME, ssmKey, ssmValue)
