from mimi_lib.tools.registry import register_tool
from mimi_lib.utils.filesystem import (
    read_file,
    write_file,
    edit_file,
    list_directory,
    search_files,
    get_codebase_index,
)
from mimi_lib.utils.git import git_pull, is_git_repo
import threading
import os
from mimi_lib.config import VAULT_PATH


def _auto_pull(path: str) -> str:
    """Attempts to pull changes if the file is in a git repo."""
    try:
        abs_path = os.path.abspath(os.path.expanduser(path))
        cwd = os.path.dirname(abs_path)

        # Traverse up to find git root if we are in a subdir
        # (Though is_git_repo and git_pull usually handle cwd fine)
        if is_git_repo(cwd):
            success, output = git_pull(cwd, remote=None, branch=None)
            if not success:
                if "not a git repository" in output:
                    return ""  # False positive?
                return f"Error: Auto-pull failed. {output}"
    except Exception as e:
        return f"Error during auto-pull: {e}"
    return ""


def _trigger_sync(path: str):
    """Triggers background vault sync if the file is in the Obsidian vault."""
    try:
        abs_path = os.path.abspath(os.path.expanduser(path))
        vault_abs = os.path.abspath(os.path.expanduser(str(VAULT_PATH)))
        if abs_path.startswith(vault_abs):
            from mimi_lib.memory.vault_indexer import index_vault

            threading.Thread(target=index_vault, args=(False,), daemon=True).start()
    except:
        pass


def write_file_wrapper(path: str, content: str) -> str:
    pull_err = _auto_pull(path)
    if pull_err:
        return f"Operation aborted. {pull_err}"

    result = write_file(path, content)
    if "Successfully" in result:
        _trigger_sync(path)
    return result


def edit_file_wrapper(path: str, old_string: str, new_string: str) -> str:
    pull_err = _auto_pull(path)
    if pull_err:
        return f"Operation aborted. {pull_err}"

    result = edit_file(path, old_string, new_string)
    if "Successfully" in result:
        _trigger_sync(path)
    return result


@register_tool(
    "list_signed_files",
    "List all files in The Vault that Mimi has worked on and signed.",
    {"type": "object", "properties": {}},
)
def list_signed_files() -> str:
    import subprocess

    try:
        # Use grep to find files containing mimi_signed: true
        cmd = ["grep", "-r", "-l", "mimi_signed: true", str(VAULT_PATH)]
        res = subprocess.run(cmd, capture_output=True, text=True)
        files = res.stdout.strip().split("\n") if res.stdout.strip() else []

        # Also check for code signatures
        cmd_code = ["grep", "-r", "-l", "Signed by Mimi ✿", str(VAULT_PATH)]
        res_code = subprocess.run(cmd_code, capture_output=True, text=True)
        code_files = (
            res_code.stdout.strip().split("\n") if res_code.stdout.strip() else []
        )

        all_signed = sorted(list(set(files + code_files)))

        if not all_signed:
            return "I haven't signed any files in The Vault yet! ✿"

        output = [f"I found {len(all_signed)} files I've worked on:"]
        for f in all_signed:
            try:
                rel = os.path.relpath(f, VAULT_PATH)
                output.append(f"- {rel}")
            except:
                output.append(f"- {f}")
        return "\n".join(output)
    except Exception as e:
        return f"Error listing signed files: {e}"


register_tool(
    "read_file",
    "Read a local file. Supports paging (offset/limit) and pattern search.",
    {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "offset": {
                "type": "integer",
                "description": "Line number to start reading from (0-indexed).",
            },
            "limit": {
                "type": "integer",
                "description": "Max lines to read (default 500).",
            },
            "pattern": {
                "type": "string",
                "description": "Optional text to search for; automatically sets offset around match.",
            },
        },
        "required": ["path"],
    },
)(read_file)

register_tool(
    "write_file",
    "Write to a local file (overwrites entire file). Triggers auto-sync if in Vault.",
    {
        "type": "object",
        "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
        "required": ["path", "content"],
    },
)(write_file_wrapper)

register_tool(
    "edit_file",
    "Edit a local file by replacing a snippet (old_string -> new_string). Triggers auto-sync if in Vault.",
    {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "old_string": {"type": "string"},
            "new_string": {"type": "string"},
        },
        "required": ["path", "old_string", "new_string"],
    },
)(edit_file_wrapper)

register_tool(
    "list_directory",
    "List files in a directory.",
    {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    },
)(list_directory)

register_tool(
    "search_files",
    "Search for files by pattern.",
    {
        "type": "object",
        "properties": {"path": {"type": "string"}, "pattern": {"type": "string"}},
        "required": ["path", "pattern"],
    },
)(search_files)

register_tool(
    "get_codebase_index",
    "Get an index of the codebase.",
    {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    },
)(get_codebase_index)
