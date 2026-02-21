"""
Minimal token_key_session for Toolathlon-mvp.
Reads tokens from environment variables set by the Klavis sandbox.
"""
import os

from addict import Dict

all_token_key_session = Dict(
    github_token=os.environ.get("KLAVIS_GITHUB_TOKEN", ""),
    huggingface_token=os.environ.get("KLAVIS_HUGGINGFACE_TOKEN", ""),
)
