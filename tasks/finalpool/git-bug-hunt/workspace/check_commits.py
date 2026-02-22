#!/usr/bin/env python3
import subprocess
import sys

commits = [
    ('9d25e171bbfcd61d5c2b73ffd284b6fde1318d71', 'motigrez', 'grdyx2138039185@126.com', 'clone: from https://github.com/ElliottYan/LUFFY'),
    ('c37a78c32787eb1dcbd9c0df231ecf1d6a3e1f47', 'Sarah Johnson', 'sarah.johnson@team.ai', 'optimize training configuration with data caching'),
    ('737c3636da8d3816b5a1da3ab899b0066d19c50b', 'Michael Zhang', 'mzhang@dataops.io', 'improve data processing with logging and progress tracking'),
    ('cdd6234342b147880f5d86c55dad6c1fbe222bfe', 'Patrick Cruz', 'patrick_cruz@mcp.com', 'add experimental caching layer optimization'),
    ('974124e210ea26f75ec8b5ae1e5516a460bf003d', 'Alex Rodriguez', 'alex.rodriguez@eval.com', 'fix evaluation script error handling and logging'),
    ('1937b6addce50565c710e6543d5531aa3ee70a4b', 'Jennifer Lee', 'jlee@modelops.dev', 'update model configuration defaults')
]

target_file = 'luffy/verl/verl/mix_src/mix_core_alg.py'
search_term = 'remove_caching_layer'

for commit_hash, author, email, message in commits:
    cmd = ['git', 'show', f'{commit_hash}:{target_file}']
    result = subprocess.run(cmd, capture_output=True, text=True, cwd='/data/LUFFY')
    
    if result.returncode == 0:
        if search_term in result.stdout:
            print(f"FOUND in commit: {commit_hash}")
            print(f"Author: {author}")
            print(f"Email: {email}")
            print(f"Message: {message}")
            print()
        else:
            print(f"NOT FOUND in commit: {commit_hash[:8]}")
    else:
        print(f"File doesn't exist in commit: {commit_hash[:8]}")
