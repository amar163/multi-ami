import json
import boto3

# SNS Topic name
SNS_TOPIC = "Distribution-AMI"


def lambda_handler(event, context):
    ssmKey = event['detail']['name']
    ssm = boto3.client('ssm')
    ssm_parameter = ssm.get_parameter(Name=ssmKey, WithDecryption=True)
    ssmValue = ssm_parameter['Parameter']['Value'] 
    
    # Get Account ID
    srcAccount = boto3.client('sts').get_caller_identity().get('Account')
    
    with open("dist.json", "r") as json_file:
       dist = json.load(json_file)  

    sourceRegion = dist['sourceAmiRegion']
    src_ec2 = boto3.client('ec2', region_name=sourceRegion)
    sns = boto3.client('sns')
    
    # SNS variables
    subject = "Distribution phase status"
    snsTopicArn = ":".join(["arn", "aws", "sns", sourceRegion, srcAccount, SNS_TOPIC])
    
    for dest in dist['distributions']:
        destRegion = dest['destRegion']
        destAccount = dest['destAccount']
        destAccountRole = dest['destAccountRole']
        
        # Distribution list count
        dist_count = len(dist['distributions'])
    
        #Declaring variable for validating sns topic
        validation_count = 0
        
        if srcAccount == destAccount :
            dest_ec2 = boto3.client('ec2', region_name=destRegion)
            
            # copying approved AMI into same account
            response = dest_ec2.copy_image(Name=ssmKey, Description=f"Copy of {ssmValue}", SourceImageId=ssmValue, SourceRegion=sourceRegion)
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
                              SourceRegion=sourceRegion)
                              
            if cross_response['ResponseMetadata']['HTTPStatusCode'] == 200:
                validation_count = validation_count + 1

    # publish notification to topic
    if validation_count == dist_count:
        messageBody = (str(ssmKey) + " AMI Copying initiated successfully")
        response = sns.publish(
            TopicArn=snsTopicArn,
            Message=messageBody,
            Subject=subject
        )
    else:
        messageBody = (str(ssmKey) + " AMI Copying failed")
        response = sns.publish(
            TopicArn=snsTopicArn,
            Message=messageBody,
            Subject=subject
        )
                
    return {
       'statusCode': 200,
       'body': json.dumps('AMI Copied successfully')
    }

