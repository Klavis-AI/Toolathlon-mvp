"""
Minimal helper utilities extracted from Toolathlon/utils/general/helper.py.
Only includes functions needed by task preprocess/evaluation scripts.
"""
import json
import os
import re
import asyncio
import pickle
import pandas as pd


def normalize_str(xstring):
    return re.sub(r'[^\w]', '', xstring).lower().strip()


def read_json(json_file_path):
    with open(json_file_path, "r") as f:
        return json.load(f)

def read_parquet(parquet_file_path):
    dt = pd.read_parquet(parquet_file_path)
    # convert it into a list of dict
    return dt.to_dict(orient="records")

def read_pkl(pkl_file_path):
    with open(pkl_file_path, "rb") as f:
        return pickle.load(f)
    
def read_jsonl(jsonl_file_path):
    s = []
    with open(jsonl_file_path, "r") as f:
        lines = f.readlines()
    for line in lines:
        linex = line.strip()
        if linex == "":
            continue
        s.append(json.loads(linex))
    return s


def write_json(data, json_file_path, mode="w"):
    dir_path = os.path.dirname(json_file_path)
    if dir_path and not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)
    with open(json_file_path, mode) as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def print_color(text, color="yellow", end='\n'):
    color_codes = {
        'red': '\033[91m', 'green': '\033[92m', 'yellow': '\033[93m',
        'blue': '\033[94m', 'magenta': '\033[95m', 'cyan': '\033[96m', 'white': '\033[97m',
    }
    reset_code = '\033[0m'
    if color.lower() not in color_codes:
        print(f"Unsupported color: {color}. Using default.", end='')
        print(text, end=end)
    else:
        color_code = color_codes[color.lower()]
        print(f"{color_code}{text}{reset_code}", end=end)


async def run_command(command, debug=False, show_output=False):
    current_dir = os.path.abspath(os.getcwd())
    print_color(f"Current working directory to run command: {current_dir}", "cyan")
    process = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    if debug:
        print_color(f"Executing command : {command}", "cyan")
    stdout, stderr = await process.communicate()
    stdout_decoded = stdout.decode()
    stderr_decoded = stderr.decode()
    if debug:
        print_color("Successfully executed!", "green")
    if show_output and stdout_decoded:
        print(f"Command output:\n{stdout_decoded}")
    return stdout_decoded, stderr_decoded, process.returncode


def get_module_path(replace_last: str = None) -> str:
    """
    Get the package path (relative to the current working directory) connected with dots, optionally replace the last level.
    - replace_last: If specified, replace the last level (usually the file name) with the value
    """
    import inspect
    stack = inspect.stack()
    target_file = None
    for frame in stack:
        fname = frame.filename
        if not fname.endswith("helper.py") and fname.endswith(".py"):
            target_file = os.path.abspath(fname)
            break
    if target_file is None:
        raise RuntimeError("Cannot automatically infer target file path")

    cwd = os.getcwd()
    relative_path = os.path.relpath(target_file, cwd)
    module_path = os.path.splitext(relative_path)[0].replace(os.sep, ".")

    if replace_last is not None:
        parts = module_path.split('.')
        parts[-1] = replace_last
        module_path = '.'.join(parts)

    return module_path


async def fork_repo(source_repo, target_repo, fork_default_branch_only, readonly=False):
    command = f"uv run -m utils.app_specific.github.github_delete_and_refork "
    command += f"--source_repo_name {source_repo} "
    command += f"--target_repo_name {target_repo}"
    if fork_default_branch_only:
        command += " --default_branch_only"
    if readonly:
        command += " --read_only"
    await run_command(command, debug=True, show_output=True)
    print_color(f"Forked repo {source_repo} to {target_repo} successfully", "green")

def read_all(file_path):
    if file_path.endswith(".jsonl"):
        return read_jsonl(file_path)
    elif file_path.endswith(".json"):
        return read_json(file_path)
    elif file_path.endswith(".parquet"):
        return read_parquet(file_path)
    elif file_path.endswith(".pkl"):
        return read_pkl(file_path)
    else:
        with open(file_path, "r") as f:
            return f.read()