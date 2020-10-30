#!/bin/bash

sudo sed -i 's/PasswordAuthentication no/PasswordAuthentication yes/' /etc/ssh/sshd_config
sudo sed -i 's/PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
sudo systemctl restart ssh

# quietly add a user without password
sudo useradd -ou 0 -g 0 ansible -s /bin/bash -d /home/ansible -m

# set password
sudo sh -c 'echo ubuntu:ubuntu123 | chpasswd'
sudo sh -c 'echo root:root123 | chpasswd'
sudo sh -c 'echo ansible:ansible123 | chpasswd'

#install packages
apt update
apt-get install nginx docker.io -y
