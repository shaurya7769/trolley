#!/bin/bash

set -e

echo "Updating system..."

sudo apt update

echo "Installing system dependencies..."

sudo apt install -y 
python3 
python3-pip 
python3-pyqt5 
python3-spidev 
python3-serial 
iputils-ping 
net-tools

echo "Installing Python dependencies..."

pip3 install -r requirements.txt

echo "Setup complete."
