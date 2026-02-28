#!/usr/bin/env bash
# Build script for Render — backend only
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt
