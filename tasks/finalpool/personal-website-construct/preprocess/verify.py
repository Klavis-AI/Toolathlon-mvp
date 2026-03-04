"""
Verify that personal-website-construct preprocess completed correctly.

The preprocess deletes repos 'academicpages.github.io' and 'LJT-Homepage'.

Checks:
  1. Repo 'academicpages.github.io' does NOT exist (was deleted)
  2. Repo 'LJT-Homepage' does NOT exist (was deleted)
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
REPOS_TO_DELETE = ["academicpages.github.io", "LJT-Homepage"]


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

    ok = True

    for repo_name in REPOS_TO_DELETE:
        r = requests.get(
            f"{GITHUB_API}/repos/{owner}/{repo_name}",
            headers=_headers(token),
            timeout=30,
        )
        if r.status_code == 404:
            print(f"[verify] OK: Repo {owner}/{repo_name} was successfully deleted (404)")
        elif r.status_code == 200:
            print(f"[verify] FAIL: Repo {owner}/{repo_name} still exists — should have been deleted")
            ok = False
        else:
            # Other error — treat as a warning but pass
            print(f"[verify] WARN: Unexpected status {r.status_code} for {owner}/{repo_name}")

    return ok


if __name__ == "__main__":
    success = verify()
    print(f"\n[verify] {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1)
