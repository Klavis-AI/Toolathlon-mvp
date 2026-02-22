#!/usr/bin/env python3
import subprocess
import os

os.chdir('/data/LUFFY')

# Get all commits from git log
commits = [
    '9d25e171bbfcd61d5c2b73ffd284b6fde1318d71',
    'c37a78c32787eb1dcbd9c0df231ecf1d6a3e1f47',
    '737c3636da8d3816b5a1da3ab899b0066d19c50b',
    'cdd6234342b147880f5d86c55dad6c1fbe222bfe',
    '974124e210ea26f75ec8b5ae1e5516a460bf003d',
    '1937b6addce50565c710e6543d5531aa3ee70a4b'
]

target_file = 'luffy/verl/verl/mix_src/mix_core_alg.py'
search_term = 'remove_caching_layer'

print("Searching for first commit introducing 'remove_caching_layer'...")
print()

for commit in commits:
    # Try to get the file content at this commit
    try:
        result = subprocess.run(
            ['python', '-c', f'''
import subprocess
import sys
result = subprocess.run(["git", "show", "{commit}:{target_file}"], 
                       capture_output=True, text=True, cwd="/data/LUFFY")
if result.returncode == 0:
    if "{search_term}" in result.stdout:
        print("FOUND")
    else:
        print("NOT_FOUND")
else:
    print("FILE_NOT_EXISTS")
'''],
            capture_output=True,
            text=True,
            cwd='/data/LUFFY'
        )
        print(f"Commit {commit[:8]}: {result.stdout.strip()}")
    except Exception as e:
        print(f"Commit {commit[:8]}: Error - {e}")
