#!/bin/bash

# uncomment this line if using an image with numpy already installed from ECR
# aws ecr get-login-password --region ${AWS_REGION} | docker login --password-stdin --username AWS ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

cdk deploy --all --require-approval never
