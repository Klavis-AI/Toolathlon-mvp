"""
Minimal token_key_session for Toolathlon-mvp.
Reads tokens from environment variables set by the Klavis sandbox.

NOTE: Some tasks have their own task-level token_key_session.py that takes
precedence over this file (e.g. woocommerce-related tasks under finalpool/).
The preprocess scripts import `from token_key_session import all_token_key_session`
and Python resolves it to the task directory first. Make sure those task-level
files also use os.environ.get() so they pick up Klavis-injected credentials.
"""
import os

from addict import Dict

all_token_key_session = Dict(
    github_token=os.environ.get("KLAVIS_GITHUB_TOKEN", ""),
    huggingface_token=os.environ.get("KLAVIS_HUGGINGFACE_TOKEN", ""),

    notion_integration_key=os.environ.get("KLAVIS_NOTION_INTEGRATION_KEY", ""),
    notion_integration_key_eval=os.environ.get("KLAVIS_NOTION_INTEGRATION_KEY_EVAL", ""),
    source_notion_page_url=os.environ.get("KLAVIS_SOURCE_NOTION_PAGE_URL", ""),
    eval_notion_page_url=os.environ.get("KLAVIS_EVAL_NOTION_PAGE_URL", ""),

    snowflake_account=os.environ.get("KLAVIS_SNOWFLAKE_ACCOUNT", ""),
    snowflake_warehouse=os.environ.get("KLAVIS_SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
    snowflake_role=os.environ.get("KLAVIS_SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
    snowflake_user=os.environ.get("KLAVIS_SNOWFLAKE_USER", ""),
    snowflake_private_key_path=os.environ.get("KLAVIS_SNOWFLAKE_PRIVATE_KEY_PATH", ""),
    snowflake_database=os.environ.get("KLAVIS_SNOWFLAKE_DATABASE", "SNOWFLAKE"),
    snowflake_schema=os.environ.get("KLAVIS_SNOWFLAKE_SCHEMA", "PUBLIC"),
    snowflake_op_allowed_databases="null",
)
