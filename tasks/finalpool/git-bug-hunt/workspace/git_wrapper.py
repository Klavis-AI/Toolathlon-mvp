#!/usr/bin/env python3
import os
import zlib

def read_git_object(repo_path, obj_hash):
    """Read a git object from the objects directory"""
    obj_dir = obj_hash[:2]
    obj_file = obj_hash[2:]
    obj_path = os.path.join(repo_path, '.git', 'objects', obj_dir, obj_file)
    
    try:
        with open(obj_path, 'rb') as f:
            compressed = f.read()
            decompressed = zlib.decompress(compressed)
            return decompressed
    except Exception as e:
        return None

def parse_commit(commit_data):
    """Parse commit data to extract information"""
    if not commit_data:
        return None
    
    # Decode bytes
    text = commit_data.decode('utf-8', errors='ignore')
    
    # Split header and message
    parts = text.split('\n\n', 1)
    header = parts[0]
    message = parts[1] if len(parts) > 1 else ''
    
    # Parse header
    lines = header.split('\n')
    tree = None
    parent = None
    author = None
    committer = None
    
    for line in lines:
        if line.startswith('tree '):
            tree = line[5:]
        elif line.startswith('parent '):
            parent = line[7:]
        elif line.startswith('author '):
            author = line[7:]
        elif line.startswith('committer '):
            committer = line[10:]
    
    return {
        'tree': tree,
        'parent': parent,
        'author': author,
        'committer': committer,
        'message': message.strip()
    }

# Read commit objects
commits = [
    'cdd6234342b147880f5d86c55dad6c1fbe222bfe',
    '737c3636da8d3816b5a1da3ab899b0066d19c50b',
    'c37a78c32787eb1dcbd9c0df231ecf1d6a3e1f47',
]

repo_path = '/data/LUFFY'

for commit_hash in commits:
    print(f"\n{'='*60}")
    print(f"Commit: {commit_hash}")
    commit_data = read_git_object(repo_path, commit_hash)
    if commit_data:
        info = parse_commit(commit_data)
        if info:
            print(f"Author: {info['author']}")
            print(f"Message: {info['message']}")
    else:
        print("Could not read commit")
