#!/bin/bash
set -e

# ===========================================
# OmniDigest Docker Entrypoint
# 
# Run first-launch bootstrap, then start the application.
# The bootstrap script is idempotent — safe to run on every container start.
# ===========================================

echo "============================================"
echo "  OmniDigest Entrypoint"
echo "  $(date)"
echo "============================================"

python /app/src/bootstrap.py

echo ""
echo "Starting application..."

exec uvicorn src.main:app --host 0.0.0.0 --port 8080
