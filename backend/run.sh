#!/usr/bin/env bash
# Convenience launcher: activates the venv and starts the API with autoreload.
set -e
cd "$(dirname "$0")"
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8003
