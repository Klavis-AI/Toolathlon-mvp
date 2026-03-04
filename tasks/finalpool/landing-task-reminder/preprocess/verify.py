"""
Verify that landing-task-reminder preprocess completed correctly.

Checks:
  1. Snowflake database LANDING_TASK_REMINDER exists
  2. Table EMPLOYEE has rows
  3. Table EMPLOYEE_LANDING has rows
  4. Table PUBLIC_TASKS has rows
  5. At least one GROUP_TASKS_* table (BACKEND, FRONTEND, TESTING, DATA) has rows
"""

import os
import sys

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..', '..'))
sys.path.insert(0, project_root)

from utils.app_specific.snowflake.client import fetch_all

DB = "LANDING_TASK_REMINDER"
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

    # 1. EMPLOYEE table
    count = _count_rows("EMPLOYEE")
    if count > 0:
        print(f"[verify] OK: EMPLOYEE has {count} rows")
    else:
        print(f"[verify] FAIL: EMPLOYEE table empty or missing (count={count})")
        ok = False

    # 2. EMPLOYEE_LANDING table
    count = _count_rows("EMPLOYEE_LANDING")
    if count > 0:
        print(f"[verify] OK: EMPLOYEE_LANDING has {count} rows")
    else:
        print(f"[verify] FAIL: EMPLOYEE_LANDING table empty or missing (count={count})")
        ok = False

    # 3. PUBLIC_TASKS table
    count = _count_rows("PUBLIC_TASKS")
    if count > 0:
        print(f"[verify] OK: PUBLIC_TASKS has {count} rows")
    else:
        print(f"[verify] FAIL: PUBLIC_TASKS table empty or missing (count={count})")
        ok = False

    # 4. GROUP_TASKS tables
    group_tables = ["GROUP_TASKS_BACKEND", "GROUP_TASKS_FRONTEND", "GROUP_TASKS_TESTING", "GROUP_TASKS_DATA"]
    any_group_has_rows = False
    for table in group_tables:
        count = _count_rows(table)
        if count > 0:
            print(f"[verify] OK: {table} has {count} rows")
            any_group_has_rows = True
        elif count == 0:
            print(f"[verify] INFO: {table} exists but has 0 rows (may be expected for new employees)")
        else:
            print(f"[verify] FAIL: {table} missing or error")
            ok = False

    if not any_group_has_rows:
        print(f"[verify] FAIL: None of the GROUP_TASKS_* tables have any rows")
        ok = False

    return ok


if __name__ == "__main__":
    success = verify()
    print(f"\n[verify] {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1)
