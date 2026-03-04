"""
Verify that sla-timeout-monitor preprocess completed correctly.

Checks:
  1. Snowflake database SLA_MONITOR exists
  2. Table USERS exists and has rows (expected: 15 sample users)
  3. Table SUPPORT_TICKETS exists and has rows (expected: 15 tickets, one per user)
  4. Users have the expected service levels (basic, pro, max)
  5. Groundtruth file sla_monitoring.jsonl was generated
"""

import os
import sys
from pathlib import Path

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..', '..'))
sys.path.insert(0, project_root)

from utils.app_specific.snowflake.client import fetch_all, fetch_all_dict


def verify() -> bool:
    ok = True

    # 1. Check database exists by querying a table
    try:
        rows = fetch_all("SELECT COUNT(*) FROM SLA_MONITOR.PUBLIC.USERS")
        user_count = rows[0][0]
        if user_count > 0:
            print(f"[verify] OK: SLA_MONITOR.PUBLIC.USERS has {user_count} rows")
        else:
            print(f"[verify] FAIL: USERS table is empty")
            ok = False
    except Exception as e:
        print(f"[verify] FAIL: Cannot query USERS table: {e}")
        ok = False

    # 2. Check SUPPORT_TICKETS table
    try:
        rows = fetch_all("SELECT COUNT(*) FROM SLA_MONITOR.PUBLIC.SUPPORT_TICKETS")
        ticket_count = rows[0][0]
        if ticket_count > 0:
            print(f"[verify] OK: SLA_MONITOR.PUBLIC.SUPPORT_TICKETS has {ticket_count} rows")
        else:
            print(f"[verify] FAIL: SUPPORT_TICKETS table is empty")
            ok = False
    except Exception as e:
        print(f"[verify] FAIL: Cannot query SUPPORT_TICKETS table: {e}")
        ok = False

    # 3. Check service levels distribution
    try:
        rows = fetch_all_dict(
            "SELECT SERVICE_LEVEL, COUNT(*) AS CNT "
            "FROM SLA_MONITOR.PUBLIC.USERS "
            "GROUP BY SERVICE_LEVEL ORDER BY SERVICE_LEVEL"
        )
        levels = {r["SERVICE_LEVEL"]: r["CNT"] for r in rows}
        expected_levels = {"basic", "pro", "max"}
        if expected_levels.issubset(levels.keys()):
            print(f"[verify] OK: Service levels present: {dict(levels)}")
        else:
            missing = expected_levels - set(levels.keys())
            print(f"[verify] FAIL: Missing service levels: {missing}")
            ok = False
    except Exception as e:
        print(f"[verify] FAIL: Cannot query service level distribution: {e}")
        ok = False

    # 4. Check groundtruth file
    gt_path = Path(current_dir).parent / "groundtruth_workspace" / "sla_monitoring.jsonl"
    if gt_path.exists():
        line_count = sum(1 for _ in gt_path.open())
        if line_count > 0:
            print(f"[verify] OK: Groundtruth file has {line_count} lines")
        else:
            print(f"[verify] FAIL: Groundtruth file is empty")
            ok = False
    else:
        print(f"[verify] FAIL: Groundtruth file {gt_path} not found")
        ok = False

    return ok


if __name__ == "__main__":
    success = verify()
    print(f"\n[verify] {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1)
