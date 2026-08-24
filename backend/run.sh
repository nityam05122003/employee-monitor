#!/usr/bin/env bash
# Convenience launcher: activates the venv and starts the API.
#
# Deliberately NOT using --reload: this app holds real devices (webcam/CCTV)
# and long-running background threads (camera capture + recognition loop).
# uvicorn's reloader has repeatedly left orphaned worker processes behind
# when it tries to restart on a file change - those orphans keep running
# with stale config and silently write bad data into the shared SQLite file.
# After code changes, stop this script and re-run it instead of relying on
# autoreload.
set -e
cd "$(dirname "$0")"
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8003
