#!/usr/bin/env bash
# exit on error
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

# Install Chromium inside the project directory so it persists on Render
# Note: --with-deps requires root which is not available on Render free tier
# Render's base Ubuntu image already has the required Chromium OS libraries
export PLAYWRIGHT_BROWSERS_PATH=/opt/render/project/src/playwright-browsers
playwright install chromium
