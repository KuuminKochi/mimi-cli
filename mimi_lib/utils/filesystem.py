import os
import shutil
import glob
import re
from datetime import datetime
from typing import List, Dict, Any, Optional

try:
    import pypdf
except ImportError:
    pypdf = None


def sign_content(path: str, content: str) -> str:
    """Adds or updates Mimi's signature in Markdown or Code files."""
    today = datetime.now().strftime("%Y-%m-%d")
    sig_visible = f"\n\n---\n_Signed by Mimi ✿ on {today}_"

    if path.endswith(".md"):
        # Handle YAML frontmatter
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                yaml = parts[1]
                body = parts[2]

                # Update/Add properties
                if "mimi_signed:" not in yaml:
                    yaml = yaml.rstrip() + "\nmimi_signed: true\n"
                if "last_mimi_update:" in yaml:
                    yaml = re.sub(
                        r"last_mimi_update: .*", f"last_mimi_update: {today}", yaml
                    )
                else:
                    yaml = yaml.rstrip() + f"\nlast_mimi_update: {today}\n"

                content = f"---{yaml}---{body}"
        else:
            # Add simple YAML if none exists
            content = (
                f"---\nmimi_signed: true\nlast_mimi_update: {today}\n---\n{content}"
            )

        # Handle Footer (Visible)
        if "_Signed by Mimi ✿ on" in content:
            content = re.sub(r"\n\n---\n_Signed by Mimi ✿ on .*_", sig_visible, content)
        else:
            content = content.rstrip() + sig_visible

    elif any(path.endswith(ext) for ext in [".py", ".js", ".ts", ".sh", ".bash"]):
        # Code comments
        comment_prefix = "#" if not path.endswith((".js", ".ts")) else "//"
        pattern = rf"{re.escape(comment_prefix)} Signed by Mimi ✿ on .*"
        new_sig = f"{comment_prefix} Signed by Mimi ✿ on {today}"

        if re.search(pattern, content):
            content = re.sub(pattern, new_sig, content)
        else:
            content = f"{new_sig}\n{content}"

    return content


def read_file(
    path: str, offset: int = 0, limit: int = 500, pattern: Optional[str] = None
) -> str:
    try:
        abs_path = os.path.abspath(os.path.expanduser(path))
        if not os.path.isfile(abs_path):
            return f"Error: '{path}' is not a file."

        # PDF handling (unchanged for now, but stripped of simple read logic)
        if abs_path.lower().endswith(".pdf"):
            # ... (Keep existing PDF logic if needed, or simplify)
            if not pypdf:
                return "Error: pypdf library not installed."
            text_content = []
            with open(abs_path, "rb") as f:
                reader = pypdf.PdfReader(f)
                for i, page in enumerate(reader.pages):
                    text = page.extract_text()
                    if text:
                        text_content.append(f"\n--- Page {i + 1} ---\n{text}")
            return "\n".join(text_content)[:30000]

        # Text file handling with surgical precision
        lines = []
        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                all_lines = f.readlines()
        except Exception as e:
            return f"Error opening file: {e}"

        total_lines = len(all_lines)

        # Pattern-based offset adjustment
        if pattern:
            found_idx = -1
            for i, line in enumerate(all_lines):
                if pattern in line:
                    found_idx = i
                    break

            if found_idx != -1:
                # Center the view around the match
                # e.g., show 20 lines before and fill up to 'limit'
                offset = max(0, found_idx - 20)
                # Ensure we don't just read one line if limit is huge
                # but if user specifically asked for pattern, maybe they want context
                # Let's trust the offset/limit logic now that we set offset
            else:
                return f"Pattern '{pattern}' not found in '{path}'."

        # Range clamping
        start = max(0, offset)
        end = min(total_lines, start + limit)

        if start >= total_lines:
            return f"Error: Offset {start} is beyond file length ({total_lines} lines)."

        # Content Formatting
        output = [f"--- File: {path} | Lines {start + 1}-{end} of {total_lines} ---"]
        for i in range(start, end):
            # Format: "  42 | import os"
            line_content = all_lines[i].rstrip("\n")
            output.append(f"{i + 1:4d} | {line_content}")

        if end < total_lines:
            output.append(
                f"\n... ( {total_lines - end} more lines. Use offset={end} to read more ) ..."
            )

        return "\n".join(output)

    except Exception as e:
        return f"Error reading file: {str(e)}"


