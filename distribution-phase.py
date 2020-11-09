import os
import json
import boto3

# S3 bucket
BUCKET_NAME = os.environ['BUCKET_NAME']

# SNS Topic name
SNS_TOPIC = os.environ['SNS_TOPIC']

currentRegion = os.environ['AWS_REGION']

# Get Account ID
account_id = boto3.client('sts').get_caller_identity().get('Account')

# boto3 instances
src_ec2 = boto3.client('ec2', region_name=currentRegion)
sns = boto3.client('sns')


def lambda_handler(event, context):
    ssmKey = event['detail']['name']
    ssm = boto3.client('ssm')
    ssm_parameter = ssm.get_parameter(Name=ssmKey, WithDecryption=True)
    ssmValue = ssm_parameter['Parameter']['Value'] 
    
    appName = ssmKey.split("-")[1]
    osType = ssmKey.split("-")[2]
    configFileName = osType + "-base-image/" + appName + "-config.json"
    
    
    # with open("dist.json", "r") as json_file:
    #   dist = json.load(json_file)  

    # sourceRegion = dist['sourceAmiRegion']
    
    # SNS variables
    # subject = "Distribution phase status"
    # snsTopicArn = ":".join(["arn", "aws", "sns", sourceRegion, srcAccount, SNS_TOPIC])
    
    dist = readConfigFile(BUCKET_NAME, configFileName)
    
    for dest in dist:
        destRegion = dest['destRegion']
        destAccount = dest['destAccount']
        destAccountRole = dest['destAccountRole']
        
        # Distribution list count
        dist_count = len(dist)
    
        #Declaring variable for validating sns topic
        validation_count = 0
        
        if account_id == destAccount :
            dest_ec2 = boto3.client('ec2', region_name=destRegion)
            
            # copying approved AMI into same account
            response = dest_ec2.copy_image(Name=ssmKey, Description=f"Copy of {ssmValue}", SourceImageId=ssmValue, currentRegion=currentRegion)
            if response['ResponseMetadata']['HTTPStatusCode'] == 200:
                validation_count = validation_count + 1

        else :
            src_ec2.modify_image_attribute(
                  Attribute='launchPermission',
                  ImageId=ssmValue,
                  OperationType='add',
                  UserIds=[destAccount]
            )
            image_details = src_ec2.describe_images(
                ImageIds=[
                    ssmValue
                ],
                Owners=[
                'self'
            ]
            )
            snapshotId = image_details['Images'][0]['BlockDeviceMappings'][0]['Ebs']['SnapshotId']
            src_ec2.modify_snapshot_attribute(
                  Attribute='createVolumePermission',
                  OperationType='add',
                  SnapshotId=snapshotId,
                  UserIds=[destAccount]
            )   
            client = boto3.client('sts')
            getCred = client.assume_role(RoleArn=destAccountRole, RoleSessionName=destAccount)
            cred = getCred['Credentials']
            tempSession = boto3.Session(aws_access_key_id=cred['AccessKeyId'],
                                        aws_secret_access_key=cred['SecretAccessKey'],
                                        aws_session_token=cred['SessionToken'],
                                        region_name=destRegion)
            client = tempSession.client('ec2', region_name=destRegion)
            
            # copying approved AMI into different account
            cross_response = client.copy_image(Name=ssmKey,
                              Description=f"Copy from Main account",
                              SourceImageId=ssmValue,
                              SourceRegion=currentRegion)
                              
            if cross_response['ResponseMetadata']['HTTPStatusCode'] == 200:
                validation_count = validation_count + 1

    # publish notification to topic
    if validation_count == dist_count:
        snsNotify(200)
        print("AMI Copying initiated successfully")
        # return {
        #     'statusCode': 200,
        #     'body': json.dumps(ssmKey + ' AMI Copying initiated successfully')
        # }
    else:
        snsNotify(400)
        print("AMI Copying failed")
        # return {
        #     'statusCode': 400,
        #     'body': json.dumps(ssmKey + ' AMI Copying failed')
        # }


# Read config file
def readConfigFile(bucketName, configFileName):
        s3 = boto3.resource('s3')
        dist = None
        content_object = s3.Object(bucketName, configFileName)
        file_content = content_object.get()['Body'].read().decode('utf-8')
        json_content = json.loads(file_content)
        
        for config in json_content['regionConfig']:
            if(config['region'] == currentRegion):
                dist = config['distributions']
        return dist    
    
# SNS Notification
def snsNotify(statusCode):
    snsTopicArn = ":".join(["arn", "aws", "sns", currentRegion, account_id, SNS_TOPIC])
    if statusCode == 200:
        subject = "Distribution Phase completed successfully"
        messageBody = "AMI Copying initiated successfully"
    elif statusCode == 400:
        subject = "Distribution Phase did not complete successfully"
        messageBody = "AMI Copying failed"
    client = boto3.client('sns')
    client.publish(
            TopicArn = snsTopicArn,
            Message = messageBody,
            Subject = subject
    )