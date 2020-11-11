provider "aws" {
  region = var.region
}

# provider "aws" {
#   alias  = "west"
#   region = "us-west-1"
# }

resource "aws_sns_topic" "assesment_complete_trigger" {
  name         = "assesment_complete_trigger"
  display_name = "assesment_complete_trigger"
  policy = <<EOF
    {
    "Version": "2008-10-17",
    "Id": "__default_policy_ID",
    "Statement": [
      {
        "Sid": "__default_statement_ID",
        "Effect": "Allow",
        "Principal": {
          "AWS": "*"
        },
        "Action": [
          "SNS:GetTopicAttributes",
          "SNS:SetTopicAttributes",
          "SNS:AddPermission",
          "SNS:RemovePermission",
          "SNS:DeleteTopic",
          "SNS:Subscribe",
          "SNS:ListSubscriptionsByTopic",
          "SNS:Publish",
          "SNS:Receive"
        ],
        "Resource": "*",
        "Condition": {
          "StringEquals": {
            "AWS:SourceOwner": "585152918139"
          }
        }
      },
      {
        "Sid": "inspector-sns-publish-statement",
        "Effect": "Allow",
        "Principal": {
          "Service": "inspector.amazonaws.com"
        },
        "Action": "SNS:Publish",
        "Resource": "arn:aws:sns:*"
      }
    ]
  }
  EOF
}

# resource "aws_sns_topic" "inspector_finding_delivery" {
#   name         = "inspector_finding_delivery"
#   display_name = "inspector_finding_delivery"
#   policy = <<EOF
#     {
#     "Version": "2008-10-17",
#     "Id": "__default_policy_ID",
#     "Statement": [
#       {
#         "Sid": "__default_statement_ID",
#         "Effect": "Allow",
#         "Principal": {
#           "AWS": "*"
#         },
#         "Action": [
#           "SNS:GetTopicAttributes",
#           "SNS:SetTopicAttributes",
#           "SNS:AddPermission",
#           "SNS:RemovePermission",
#           "SNS:DeleteTopic",
#           "SNS:Subscribe",
#           "SNS:ListSubscriptionsByTopic",
#           "SNS:Publish",
#           "SNS:Receive"
#         ],
#         "Resource": "arn:aws:lambda:us-east-2:585152918139:function:validation-2",
#         "Condition": {
#           "StringEquals": {
#             "AWS:SourceOwner": "585152918139"
#           }
#         }
#       },
#       {
#         "Sid": "inspector-sns-publish-statement",
#         "Effect": "Allow",
#         "Principal": {
#           "Service": "inspector.amazonaws.com"
#         },
#         "Action": "SNS:Publish",
#         "Resource": "arn:aws:sns:*"
#       }
#     ]
#   }
#   EOF
# }