def write_file(path: str, content: str) -> str:
    try:
        abs_path = os.path.abspath(os.path.expanduser(path))
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)

        # Sign content before writing
        signed_content = sign_content(path, content)

        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(signed_content)
        return f"Successfully wrote to '{path}'."
    except Exception as e:
        return f"Error writing file: {str(e)}"


def edit_file(path: str, old_string: str, new_string: str) -> str:
    """Find and replace a string in a file (snippet-based editing)."""
    try:
        abs_path = os.path.abspath(os.path.expanduser(path))
        if not os.path.isfile(abs_path):
            return f"Error: '{path}' is not a file."

        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        if old_string not in content:
            return f"Error: '{old_string}' not found in '{path}'."

        if content.count(old_string) > 1:
            return f"Error: Multiple occurrences of '{old_string}' found. Please provide more context."

        new_content = content.replace(old_string, new_string)

        # Sign content after edit
        signed_content = sign_content(path, new_content)

        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(signed_content)

        return f"Successfully edited '{path}'."
    except Exception as e:
        return f"Error editing file: {str(e)}"


def list_directory(path: str) -> str:
    try:
        abs_path = os.path.abspath(os.path.expanduser(path))
        if not os.path.isdir(abs_path):
            return f"Error: '{path}' is not a directory."
        items = os.listdir(abs_path)
        output = [f"Contents of '{path}':"]
        for item in sorted(items):
            item_path = os.path.join(abs_path, item)
            prefix = "[DIR] " if os.path.isdir(item_path) else "[FILE]"
            output.append(f"  {prefix} {item}")
        return "\n".join(output)
    except Exception as e:
        return f"Error listing directory: {str(e)}"


def search_files(path: str, pattern: str) -> str:
    try:
        abs_path = os.path.abspath(os.path.expanduser(path))
        results = []
        # Common exclusion list to speed up search
        excludes = {
            ".git",
            "node_modules",
            "__pycache__",
            "venv",
            ".env",
            "dist",
            "build",
            ".vscode",
            ".idea",
        }

        # Simple glob-like matching using fnmatch would be ideal, but for now we'll do simple substring or extension check
        # depending on if the pattern looks like a glob (*.py) or a name (config)
        import fnmatch

        for root, dirs, files in os.walk(abs_path):
            # Prune excluded directories
            dirs[:] = [d for d in dirs if d not in excludes and not d.startswith(".")]

            for name in files:
                if fnmatch.fnmatch(name, pattern):
                    results.append(os.path.join(root, name))
                    if len(results) >= 100:  # Hard limit to prevent massive output
                        break
            if len(results) >= 100:
                break

        if not results:
            return f"No files matching '{pattern}' found."

        output = [f"Search results for '{pattern}' in '{path}':"]
        for r in sorted(results):
            output.append(f"  {os.path.relpath(r, abs_path)}")
        return "\n".join(output)
    except Exception as e:
        return f"Error searching files: {str(e)}"


def get_codebase_index(path: str) -> str:
    try:
        abs_path = os.path.abspath(os.path.expanduser(path))
        index_lines = [f"Codebase Index for: {abs_path}"]
        for root, dirs, files in os.walk(abs_path):
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".")
                and d not in ["__pycache__", "venv", "node_modules"]
            ]
            for f in sorted(files):
                if f.startswith("."):
                    continue
                rel_path = os.path.relpath(os.path.join(root, f), abs_path)
                index_lines.append(f"\n[FILE] {rel_path}")
                if f.endswith(".py"):
                    try:
                        with open(
                            os.path.join(root, f),
                            "r",
                            encoding="utf-8",
                            errors="ignore",
                        ) as py_f:
                            for line in py_f:
                                line = line.strip()
                                if line.startswith("class ") or line.startswith("def "):
                                    index_lines.append(f"  - {line.split(':')[0]}")
                    except:
                        pass
        return "\n".join(index_lines)
    except Exception as e:
        return f"Error indexing codebase: {str(e)}"
