from __future__ import print_function
import subprocess
import json
import boto3
import re
import os
import uuid
from packerpy import PackerExecutable
from botocore.exceptions import ClientError

download_dir = '/tmp/'
GITHUB_EMAIL = os.environ['GITHUB_EMAIL']
GITHUB_USERNAME = os.environ['GITHUB_USERNAME']
GITHUB_REPO = os.environ['GITHUB_REPO']
currentRegion = os.environ['AWS_REGION']
SNS_TOPIC = os.environ['SNS_TOPIC']

# Get Account ID
account_id = boto3.client('sts').get_caller_identity().get('Account')


# To be deleted
dest_lambda = "terraform_test"

def update_ssm_parameter(param, value):
    print(value)
    SSM_CLIENT = boto3.client('ssm')
    response = SSM_CLIENT.put_parameter(
        Name=param,
        Value=value,
        Type='String',
        Overwrite=True
    )

    if type(response['Version']) is int:
        return True
    else:
        return False


def readConfigFile(bucketName, configFileName):
    s3 = boto3.resource('s3')
    amiConfig = None
    content_object = s3.Object(bucketName, configFileName)
    file_content = content_object.get()['Body'].read().decode('utf-8')
    json_content = json.loads(file_content)
 
    for config in json_content['regionConfig']:
        if(config['region'] == currentRegion):
            amiConfig = config['amiConfig']
    return amiConfig

def checkoutFilesFromGit():
    ssm = boto3.client('ssm')
    ssm_value = ssm.get_parameter(Name='GITHUB_TOKEN', WithDecryption=True)
    GITHUB_TOKEN  = ssm_value['Parameter']['Value']
    subprocess.call('rm -rf /tmp/*', shell = True)    
    subprocess.call(f"git clone https://{GITHUB_USERNAME}:{GITHUB_TOKEN}@github.com/{GITHUB_USERNAME}/{GITHUB_REPO}.git", shell = True, cwd='/tmp')   

def readEvent(currentEvent):
    bucketName = ''
    configFileName = ''
    if currentEvent['eventSource'] == 'aws:s3' and currentEvent['eventName'] == 'ObjectCreated:Put':
        bucketName = currentEvent['s3']['bucket']['name']
        configFileName = currentEvent['s3']['object']['key']    
    return bucketName, configFileName


def invokePacker(region, packerFile, installScript, amiBaseImage, targetAmiName, appName, osType):
    amivalue = ""
    pkr = PackerExecutable("/opt/python/lib/python3.8/site-packages/packerpy/packer")

    if packerFile == "common-packer-linux.json":
        template = download_dir + GITHUB_REPO + '/' + osType  + '/' + packerFile
        installScriptFile = download_dir + GITHUB_REPO + '/' + osType + '/' + appName + '/' + installScript
        template_vars = {'baseimage': amiBaseImage, 'installScript': installScriptFile, 'targetAmiName':targetAmiName, 'region': region}
    else:
        template = download_dir + GITHUB_REPO + '/' + osType  + '/' + packerFile
        installScriptFile = download_dir + GITHUB_REPO + '/' + osType + '/' + appName + '/' + installScript
        user_data_file = download_dir + GITHUB_REPO + '/' + osType+ '/' + appName + '/bootstrap_win.txt'
        template_vars = {'baseimage': amiBaseImage, 'installScript': installScriptFile, 'userdata_file': user_data_file, 'targetAmiName':targetAmiName, 'region': region}
    (ret, out, err) = pkr.build(template, var=template_vars)
    
    
    outDecoded = out.decode('ISO-8859-1')
    print(outDecoded)
    if ret == 0:
        ami = re.search((':ami-[0-9][a-zA-Z0-9_]{16}'), outDecoded)
        amivalue = ami.group(0)
        amivalue = amivalue[1:]
    return amivalue

# SNS Notification    
def snsNotify(appName, newAmi, statusCode):
    snsTopicArn = ":".join(["arn", "aws", "sns", currentRegion, account_id, SNS_TOPIC])
    if statusCode == 200:
        subject = "Build phase completed successfully"
        messageBody = 'AMI id'+ ' '+ newAmi +' '+ 'is created for' + ' ' + appName  
    elif statusCode == 300:
        subject = "Build phase did not complete successfully"
        messageBody = 'AMI id is created for' + ' ' + appName     
    elif statusCode == 400:
        subject = "Build phase failed"
        messageBody = 'No AMI Config found for the app' + ' ' + appName  
    elif statusCode == 500:
        subject = "Build phase failed"
        messageBody = 'Couldnt retrieve S3 Object information'
    client = boto3.client('sns')
    client.publish(
            TopicArn = snsTopicArn,
            Message = messageBody,
            Subject = subject
    )
    

# creating trigger for validation phase 1 lambda
def trigger_lambda():
    id = uuid.uuid1()
    
    dest_lambda_arn = ":".join(["arn", "aws", "lambda", currentRegion, account_id, "function", dest_lambda])
    
    print("Lambda trigger created")

    client = boto3.client('events')
    rule_name = 'ssm_update_event'
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
                                            { "prefix": "app" }
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
    
    print("res ==== ",rule_res)

        
    lambda_client = boto3.client('lambda')
    lambda_client.add_permission(
        FunctionName=dest_lambda_arn,
        StatementId=str(id),
        # StatementId=custom_app,
        Action='lambda:InvokeFunction',
        Principal='events.amazonaws.com',
        SourceArn=rule_res['RuleArn']
    )


    response = client.put_targets(Rule='ssm_update_event',
                                   Targets=[
                                       {"Arn": dest_lambda_arn,
                                        "Id": '1'
                                        }])
    print("\nresponse ==== ",response)

     

def lambda_handler(event, context):
    print('ENTERED BUILD LAMBDA')
    bucketName = ''
    configFileName = ''
    
    events = event.get('Records', [])
    if len(events) > 0:
        currentEvent = events[0]
        eventDetails = readEvent(currentEvent)
        bucketName = eventDetails[0]
        configFileName = eventDetails[1]

    if bucketName != '' and configFileName != '':
        config = readConfigFile(bucketName, configFileName)
        if config is not None: 
            appName = config['appName']
            osType = config['osType']
            amiId = config['amiId']
            region = config['region']
            packerFile = config['packerFile']
            installScript = config['installScript']
            targetAmiId = config['targetAmiName']
            updateSSMID = config['amissmid']
            checkoutFilesFromGit()
            newAmi = invokePacker(region, packerFile, installScript, amiId, targetAmiId, appName, osType) 
            if newAmi != '':    
                update_ssm_parameter(updateSSMID, newAmi)
                
                # creating trigger for validation phase 1 lambda
                trigger_lambda()
                
                snsNotify(appName, newAmi, 200)
                print('Exiting Lambda')
                return {
                   'statusCode': 200,
                   'body': json.dumps('AMI Creation Successful')
                }
            else: 
                snsNotify(appName, newAmi, 300)
                return {
                    'statusCode': 300,
                    'body': json.dumps('AMI creation was not succesful')
                }
        else:
            snsNotify(appName, newAmi, 400)
            return {
                'statusCode': 400,
                'body': json.dumps('No AMI Config found')
            }
    else:
        snsNotify(appName, newAmi, 500)
        return {
            'statusCode': 500,
            'body': json.dumps('Couldnt retrieve S3 Object information')
        }