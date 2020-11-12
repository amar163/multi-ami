import os
import subprocess
import boto3
import uuid
from python_terraform import *

# Get Account ID
account_id = boto3.client('sts').get_caller_identity().get('Account')

# AWS current region
currentRegion = os.environ['AWS_REGION']

# Download directory for S3
download_dir = '/tmp/'

# SNS topic
SNS_TOPIC = os.environ['SNS_TOPIC']

# Destnation lambda
# dest_lambda = "validation-phase-2"

# GIT details
GITHUB_EMAIL = os.environ['GITHUB_EMAIL']
GITHUB_USERNAME = os.environ['GITHUB_USERNAME']
GITHUB_REPO = os.environ['GITHUB_REPO']



def lambda_handler(event, context):
    
    print(event)
    ssmValue = event['detail']['name']
    
    print(ssmValue)
    print(account_id)
    
    # Get Config file name
    osType = ssmValue.split("-")[1]
    print("osType is "+osType)
    
    # git clone
    checkoutFilesFromGit()

    # get ami id from SSM parameter
    ami_id = get_ami_id(ssmValue)
    print(ami_id)
    
    if ami_id != '':
        print('SSM parameter is available')
        
        # Execute terraform scripts for assessment run and fetch template arn as output
        output = execute(ami_id,osType)
        if output != '':
            print("Terraform scripts executed successfully")
            template_arn = output['template_arn']['value']
            print("template_arn ===== ", template_arn)
            
            # subscribe to SNS based event
            subscribe_to_event(template_arn)
            
            # creating trigger for validation phase 2 lambda 
            # trigger_lambda()
            
            # Running assessment template and tagging template
            start_assessment_run(template_arn, ssmValue)
            
            # SNS notify for successful run
            snsNotify(ssmValue,200)
            print("Validation Phase 1 completed successfully")
            
        else:
            # SNS notify for terraform failure
            snsNotify(ssmValue,400)
            print("Terraform execution failed")
            
    else:
        snsNotify(ssmValue,401)
        print("No such SSM parameter is available")



# git clone
def checkoutFilesFromGit():
    ssm = boto3.client('ssm')
    ssm_value = ssm.get_parameter(Name='GITHUB_TOKEN', WithDecryption=True)
    GITHUB_TOKEN  = ssm_value['Parameter']['Value']
    subprocess.call('rm -rf /tmp/*', shell = True)    
    subprocess.call(f"git clone https://{GITHUB_USERNAME}:{GITHUB_TOKEN}@github.com/{GITHUB_USERNAME}/{GITHUB_REPO}.git", shell = True, cwd='/tmp')


# get ami id from SSM parameter    
def get_ami_id(ssmValue):
    client = boto3.client('ssm')
    
    response = client.get_parameter(
    Name=ssmValue,
    WithDecryption=True
    )
    return (response['Parameter']['Value'])
    
    
# Execute terraform scripts for assessment
def execute(ami_id,osType):
        print("In Execution() ---",ami_id)
        dir = "/tmp/" + GITHUB_REPO + "/" + osType
        tf = Terraform(working_dir=dir,terraform_bin_path='/opt/python/lib/python3.8/site-packages/terraform',variables={"region": currentRegion, "AMI_ID": ami_id})
        tf.init()
        approve = {"auto-approve": True}
        (ret, out, err) = tf.apply(capture_output=True, skip_plan=True, **approve)
        while ret != 0:
            tf.destroy(capture_output=True, **approve)
            tf = Terraform(working_dir=dir,terraform_bin_path='/opt/python/lib/python3.8/site-packages/terraform',variables={"region": currentRegion, "AMI_ID": ami_id})
            tf.init()
            approve = {"auto-approve": True}
            (ret, out, err) = tf.apply(capture_output=True, skip_plan=True, **approve)
        stdout=tf.output()
        return stdout
    

# subscribe to SNS based event  
def subscribe_to_event(template_arn):

    # client representing
    inspector = boto3.client('inspector')
    sns = boto3.client('sns')

    # To create topic ARN using regular expression
    topic_arn = ":".join(["arn", "aws", "sns", currentRegion, account_id, SNS_TOPIC])

    # Subscribing sns with template, event based
    events = ['ASSESSMENT_RUN_COMPLETED']  # ,'FINDING_REPORTED','ASSESSMENT_RUN_STATE_CHANGED','ASSESSMENT_RUN_STARTED', ]
    for event in events:
        event_response = inspector.subscribe_to_event(resourceArn=template_arn, event=event, topicArn=topic_arn)
        
    

# creating trigger for validation phase 2 lambda 
def trigger_lambda():
    id = uuid.uuid1()
    # To create topic ARN using regular expression
    topic_arn = ":".join(["arn", "aws", "sns", currentRegion, account_id, SNS_TOPIC])
    dest_lambda_arn = ":".join(["arn", "aws", "lambda", currentRegion, account_id, "function", dest_lambda])
    
    sns = boto3.client('sns')
    
    sns.subscribe(
    TopicArn=topic_arn,
    Protocol='lambda',
    Endpoint=dest_lambda_arn
    )

    # To create lambda trigger for SNS
    lambda_client = boto3.client('lambda')

    lambda_client.add_permission(
        FunctionName=dest_lambda_arn,
        StatementId=str(id),
        Action='lambda:InvokeFunction',
        Principal='sns.amazonaws.com',
        SourceArn=topic_arn
    )
    

# Running assessment template and tagging template
def start_assessment_run(arn, ssmValue):
    client = boto3.client('inspector')
    
    # running assessment te
    response = client.start_assessment_run(
        assessmentTemplateArn=arn,
        assessmentRunName='Gold_AMI_Assessment_Run'
    )
    
    # tagging template
    client.set_tags_for_resource(
    resourceArn=arn,
    tags=[
            {
                'key': 'ami-name',
                'value': ssmValue
            },
         ]
    )

    
# SNS Notification
def snsNotify(ssmValue,statusCode):
    snsTopicArn = ":".join(["arn", "aws", "sns", currentRegion, account_id, SNS_TOPIC])
    if statusCode == 200:
        subject = "Validation Phase 1 completed successfully"
        messageBody = "Assessment run Started for AMI " + ssmValue
    elif statusCode == 400:
        subject = "Validation phase 1 did not complete successfully"
        messageBody = "Terraform execution failed"
    elif statusCode == 401:
        subject = "Validation phase 1 did not complete successfully"
        messageBody = "No such SSM parameter is available"
    elif statusCode == 402:
        subject = "Validation phase 1 did not complete successfully"
        messageBody = "No AMI Config found"    
    elif statusCode == 403:
        subject = "Validation phase 1 did not complete successfully"
        messageBody = "Couldnt retrieve S3 Object information"
    client = boto3.client('sns')
    client.publish(
            TopicArn = snsTopicArn,
            Message = messageBody,
            Subject = subject
    )
