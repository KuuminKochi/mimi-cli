import os
import shutil
import glob
from typing import List, Dict, Any, Optional

try:
    import pypdf
except ImportError:
    pypdf = None


def read_file(path: str) -> str:
    """Reads the content of a file. Supports native PDF text extraction."""
    try:
        # Expand user path
        abs_path = os.path.abspath(os.path.expanduser(path))
        if not os.path.isfile(abs_path):
            return f"Error: '{path}' is not a file."

        # Handle PDF files
        if abs_path.lower().endswith(".pdf"):
            if not pypdf:
                return "Error: pypdf library not installed. Cannot read PDF."
            try:
                text_content = []
                with open(abs_path, "rb") as f:
                    reader = pypdf.PdfReader(f)
                    text_content.append(
                        f"--- PDF Content: {os.path.basename(path)} ---"
                    )
                    text_content.append(f"Pages: {len(reader.pages)}")
                    for i, page in enumerate(reader.pages):
                        text = page.extract_text()
                        if text:
                            text_content.append(f"\n--- Page {i + 1} ---\n{text}")
                return "\n".join(text_content)
            except Exception as e:
                return f"Error reading PDF: {e}"

        # Handle Text files
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        # Limit content size for LLM context
        if len(content) > 30000:
            return content[:30000] + "\n... [Content Truncated]"
        return content
    except Exception as e:
        return f"Error reading file: {str(e)}"


def write_file(path: str, content: str) -> str:
    """Writes content to a file, creating directories if needed."""
    try:
        abs_path = os.path.abspath(os.path.expanduser(path))
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)

        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)

        return f"Successfully wrote to '{path}'."
    except Exception as e:
        return f"Error writing file: {str(e)}"


def list_directory(path: str) -> str:
    """Lists files and directories in a given path."""
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


def create_directory(path: str) -> str:
    """Creates a new directory."""
    try:
        abs_path = os.path.abspath(os.path.expanduser(path))
        os.makedirs(abs_path, exist_ok=True)
        return f"Directory '{path}' created or already exists."
    except Exception as e:
        return f"Error creating directory: {str(e)}"


def move_file(source: str, destination: str) -> str:
    """Moves or renames a file or directory."""
    try:
        src_abs = os.path.abspath(os.path.expanduser(source))
        dst_abs = os.path.abspath(os.path.expanduser(destination))

        if not os.path.exists(src_abs):
            return f"Error: Source '{source}' does not exist."

        shutil.move(src_abs, dst_abs)
        return f"Moved '{source}' to '{destination}'."
    except Exception as e:
        return f"Error moving file: {str(e)}"


def search_files(path: str, pattern: str) -> str:
    """Searches for files matching a pattern recursively."""
    try:
        abs_path = os.path.abspath(os.path.expanduser(path))
        if not os.path.isdir(abs_path):
            return f"Error: '{path}' is not a directory."

        # Use glob for recursive search
        search_pattern = os.path.join(abs_path, "**", pattern)
        results = glob.glob(search_pattern, recursive=True)

        if not results:
            return f"No files matching '{pattern}' found in '{path}'."

        output = [f"Search results for '{pattern}' in '{path}':"]
        for r in sorted(results):
            # Make path relative to search root for cleaner output
            rel = os.path.relpath(r, abs_path)
            output.append(f"  {rel}")

        return "\n".join(output[:100])  # Limit to 100 results
    except Exception as e:
        return f"Error searching files: {str(e)}"


def get_codebase_index(path: str) -> str:
    """Generates a high-level index of the codebase (files + definitions)."""
    try:
        abs_path = os.path.abspath(os.path.expanduser(path))
        if not os.path.isdir(abs_path):
            return f"Error: '{path}' is not a directory."

        index_lines = [f"Codebase Index for: {abs_path}"]

        # Walk the directory
        for root, dirs, files in os.walk(abs_path):
            # Skip hidden folders and common noise
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".")
                and d not in ["__pycache__", "venv", "node_modules", "build", "dist"]
            ]

            rel_root = os.path.relpath(root, abs_path)
            if rel_root == ".":
                rel_root = ""

            for f in sorted(files):
                if f.startswith("."):
                    continue

                file_path = os.path.join(root, f)
                rel_path = os.path.join(rel_root, f)

                # Basic file entry
                index_lines.append(f"\n[FILE] {rel_path}")

                # Simple Python definition extraction
                if f.endswith(".py"):
                    try:
                        with open(
                            file_path, "r", encoding="utf-8", errors="ignore"
                        ) as py_f:
                            for line in py_f:
                                line = line.strip()
                                if line.startswith("class ") or line.startswith("def "):
                                    if line.endswith(":"):
                                        # Truncate long signatures
                                        sig = line[:-1]
                                        if len(sig) > 80:
                                            sig = sig[:77] + "..."
                                        index_lines.append(f"  - {sig}")
                    except:
                        pass

                # Simple JS/TS definition extraction (basic heuristic)
                elif f.endswith((".js", ".ts", ".jsx", ".tsx")):
                    try:
                        with open(
                            file_path, "r", encoding="utf-8", errors="ignore"
                        ) as js_f:
                            for line in js_f:
                                line = line.strip()
                                if (
                                    line.startswith("function ")
                                    or line.startswith("class ")
                                    or ("const " in line and " = (" in line)
                                    or ("export " in line)
                                ):
                                    if len(line) < 100 and "{" in line:
                                        clean = line.split("{")[0].strip()
                                        index_lines.append(f"  - {clean}")
                    except:
                        pass

        return "\n".join(index_lines)

    except Exception as e:
        return f"Error indexing codebase: {str(e)}"
