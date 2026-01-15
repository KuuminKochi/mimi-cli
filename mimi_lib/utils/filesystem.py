import os
import shutil
import glob
from typing import List, Dict, Any, Optional

try:
    import pypdf
except ImportError:
    pypdf = None

def read_file(path: str) -> str:
    try:
        abs_path = os.path.abspath(os.path.expanduser(path))
        if not os.path.isfile(abs_path):
            return f"Error: '{path}' is not a file."
        if abs_path.lower().endswith(".pdf"):
            if not pypdf:
                return "Error: pypdf library not installed."
            text_content = []
            with open(abs_path, "rb") as f:
                reader = pypdf.PdfReader(f)
                for i, page in enumerate(reader.pages):
                    text = page.extract_text()
                    if text:
                        text_content.append(f"\n--- Page {i + 1} ---\n{text}")
            return "\n".join(text_content)
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return content[:30000] if len(content) > 30000 else content
    except Exception as e:
        return f"Error reading file: {str(e)}"

def write_file(path: str, content: str) -> str:
    try:
        abs_path = os.path.abspath(os.path.expanduser(path))
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote to '{path}'."
    except Exception as e:
        return f"Error writing file: {str(e)}"

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
        excludes = {".git", "node_modules", "__pycache__", "venv", ".env", "dist", "build", ".vscode", ".idea"}
        
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
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ["__pycache__", "venv", "node_modules"]]
            for f in sorted(files):
                if f.startswith("."): continue
                rel_path = os.path.relpath(os.path.join(root, f), abs_path)
                index_lines.append(f"\n[FILE] {rel_path}")
                if f.endswith(".py"):
                    try:
                        with open(os.path.join(root, f), "r", encoding="utf-8", errors="ignore") as py_f:
                            for line in py_f:
                                line = line.strip()
                                if line.startswith("class ") or line.startswith("def "):
                                    index_lines.append(f"  - {line.split(':')[0]}")
                    except: pass
        return "\n".join(index_lines)
    except Exception as e:
        return f"Error indexing codebase: {str(e)}"
