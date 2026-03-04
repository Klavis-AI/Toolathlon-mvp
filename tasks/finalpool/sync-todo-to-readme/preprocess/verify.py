"""
Verify that sync-todo-to-readme preprocess completed correctly.

Checks:
  1. GitHub repo 'LUFFY' exists under the authenticated user
  2. The repo has commits (is not empty)
  3. The repo contains a README.md file
"""

import os
import sys

import requests

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..', '..'))
sys.path.insert(0, project_root)

from configs.token_key_session import all_token_key_session

GITHUB_API = "https://api.github.com"
REPO_NAME = "LUFFY"


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

    # 3. Check README.md exists
    r = requests.get(
        f"{GITHUB_API}/repos/{repo_full}/contents/README.md",
        headers=_headers(token),
        timeout=30,
    )
    if r.status_code == 200:
        print(f"[verify] OK: README.md exists in repo")
    else:
        print(f"[verify] FAIL: README.md not found in repo ({r.status_code})")
        ok = False

    return ok


if __name__ == "__main__":
    success = verify()
    print(f"\n[verify] {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1)
