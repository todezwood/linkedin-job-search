#!/bin/bash
# Wrapper script for launchd daily scheduling.
# Update paths below if the project directory moves.
PROJECT_DIR="/Users/jarmarledesma/Documents/n8n/LinkedIn Job Search"
cd "$PROJECT_DIR"
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"
"$PROJECT_DIR/venv/bin/python" -m pipeline >> cron.log 2>&1
