from mimi_lib.tools.registry import register_tool
from mimi_lib.memory.brain import save_memory
from mimi_lib.memory.embeddings import semantic_search
from mimi_lib.memory.vault_indexer import index_vault, search_vault
from mimi_lib.config import VAULT_PATH
import subprocess
import os


@register_tool(
    "vault_index",
    "Index or refresh the Obsidian vault knowledge base.",
    {"type": "object", "properties": {"force": {"type": "boolean", "default": False}}},
)
def vault_index(force: bool = False):
    return index_vault(force=force)


@register_tool(
    "vault_search",
    "Semantically search the user's Obsidian vault for relevant notes.",
    {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
)
def vault_search(query: str):
    results = search_vault(query)
    if not results:
        return "No relevant notes found in the vault."

    output = [f"Semantic search results for '{query}':"]
    for r in results:
        output.append(f"\n--- {r['path']} (Score: {r['score']:.2f}) ---\n{r['text']}")
    return "\n".join(output)


@register_tool(
    "obsidian_query",
    "Search and read notes from the user's Obsidian vault (Keyword match).",
    {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
)
def obsidian_query(query: str):
    vault_path = str(VAULT_PATH)
    try:
        cmd = ["grep", "-r", "-i", "-l", query, vault_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return "No matching notes found."
        files = result.stdout.strip().split("\n")
        output = [f"Found {len(files)} matching notes:"]
        for fpath in files[:3]:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                output.append(
                    f"\n--- {os.path.relpath(fpath, vault_path)} ---\n{f.read()[:1000]}"
                )
        return "\n".join(output)
    except Exception as e:
        return f"Obsidian query error: {e}"
