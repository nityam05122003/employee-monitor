#!/usr/bin/env python3
"""
Enroll an employee from the terminal, without needing the React frontend
(which doesn't exist until Phase 6).

This is a thin client - the actual webcam capture happens in the backend
(POST /enroll), since the backend process is the one holding the camera open.
So the server MUST already be running (./run.sh) before you use this script.

Usage:
    .venv/bin/python scripts/enroll_cli.py
"""
import json
import sys
import urllib.error
import urllib.request

API_BASE = "http://localhost:8003"


def main():
    print("=== Employee enrollment ===")
    print(f"(backend must already be running at {API_BASE} - start it with ./run.sh)\n")

    employee_code = input("Employee code (e.g. EMP001): ").strip()
    name = input("Full name: ").strip()
    if not employee_code or not name:
        print("Both employee code and name are required.")
        sys.exit(1)

    input("\nLook directly at the webcam, then press Enter to start capturing...")
    print("Capturing... hold still and look at the camera for a few seconds.")

    body = json.dumps({"employee_code": employee_code, "name": name}).encode()
    request = urllib.request.Request(
        f"{API_BASE}/enroll",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode()
        print(f"\nEnrollment failed ({e.code}): {detail}")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"\nCould not reach the backend at {API_BASE}: {e}\nIs it running? (./run.sh)")
        sys.exit(1)

    print(
        f"\nEnrolled '{result['name']}' ({result['employee_code']}): "
        f"{result['embeddings_captured']}/{result['shots_attempted']} face shots captured."
    )
    if result["embeddings_captured"] < result["shots_attempted"]:
        print("Some shots missed a face - that's fine as long as at least one was captured.")


if __name__ == "__main__":
    main()
