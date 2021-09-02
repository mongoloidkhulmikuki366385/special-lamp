#!/bin/bash
echo "Installing aws cdk (npm)"
npm install -g aws-cdk
# Note: zsh users need to use ""
echo "Installing python packages (pip)"
pip install -e ".[deploy]"
