#!/usr/bin/env bash
# Build script for Render — installs Python deps + builds React frontend
set -o errexit  # exit on error

# 1. Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 2. Build the React frontend
cd frontend
npm install
npm run build
cd ..
