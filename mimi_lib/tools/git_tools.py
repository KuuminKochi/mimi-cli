import os
from mimi_lib.tools.registry import register_tool
from mimi_lib.utils.git import (
    run_git_cmd,
    git_pull,
    git_add,
    git_commit,
    git_push,
    git_status,
    is_git_repo,
)
from mimi_lib.config import VAULT_PATH, PROJECT_ROOT


@register_tool(
    "sync_vault",
    "Sync the Obsidian Vault with GitHub (Pull -> Add -> Commit -> Push).",
    {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "Commit message describing the changes or 'Sync' for general update.",
            }
        },
        "required": ["message"],
    },
)
def sync_vault(message: str) -> str:
    """
    Orchestrates a full sync of the Obsidian Vault.
    1. Pull latest changes (to avoid conflicts)
    2. Add all local changes
    3. Commit
    4. Push
    """
    vault_dir = str(VAULT_PATH)

    if not is_git_repo(vault_dir):
        return (
            f"Error: The vault directory '{vault_dir}' is not a valid git repository."
        )

    # 1. Pull
    success, output = git_pull(vault_dir)
    if not success:
        return f"Error pulling changes: {output}\n\nAborting sync to prevent conflicts."
    pull_msg = f"Pull result: {output}" if output else "Already up to date."

    # 2. Add
    success, output = git_add(vault_dir)
    if not success:
        return f"{pull_msg}\nError adding files: {output}"

    # 3. Commit
    # Check status first to see if there is anything to commit
    s_success, s_output = git_status(vault_dir)
    if "nothing to commit, working tree clean" in s_output:
        return f"{pull_msg}\nNo local changes to commit."

    success, output = git_commit(vault_dir, f"Mimi: {message}")
    if not success:
        return f"{pull_msg}\nError committing: {output}"
    commit_msg = output

    # 4. Push
    success, output = git_push(vault_dir)
    if not success:
        return f"{pull_msg}\nCommit successful: {commit_msg}\nError pushing: {output}"

    return f"Vault Sync Complete.\n{pull_msg}\n{commit_msg}\nPush result: {output}"


@register_tool(
    "check_git_status",
    "Check the git status of the Vault or the Mimi System.",
    {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "enum": ["vault", "system"],
                "description": "Which repository to check.",
            }
        },
        "required": ["target"],
    },
)
def check_git_status(target: str) -> str:
    """Checks git status for the specified repo."""
    if target == "vault":
        path = str(VAULT_PATH)
    else:
        path = str(PROJECT_ROOT)

    if not is_git_repo(path):
        return f"Error: '{path}' is not a git repository."

    success, output = git_status(path)
    if success:
        return f"Git Status for {target} ({path}):\n{output}"
    else:
        return f"Error checking status: {output}"
