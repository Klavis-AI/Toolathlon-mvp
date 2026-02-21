"""
Minimal helper utilities extracted from Toolathlon/utils/general/helper.py.
Only includes functions needed by task preprocess/evaluation scripts.
"""
import os
import asyncio


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
