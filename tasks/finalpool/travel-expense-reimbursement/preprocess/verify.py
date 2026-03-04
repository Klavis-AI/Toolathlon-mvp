"""
Verify that travel-expense-reimbursement preprocess completed correctly.

Checks:
  1. Snowflake database TRAVEL_EXPENSE_REIMBURSEMENT exists
  2. Table ENTERPRISE_CONTACTS exists and has rows
  3. Table "2024Q4REIMBURSEMENT" exists (may be empty — preprocess skips insertion)
  4. Groundtruth files (expense_claims.json, enterprise_contacts.json) exist
"""

import os
import sys
from pathlib import Path

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..', '..'))
sys.path.insert(0, project_root)

from utils.app_specific.snowflake.client import fetch_all

DB = "TRAVEL_EXPENSE_REIMBURSEMENT"
SCHEMA = "PUBLIC"


def _count_rows(table: str) -> int:
    """Return row count for a fully-qualified table, or -1 on error."""
    try:
        rows = fetch_all(f"SELECT COUNT(*) FROM {DB}.{SCHEMA}.{table}")
        return rows[0][0]
    except Exception as e:
        print(f"[verify] ERROR querying {table}: {e}")
        return -1


def verify() -> bool:
    ok = True

    # 1. ENTERPRISE_CONTACTS table
    count = _count_rows("ENTERPRISE_CONTACTS")
    if count > 0:
        print(f"[verify] OK: ENTERPRISE_CONTACTS has {count} rows")
    else:
        print(f"[verify] FAIL: ENTERPRISE_CONTACTS table empty or missing (count={count})")
        ok = False

    # 2. "2024Q4REIMBURSEMENT" table — should exist (created) even if empty
    try:
        rows = fetch_all(f'SELECT COUNT(*) FROM {DB}.{SCHEMA}."2024Q4REIMBURSEMENT"')
        count = rows[0][0]
        print(f"[verify] OK: \"2024Q4REIMBURSEMENT\" table exists ({count} rows)")
    except Exception as e:
        print(f"[verify] FAIL: \"2024Q4REIMBURSEMENT\" table missing or error: {e}")
        ok = False

    # 3. Groundtruth files
    gt_dir = Path(current_dir).parent / "groundtruth_workspace"

    for filename in ["expense_claims.json", "enterprise_contacts.json"]:
        gt_path = gt_dir / filename
        if gt_path.exists():
            size = gt_path.stat().st_size
            if size > 10:
                print(f"[verify] OK: {filename} exists ({size} bytes)")
            else:
                print(f"[verify] FAIL: {filename} exists but is too small ({size} bytes)")
                ok = False
        else:
            print(f"[verify] FAIL: {gt_path} not found")
            ok = False

    return ok


if __name__ == "__main__":
    success = verify()
    print(f"\n[verify] {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1)
