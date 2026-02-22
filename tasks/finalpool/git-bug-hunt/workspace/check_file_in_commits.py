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

def parse_tree(tree_data):
    """Parse git tree object"""
    if not tree_data:
        return []
    
    # Skip the header
    null_pos = tree_data.find(b'\x00')
    if null_pos == -1:
        return []
    
    data = tree_data[null_pos + 1:]
    entries = []
    
    while data:
        # Find the space (mode/name separator)
        space_pos = data.find(b' ')
        if space_pos == -1:
            break
        
        mode = data[:space_pos]
        data = data[space_pos + 1:]
        
        # Find null byte (name/hash separator)
        null_pos = data.find(b'\x00')
        if null_pos == -1:
            break
        
        name = data[:null_pos].decode('utf-8', errors='ignore')
        data = data[null_pos + 1:]
        
        # Next 20 bytes are the SHA-1 hash
        if len(data) < 20:
            break
        
        obj_hash = data[:20].hex()
        data = data[20:]
        
        entries.append({
            'mode': mode.decode('utf-8'),
            'name': name,
            'hash': obj_hash
        })
    
    return entries

def find_file_in_tree(repo_path, tree_hash, path_parts):
    """Recursively find a file in a git tree"""
    if not path_parts:
        return None
    
    tree_data = read_git_object(repo_path, tree_hash)
    if not tree_data:
        return None
    
    entries = parse_tree(tree_data)
    
    for entry in entries:
        if entry['name'] == path_parts[0]:
            if len(path_parts) == 1:
                # Found the file
                return entry['hash']
            else:
                # Need to go deeper
                return find_file_in_tree(repo_path, entry['hash'], path_parts[1:])
    
    return None

def read_blob(repo_path, blob_hash):
    """Read a blob object (file content)"""
    blob_data = read_git_object(repo_path, blob_hash)
    if not blob_data:
        return None
    
    # Skip the header
    null_pos = blob_data.find(b'\x00')
    if null_pos == -1:
        return None
    
    return blob_data[null_pos + 1:].decode('utf-8', errors='ignore')

def get_commit_tree(repo_path, commit_hash):
    """Get the tree hash from a commit"""
    commit_data = read_git_object(repo_path, commit_hash)
    if not commit_data:
        return None
    
    text = commit_data.decode('utf-8', errors='ignore')
    for line in text.split('\n'):
        if line.startswith('tree '):
            return line[5:].strip()
    
    return None

# Check commits in chronological order
commits = [
    ('9d25e171bbfcd61d5c2b73ffd284b6fde1318d71', 'motigrez', 'grdyx2138039185@126.com'),
    ('c37a78c32787eb1dcbd9c0df231ecf1d6a3e1f47', 'Sarah Johnson', 'sarah.johnson@team.ai'),
    ('737c3636da8d3816b5a1da3ab899b0066d19c50b', 'Michael Zhang', 'mzhang@dataops.io'),
    ('cdd6234342b147880f5d86c55dad6c1fbe222bfe', 'Patrick Cruz', 'patrick_cruz@mcp.com'),
    ('974124e210ea26f75ec8b5ae1e5516a460bf003d', 'Alex Rodriguez', 'alex.rodriguez@eval.com'),
    ('1937b6addce50565c710e6543d5531aa3ee70a4b', 'Jennifer Lee', 'jlee@modelops.dev')
]

repo_path = '/data/LUFFY'
target_file = 'luffy/verl/verl/mix_src/mix_core_alg.py'
path_parts = target_file.split('/')
search_term = 'remove_caching_layer'

print(f"Searching for '{search_term}' in {target_file}\n")

first_commit_found = None

for commit_hash, author, email in commits:
    tree_hash = get_commit_tree(repo_path, commit_hash)
    if tree_hash:
        blob_hash = find_file_in_tree(repo_path, tree_hash, path_parts)
        if blob_hash:
            content = read_blob(repo_path, blob_hash)
            if content and search_term in content:
                print(f"✓ FOUND in {commit_hash[:8]} - {author}")
                if not first_commit_found:
                    first_commit_found = (commit_hash, author, email)
            else:
                print(f"✗ NOT FOUND in {commit_hash[:8]} - {author}")
        else:
            print(f"✗ File doesn't exist in {commit_hash[:8]} - {author}")
    else:
        print(f"✗ Could not read tree for {commit_hash[:8]}")

if first_commit_found:
    print(f"\n{'='*60}")
    print(f"EARLIEST COMMIT WITH '{search_term}':")
    print(f"Commit: {first_commit_found[0]}")
    print(f"Author: {first_commit_found[1]}")
    print(f"Email: {first_commit_found[2]}")
