# multi-ami-multi-region-2
This version of build-phase custom-ami comes with some changes to the existing parameter store variables,events and lambda functions.
Only config files(linux/windows) are stored in s3 bucket. 

For Linux AMIs,
install.sh ,common-packer-linux.json and terraform files of inspect.tf, output.tf and var.tf files are stored in github.

For Windows AMIs,
bootstrap_win.txt , sample_script.ps1, common-packer-windows.json and terraform files of inspect.tf, output.tf and var.tf files are stored in github.

Parameter store changes:
There will be 2 main base-image SSM parameters where the initial trigger is based on:
- linux-base-image
- windows-base-image

When there is any new linux based image, provided by the security team to linux-base-image SSM parameter, Only linux based applications will be part of build pipeline. which means only config files for linux customization are updated by build-phase-1.py lambda.

When there is any new windows image in windows-base-image SSM parameter, Only windows based config files are updated by build-phase-1.py lambda.

In S3 bucket 'demos-s3-lambda11' there are 2 folders:
linux-base-image , windows-base-image
Folder structure:
- linux-base-image
   - app111-config.json
   - app112-config.json
- windows-base-image
   - app113-config.json
   
CloudWatch event that triggers the build-phase-1.py lambda whenever there is a change in base image now consists of 2 SSM Parameters

{
  "source": [
    "aws.ssm"
  ],
  "detail-type": [
    "Parameter Store Change"
  ],
  "detail": {
    "name": [
      "linux-base-image",
      "windows-base-image"
    ],
    "operation": [
      "Create",
      "Update"
    ]
  }
}

S3 event remains the same as earlier

SNS topic is added to build-lambda.py to notify the success or failure of the build phase. SNS Arn is hardcoded.

In the github the naming convention of install.sh changes as below
- app111.install.sh
- app112.install.sh
- app113.install.sh

common-packer.json remains the same. 

build-lambda.py will have an additional git layer along with existing packer layer.
This layer requires 3 environment variables on build-lambda.py and 1 variable in parameter store.
Firstly we have to create a personal access token.
You need to visit the 'Settings' of the user account and under 'Developer settings' you will find 'Personal access tokens'
Generate a token and create a parameter in the SSM Parameter store with the name GITHUB_TOKEN and add the token as value.

Layers folder contain all layer zips.

GIT layer arn to be used in those lambdas where below GITHUB environment details are used:
arn:aws:lambda:us-east-2:553035198032:layer:git-lambda2:8

Create 3 environment variables Lambda UI whenever GITHUB repo content is required.
- GITHUB_EMAIL : <your github email>
- GITHUB_REPO : <Repository that you want to access in the lambda>
- GITHUB_USERNAME : <your github user name>

Sharing the current repo github details for reference.

SNS topic to be created as a pre-requisite using sns.tf and intended recipients to be subscribed.



Prerequisites for build-phase-1 lambda:

NOTE:
The function build-phase-1.py needs to be setup as a separate lambda in AWS console.

1. Cloudwatch Event Trigger for initiating build-phase-1 lambda to be terraformed w.r.t to any update to the SSM paramater create or update event.(As mentioned above)

2. Role/policies for lambda:
S3, Lambda, cloudwatchevents, SSM

3. Trigger based on update of config files in S3 bucket to be terraformed. (Build phase 1 triggering Build phase 2)

Environment variables used:-
- BUCKET_NAME : <S3 bucket name>
- SNS_TOPIC : <SNS topic name created from sns.tf>



Pre-requisites for build-phase-2 lambda:

NOTE:
The function build-phase-2.py needs to be setup as a separate lambda in AWS console.

1. Python-packerpy layer:
python.zip to be placed as layer

2. Role/policies for lambda:
S3, EC2, Lambda, cloudwatchevents, SSM

3. Trigger based on create/update of SSM parameter to be terraformed. (Build phase 2 triggering validation phase 1)

4. Basic settings to updated with Timeout = 15 min and Memory = 256 MB

Environment variables used:- 
- GITHUB_EMAIL : <your github email>
- GITHUB_REPO : <Repository that you want to access in the lambda>
- GITHUB_USERNAME : <your github user name>
- SNS_TOPIC : <SNS topic name created from sns.tf>


Pre-requisites for Validation-phase-1 lambda:

NOTE:
The function validation-phase-1.py needs to be setup as a separate lambda in AWS console.

1. Python-Terraform layer:
terraform-pkg.zip to be placed as layer

2. Lambda should have basic settings of Memory = 256 MB and Timeout = 15 min(max. limit)

3. SNS Trigger based on assessment run completed to be terraformed. (Validation phase 1 triggering validation phase 2)

4. Role/policies for lambda:
EC2, Lambda, Inspector, cloudwatchevents, SSM

Environment variables used:- 
- GITHUB_EMAIL : <your github email>
- GITHUB_REPO : <Repository that you want to access in the lambda>
- GITHUB_USERNAME : <your github user name>
- SNS_TOPIC : <SNS topic name created from sns.tf>
 
  
Pre-requisites for Validation-phase-2 lambda:

NOTE:
The function validation-phase-2.py needs to be setup as a separate lambda in AWS console.

1. Role/policies for lambda:
EC2, Lambda, Inspector, cloudwatchevents, SSM

2. Trigger based on create/update of SSM parameter to be terraformed. (Validation phase 2 triggering distribution phase)

Environment variables used:-
- BUCKET_NAME : <S3 bucket name>
- SNS_TOPIC : <SNS topic name created from sns.tf>


Pre-requisite for distribution phase lambda:

NOTE:
The function distribution-phase.py needs to be setup as a separate lambda in AWS console.
All policy jsons under folder distribution-phase-json.

1. Account IDs to be modified as per AWS account used under "distributions" section in respective .jsons in S3 bucket.

2. dist-ami-policy.json content to be added as a policy to the distribution-phase lambda role.

3. crossAccountAMI-Role role to be created in destination account.

4. crossAccountAMI-Role.json to be added as a policy to crossAccountAMI-Role role in destination account.

5. trust_policy.json content to be added to trust relationship in crossAccountAMI-Role role.

3. Role/policies for lambda:
Lambda, cloudwatchevents, SSM, IAM, STS, EC2

Environment variables used:-
- BUCKET_NAME : <S3 bucket name>
- SNS_TOPIC : <SNS topic name created from sns.tf>