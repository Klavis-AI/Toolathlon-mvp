"""
Verify that dataset-license-issue preprocess completed correctly.

Checks:
  1. GitHub repo 'Annoy-DataSync' exists under the authenticated user
  2. The repo has commits (is not empty)
  3. An issue titled 'License info. needed' exists on the repo
  4. The groundtruth task_state.json was written with expected fields
"""

import json
import os
import sys
from pathlib import Path

import requests

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..', '..'))
sys.path.insert(0, project_root)

from configs.token_key_session import all_token_key_session

GITHUB_API = "https://api.github.com"
REPO_NAME = "Annoy-DataSync"


def _headers(token: str) -> dict:
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }


def verify() -> bool:
    token = all_token_key_session.github_token
    if not token:
        print("[verify] ERROR: KLAVIS_GITHUB_TOKEN is not set")
        return False

    # Get authenticated user
    r = requests.get(f"{GITHUB_API}/user", headers=_headers(token), timeout=30)
    if r.status_code != 200:
        print(f"[verify] ERROR: Cannot fetch GitHub user: {r.status_code}")
        return False
    owner = r.json()["login"]
    repo_full = f"{owner}/{REPO_NAME}"

    ok = True

    # 1. Check repo exists
    r = requests.get(f"{GITHUB_API}/repos/{repo_full}", headers=_headers(token), timeout=30)
    if r.status_code == 200:
        print(f"[verify] OK: Repo {repo_full} exists")
    else:
        print(f"[verify] FAIL: Repo {repo_full} not found ({r.status_code})")
        ok = False

    # 2. Check repo has commits
    r = requests.get(
        f"{GITHUB_API}/repos/{repo_full}/commits",
        headers=_headers(token),
        params={"per_page": 1},
        timeout=30,
    )
    if r.status_code == 200 and r.json():
        print(f"[verify] OK: Repo has commits (latest: {r.json()[0]['sha'][:8]})")
    else:
        print(f"[verify] FAIL: Repo has no commits or error ({r.status_code})")
        ok = False

    # 3. Check issue exists
    r = requests.get(
        f"{GITHUB_API}/repos/{repo_full}/issues",
        headers=_headers(token),
        params={"state": "open", "per_page": 100},
        timeout=30,
    )
    if r.status_code == 200:
        issues = r.json()
        matching = [i for i in issues if i["title"] == "License info. needed"]
        if matching:
            print(f"[verify] OK: Issue 'License info. needed' found (#{matching[0]['number']})")
        else:
            print(f"[verify] FAIL: Issue 'License info. needed' not found among {len(issues)} open issues")
            ok = False
    else:
        print(f"[verify] FAIL: Cannot list issues ({r.status_code})")
        ok = False

    # 4. Check groundtruth task_state.json
    gt_path = Path(current_dir).parent / "groundtruth_workspace" / "task_state.json"
    if gt_path.exists():
        state = json.loads(gt_path.read_text())
        required_keys = ["github_repo", "issue_number", "hf_datasets", "latest_commit_hash"]
        missing = [k for k in required_keys if k not in state]
        if missing:
            print(f"[verify] FAIL: task_state.json missing keys: {missing}")
            ok = False
        else:
            print(f"[verify] OK: task_state.json has all required fields")
    else:
        print(f"[verify] FAIL: {gt_path} does not exist")
        ok = False

    return ok


if __name__ == "__main__":
    success = verify()
    print(f"\n[verify] {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1)
