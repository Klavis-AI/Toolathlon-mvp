"""
Verify that email-paper-homepage preprocess completed correctly.

Checks:
  1. All 5 GitHub repos exist under the authenticated user:
     My-Homepage, optimizing-llms-contextual-reasoning, llm-adaptive-learning,
     ipsum-lorem-all-you-need, enhancing-llms
  2. Each repo has at least one commit
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
EXPECTED_REPOS = [
    "My-Homepage",
    "optimizing-llms-contextual-reasoning",
    "llm-adaptive-learning",
    "ipsum-lorem-all-you-need",
    "enhancing-llms",
]


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

    for repo_name in EXPECTED_REPOS:
        repo_full = f"{owner}/{repo_name}"

        # Check repo exists
        r = requests.get(f"{GITHUB_API}/repos/{repo_full}", headers=_headers(token), timeout=30)
        if r.status_code != 200:
            print(f"[verify] FAIL: Repo {repo_full} not found ({r.status_code})")
            ok = False
            continue

        # Check repo has commits
        r = requests.get(
            f"{GITHUB_API}/repos/{repo_full}/commits",
            headers=_headers(token),
            params={"per_page": 1},
            timeout=30,
        )
        if r.status_code == 200 and r.json():
            print(f"[verify] OK: Repo {repo_full} exists with commits")
        else:
            print(f"[verify] FAIL: Repo {repo_full} exists but has no commits ({r.status_code})")
            ok = False

    return ok


if __name__ == "__main__":
    success = verify()
    print(f"\n[verify] {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1)
