#!/bin/bash
echo "Installing aws cdk (npm)"
npm install -g aws-cdk
# Note: zsh users need to use ""
echo "Installing python packages (pip)"
pip install -e ".[deploy]"

# echo "Setting AWS_ACCOUNT_ID and AWS_REGION"
# # Bootstrap the AWS accont
# export AWS_ACCOUNT_ID=$(aws sts get-caller-identity | jq .Account -r)
# export AWS_REGION=$(aws configure get region)

echo "CDK bootstrapping AWS_ACCOUNT_ID and AWS_REGION"
cdk bootstrap aws://$AWS_ACCOUNT_ID/$AWS_REGION --all
