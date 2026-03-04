"""
Verify that payable-invoice-checker preprocess completed correctly.

Checks:
  1. Snowflake database PURCHASE_INVOICE exists
  2. Table INVOICES exists and has rows
  3. Table INVOICE_PAYMENTS exists and has rows
  4. Groundtruth file invoice.jsonl was generated
"""

import os
import sys
from pathlib import Path

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..', '..'))
sys.path.insert(0, project_root)

from utils.app_specific.snowflake.client import fetch_all

DB = "PURCHASE_INVOICE"
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

    # 1. INVOICES table
    count = _count_rows("INVOICES")
    if count > 0:
        print(f"[verify] OK: INVOICES has {count} rows")
    else:
        print(f"[verify] FAIL: INVOICES table empty or missing (count={count})")
        ok = False

    # 2. INVOICE_PAYMENTS table
    count = _count_rows("INVOICE_PAYMENTS")
    if count > 0:
        print(f"[verify] OK: INVOICE_PAYMENTS has {count} rows")
    else:
        print(f"[verify] FAIL: INVOICE_PAYMENTS table empty or missing (count={count})")
        ok = False

    # 3. Groundtruth file
    gt_path = Path(current_dir).parent / "groundtruth_workspace" / "invoice.jsonl"
    if gt_path.exists():
        line_count = sum(1 for _ in gt_path.open())
        if line_count > 0:
            print(f"[verify] OK: Groundtruth invoice.jsonl has {line_count} lines")
        else:
            print(f"[verify] FAIL: Groundtruth invoice.jsonl is empty")
            ok = False
    else:
        print(f"[verify] FAIL: Groundtruth file {gt_path} not found")
        ok = False

    return ok


if __name__ == "__main__":
    success = verify()
    print(f"\n[verify] {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1)
