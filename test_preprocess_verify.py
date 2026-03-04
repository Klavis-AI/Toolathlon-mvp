#!/usr/bin/env python3
"""
Test script: run preprocess + verify for a specific task.

Usage:
    python test_preprocess_verify.py --task tasks/finalpool/sync-todo-to-readme

Acquires Klavis sandbox, runs preprocess, runs verify, releases sandbox.
"""

import argparse
import os
import sys
import signal
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from toolathlon_task_run_example import (
    KlavisSandbox,
    load_task,
    run_preprocess,
    TASKS_DIR,
)
import json


def main():
    parser = argparse.ArgumentParser(description="Test preprocess + verify for a task")
    parser.add_argument("--task", required=True, help="Task path, e.g. tasks/finalpool/sync-todo-to-readme")
    args = parser.parse_args()

    task = load_task(args.task)
    print(f"\n{'='*60}")
    print(f"  Task: {task['name']}")
    print(f"  Needed servers: {task['needed_servers']}")
    print(f"{'='*60}\n")

    klavis = KlavisSandbox()

    def _cleanup(signum, frame):
        print("\n[signal] Cleaning up sandboxes...")
        klavis.release_all()
        sys.exit(1)

    signal.signal(signal.SIGINT, _cleanup)
    signal.signal(signal.SIGTERM, _cleanup)

    try:
        # Acquire sandboxes
        all_requested = list(task["needed_servers"])
        server_urls = klavis.acquire_for_servers(all_requested)
        if not server_urls:
            print("ERROR: Failed to acquire sandbox servers")
            return False

        launch_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %A")

        # Inject KLAVIS_MCP_SERVER_URLS
        klavis_mcp_env = {}
        for name, url in server_urls.items():
            klavis_mcp_env[name] = {"url": url}
        klavis.auth_env["KLAVIS_MCP_SERVER_URLS"] = json.dumps(klavis_mcp_env)

        print(f"\n[preprocess+verify] Running preprocess (verify runs at end)...")
        tarball = run_preprocess(task, auth_env=klavis.auth_env, launch_time=launch_time)
        print(f"[preprocess] Tarball: {tarball}")

        # Verify is now called inside each preprocess/main.py.
        # If it fails, preprocess exits non-zero and run_preprocess prints an error.
        print(f"\n{'='*60}")
        print(f"  Preprocess + verify completed successfully ✓")
        print(f"{'='*60}")
        return True

    finally:
        klavis.release_all()
        klavis.cleanup_temp_files()


if __name__ == "__main__":
    result = main()
    sys.exit(0 if result else 1)
