# multi-ami-multi-region-2
This version of build-phase custom-ami comes with some changes to the existing parameter store variables,events and lambda functions.
Only config files(linux/windows) are stored in s3 bucket. Install.sh and Common-packer.json files are stored in github.

Parameter store changes:
There will be 2 main base-image SSM parameters where the initial trigger is based on:
- linux-base-image
- windows-base-image

When there is any new linux based image is provided by the security team to linux-base-image SSM parameter, Only linux based applications
will be part of build pipeline. which means only config files for linux customization are updated by trigger-multiplier.py lambda.

When there is any new windows image in windows-base-image SSM parameter, Only windows based config files are updated by trigger-multiplier.py.

In S3 our bucket 'demos-s3-lambda' there will be 2 folders:
linux-base-image , windows-base-image
Folder structure:
- linux-base-image
   - app111-config.json
   - app112-config.json
- windows-base-image
   - app113-config.json
   
CloudWatch event that triggers the trigger-multiplier.py whenever there is a change in base image now consists of 2 SSM Parameters

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

Create 3 environment variables on the build-lambda.py UI.
- GITHUB_EMAIL : <your github email>
- GITHUB_REPO : <Repository that you want to access in the lambda>
- GITHUB_USERNAME : <your github user name>
 
  
