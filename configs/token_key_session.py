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
)
