import subprocess
import os
from typing import Optional, Tuple


def run_git_cmd(args: list[str], cwd: Optional[str] = None) -> Tuple[bool, str]:
    """
    Runs a git command in the specified directory.
    Returns (success, output_or_error_message).
    """
    try:
        if not cwd:
            cwd = os.getcwd()

        # Check if directory exists
        if not os.path.exists(cwd):
            return False, f"Directory '{cwd}' does not exist."

        full_cmd = ["git"] + args
        result = subprocess.run(
            full_cmd, cwd=cwd, capture_output=True, text=True, check=False
        )

        if result.returncode == 0:
            return True, result.stdout.strip()
        else:
            return False, result.stderr.strip()

    except Exception as e:
        return False, f"System Error executing git command: {str(e)}"


def is_git_repo(path: str) -> bool:
    """Checks if the given path is a git repository."""
    success, _ = run_git_cmd(["rev-parse", "--is-inside-work-tree"], cwd=path)
    return success


def git_status(cwd: str) -> Tuple[bool, str]:
    """Returns the output of 'git status'."""
    return run_git_cmd(["status"], cwd=cwd)


def git_pull(
    cwd: str, remote: Optional[str] = "origin", branch: Optional[str] = "main"
) -> Tuple[bool, str]:
    """Executes 'git pull <remote> <branch>'. If remote/branch are None, runs standard 'git pull'."""
    cmd = ["pull"]
    if remote:
        cmd.append(remote)
        if branch:
            cmd.append(branch)
    return run_git_cmd(cmd, cwd=cwd)


def git_add(cwd: str, files: str = ".") -> Tuple[bool, str]:
    """Executes 'git add <files>'."""
    return run_git_cmd(["add", files], cwd=cwd)


def git_commit(cwd: str, message: str) -> Tuple[bool, str]:
    """Executes 'git commit -m <message>'."""
    return run_git_cmd(["commit", "-m", message], cwd=cwd)


def git_push(
    cwd: str, remote: str = "origin", branch: str = "main"
) -> Tuple[bool, str]:
    """Executes 'git push <remote> <branch>'."""
    return run_git_cmd(["push", remote, branch], cwd=cwd)
