provider "aws" {
  region = var.region
}

# data "rule_packages" "us-east-2" {
#   rules_package_arns = [
#     "arn:aws:inspector:us-east-2:646659390643:rulespackage/0-JnA8Zp85",
#     "arn:aws:inspector:us-east-2:646659390643:rulespackage/0-cE4kTR30"
#   ]
# }

# data "rule_packages" "us-west-1" {
#   rules_package_arns = [
#     "arn:aws:inspector:us-west-1:166987590008:rulespackage/0-TKgzoVOa",
#     "arn:aws:inspector:us-west-1:166987590008:rulespackage/0-TxmXimXF"
#   ]
# }

data "aws_inspector_rules_packages" "rules" {}

resource "random_id" "id"{
  byte_length = 8
}

resource "aws_instance" "inspector-instance" {
  ami = var.AMI_ID
  instance_type = "t3.small"
  security_groups = ["${aws_security_group.sample_sg.name}"]
  user_data = file("bootstrap_win.txt")
  tags = {
    Name = "InspectInstances-${random_id.id.hex}"
  }
  depends_on = [aws_inspector_resource_group.bar]

}

resource "aws_security_group" "sample_sg" {
  name = "Allow WINRM-${random_id.id.hex}"
  ingress {
    from_port = 5985
    to_port = 5985
    protocol = "TCP"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

}

resource "aws_inspector_resource_group" "bar" {
  tags = {
    Name = "InspectInstances-${random_id.id.hex}"
  }
}

resource "aws_inspector_assessment_target" "myinspect" {
  name = "inspector-instance-assessment-${random_id.id.hex}"
  resource_group_arn = aws_inspector_resource_group.bar.arn
}

resource "aws_inspector_assessment_template" "bar-template" {
  name       = "bar-template-${random_id.id.hex}"
  target_arn = aws_inspector_assessment_target.myinspect.arn
  duration   = 180

  rules_package_arns = data.aws_inspector_rules_packages.rules.arns
}

    # "arn:aws:inspector:us-east-2:646659390643:rulespackage/0-JnA8Zp85",
    # "arn:aws:inspector:us-east-2:646659390643:rulespackage/0-m8r61nnh",
    # "arn:aws:inspector:us-east-2:646659390643:rulespackage/0-cE4kTR30",
    # "arn:aws:inspector:us-east-2:646659390643:rulespackage/0-AxKmMHPX",

resource "null_resource" "example1" {
  provisioner "remote-exec" {
    connection {
      type = "winrm"
      user = "Administrator"
      password = "SuperS3cr3t!!!!"
      host = aws_instance.inspector-instance.public_ip
    }
    inline = [
      "powershell (new-object System.Net.WebClient).DownloadFile('https://inspector-agent.amazonaws.com/windows/installer/latest/AWSAgentInstall.exe','C:\\Users\\Administrator\\AWSAgentInstall.exe')",
      "AWSAgentInstall.exe /q install USEPROXY=1"
    ]
  }
  depends_on = [aws_instance.inspector-instance]
}

# inline = [
#       "(new-object System.Net.WebClient).DownloadFile('https://inspector-agent.amazonaws.com/windows/installer/latest/AWSAgentInstall.exe','C:UsersAdministratorDesktopAWSAgentInstall.exe')",
#       "AWSAgentInstall.exe install USEPROXY=1"
#     ]


# resource "null_resource" "example1" {
#   provisioner "remote-exec" {
#     connection {
#       type = "ssh"
#       user = "ansible"
#       password = "ansible123"
#       host = aws_instance.inspector-instance.public_ip
#     }
#     inline = [
#       "wget https://d1wk0tztpsntt1.cloudfront.net/linux/latest/install -P /tmp/",
#       "sudo bash /tmp/install",
#       "sudo systemctl start awsagent"
#     ]
#   }
#   depends_on = [aws_instance.inspector-instance]
# }
