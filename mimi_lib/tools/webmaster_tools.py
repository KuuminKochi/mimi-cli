import os
import re
import subprocess
from datetime import datetime
from mimi_lib.tools.registry import register_tool
from mimi_lib.config import PROJECT_ROOT

# Hardcoded paths based on user environment
SITE_ROOT = "/projects/itskuuminfyi"
CONTENT_DIR = os.path.expanduser("~/Documents/kuumin/content/")
INDEX_FILE = os.path.join(SITE_ROOT, "index.html")
KSYNC_CMD = "/home/kuumin/bin/ksync"


@register_tool(
    name="update_status",
    description="Updates Mimi's status window on the itskuuminfyi website sidebar.",
    parameters={
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "The status message to display in the sidebar window.",
            },
            "system_status": {
                "type": "string",
                "description": "Short system state (e.g., ONLINE, STUDYING, OFFLINE). Defaults to current value if not provided.",
            },
        },
        "required": ["message"],
    },
)
def update_status(message: str, system_status: str | None = None) -> str:
    """Updates the status message in index.html."""
    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            content = f.read()

        # Update Message
        # Regex to find content inside <div id="mimi-status-msg" ...> ... </div>
        # We look for the div, preserve the opening tag attributes, and replace content until the closing div
        msg_pattern = r'(<div id="mimi-status-msg"[^>]*>)(.*?)(</div>)'

        if not re.search(msg_pattern, content, re.DOTALL):
            return "Error: Could not find #mimi-status-msg div in index.html"

        # Clean the message of HTML injections just in case, though basic formatting is allowed
        clean_msg = message.strip().replace("\n", "<br>")

        content = re.sub(
            msg_pattern,
            f"\\1\n                        {clean_msg}\n                    \\3",
            content,
            flags=re.DOTALL,
        )

        # Update System Status Label if provided
        if system_status:
            # Pattern: [SYSTEM]: <span ...>ONLINE</span>
            status_pattern = r"(\[SYSTEM\]: <span[^>]*>)(.*?)(</span>)"
            if re.search(status_pattern, content):
                content = re.sub(
                    status_pattern, f"\\1{system_status.upper()}\\3", content
                )

        with open(INDEX_FILE, "w", encoding="utf-8") as f:
            f.write(content)

        return f"Successfully updated status to: '{message}'"

    except Exception as e:
        return f"Error updating status: {str(e)}"


@register_tool(
    name="create_post",
    description="Creates a new blog post/log entry for the website and syncs it.",
    parameters={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Title of the post"},
            "content": {
                "type": "string",
                "description": "Body content of the post (Markdown supported)",
            },
            "mood": {
                "type": "string",
                "description": "Current mood (e.g., Focused, Happy, Tired)",
                "default": "Neutral",
            },
            "author": {
                "type": "string",
                "description": "Author name. Use 'mimi' for Journal style, 'kuumin' for default.",
                "default": "mimi",
            },
        },
        "required": ["title", "content"],
    },
)
def create_post(
    title: str, content: str, mood: str = "Neutral", author: str = "mimi"
) -> str:
    """Creates a markdown file and runs ksync."""
    try:
        date_str = datetime.now().strftime("%Y-%m-%d")

        # Sanitize title for filename
        safe_title = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        filename = f"{date_str}-{safe_title}.md"
        filepath = os.path.join(CONTENT_DIR, filename)

        frontmatter = f"""---
title: {title}
date: {date_str}
mood: {mood}
author: {author}
---

"""
        full_content = frontmatter + content

        # Ensure directory exists
        os.makedirs(CONTENT_DIR, exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(full_content)

        # Run ksync
        result = subprocess.run(
            [KSYNC_CMD], capture_output=True, text=True, check=False
        )

        if result.returncode != 0:
            # Fallback to python execution if ksync is not executable or found
            sync_script = os.path.join(SITE_ROOT, "sync.py")
            result = subprocess.run(
                ["python3", sync_script], capture_output=True, text=True, check=False
            )

        if result.returncode == 0:
            return f"Post created at {filename} and site synced successfully."
        else:
            return f"Post created but sync failed: {result.stderr}"

    except Exception as e:
        return f"Error creating post: {str(e)}"


@register_tool(
    name="create_template",
    description="Creates a blank Markdown template for a new blog post.",
    parameters={
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Title of the post (defaults to 'New Post')",
                "default": "New Post",
            },
            "author": {
                "type": "string",
                "description": "Author name (defaults to 'kuumin')",
                "default": "kuumin",
            },
        },
        "required": [],
    },
)
def create_template(title: str = "New Post", author: str = "kuumin") -> str:
    """Creates a template markdown file without syncing."""
    try:
        date_str = datetime.now().strftime("%Y-%m-%d")

        # Sanitize title for filename
        safe_title = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        filename = f"{date_str}-{safe_title}.md"
        filepath = os.path.join(CONTENT_DIR, filename)

        frontmatter = f"""---
title: {title}
date: {date_str}
mood: Neutral
author: {author}
---

# {title}

(Write your content here)
"""
        # Ensure directory exists
        os.makedirs(CONTENT_DIR, exist_ok=True)

        if os.path.exists(filepath):
            return f"Error: File '{filename}' already exists."

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(frontmatter)

        return f"Template created successfully: {filepath}"

    except Exception as e:
        return f"Error creating template: {str(e)}"


@register_tool(
    name="deploy_site",
    description="Syncs content using ksync, then commits and pushes changes to the website repository.",
    parameters={
        "type": "object",
        "properties": {"message": {"type": "string", "description": "Commit message"}},
        "required": ["message"],
    },
)
def deploy_site(message: str) -> str:
    """Runs ksync, then git add, commit, push for the site."""
    try:
        # Step 1: Run ksync to ensure all new content is baked into index.html
        sync_res = subprocess.run(
            [KSYNC_CMD], capture_output=True, text=True, check=False
        )
        if sync_res.returncode != 0:
            # Fallback
            sync_script = os.path.join(SITE_ROOT, "sync.py")
            sync_res = subprocess.run(
                ["python3", sync_script], capture_output=True, text=True, check=False
            )
            if sync_res.returncode != 0:
                return f"Sync failed before deploy: {sync_res.stderr}"

        # Step 2: Git Operations
        # Check if there are changes
        status = subprocess.run(
            ["git", "-C", SITE_ROOT, "status", "--porcelain"],
            capture_output=True,
            text=True,
        )

        if not status.stdout.strip():
            return "Sync completed, but no changes detected to deploy."

        # Add
        subprocess.run(["git", "-C", SITE_ROOT, "add", "."], check=True)

        # Commit
        subprocess.run(["git", "-C", SITE_ROOT, "commit", "-m", message], check=True)

        # Push
        push_res = subprocess.run(
            ["git", "-C", SITE_ROOT, "push", "origin", "main"],
            capture_output=True,
            text=True,
            check=False,
        )

        if push_res.returncode == 0:
            return "Site synced and deployed successfully."
        else:
            return f"Commit successful but push failed: {push_res.stderr}"

    except subprocess.CalledProcessError as e:
        return f"Git operation failed: {str(e)}"
    except Exception as e:
        return f"Error deploying site: {str(e)}"
