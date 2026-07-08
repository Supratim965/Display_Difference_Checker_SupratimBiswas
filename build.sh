#!/usr/bin/env bash
# exit on error
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

# Install Chromium inside the project directory so it persists on Render
# (Render's cache dir gets wiped between build and runtime containers)
export PLAYWRIGHT_BROWSERS_PATH=/opt/render/project/src/playwright-browsers
playwright install chromium --with-deps
