from mimi_lib.tools.registry import register_tool
from mimi_lib.memory.brain import save_memory, delete_memory
from mimi_lib.memory.embeddings import semantic_search
from mimi_lib.memory.vault_indexer import index_vault, search_vault
from mimi_lib.config import VAULT_PATH, MEMORY_ARCHIVE_FILE
import json
import subprocess
import os


@register_tool(
    "add_memory",
    "Commit a significant fact, event, or user preference to long-term memory.",
    {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The concise fact to remember.",
            },
            "category": {
                "type": "string",
                "enum": ["Kuumin", "Mimi", "Events", "Others"],
                "default": "Kuumin",
                "description": "Category for the memory.",
            },
        },
        "required": ["content"],
    },
)
def add_memory_tool(content: str, category: str = "Kuumin"):
    mem_id = save_memory(content, category)
    return f"Memory saved with ID: {mem_id}"


@register_tool(
    "delete_memory",
    "Remove a memory by its ID.",
    {
        "type": "object",
        "properties": {
            "id": {"type": "string", "description": "The ID of the memory to delete."}
        },
        "required": ["id"],
    },
)
def delete_memory_tool(id: str):
    success = delete_memory(id)
    if success:
        return f"Memory {id} deleted successfully."
    return f"Failed to find or delete memory {id}."


@register_tool(
    "search_memory",
    "Search the internal memory store (non-vault) for facts.",
    {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The semantic search query."}
        },
        "required": ["query"],
    },
)
def search_memory_tool(query: str):
    results = semantic_search(query, top_k=5)
    if not results:
        return "No relevant memories found."

    output = [f"Memory Search Results for '{query}':"]
    for r in results:
        output.append(
            f"- [{r.get('timestamp')}] {r.get('content')} (ID: {r.get('id')})"
        )
    return "\n".join(output)


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
    "vault_query",
    "Search The Vault for filenames and content to find valid [[WikiLinks]] targets.",
    {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
)
def vault_query(query: str):
    vault_path = str(VAULT_PATH)
    try:
        # Search filenames first (for linking)
        cmd_files = ["find", vault_path, "-iname", f"*{query}*"]
        res_files = subprocess.run(cmd_files, capture_output=True, text=True)
        found_files = (
            res_files.stdout.strip().split("\n") if res_files.stdout.strip() else []
        )

        # Then search content
        cmd_content = ["grep", "-r", "-i", "-l", query, vault_path]
        res_content = subprocess.run(cmd_content, capture_output=True, text=True)
        content_files = (
            res_content.stdout.strip().split("\n") if res_content.stdout.strip() else []
        )

        all_files = sorted(list(set(found_files + content_files)))

        if not all_files:
            return "No matching notes found."

        output = [f"Found {len(all_files)} matching notes (Use these for [[Links]]):"]
        for fpath in all_files[:5]:
            if not fpath:
                continue
            rel_path = os.path.relpath(fpath, vault_path)
            # Extract just filename for easy linking
            name_only = os.path.basename(fpath).replace(".md", "")
            output.append(f"\n- [[{name_only}]] (Path: {rel_path})")

            # Preview content
            if os.path.isfile(fpath):
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    output.append(f"  Preview: {f.read()[:200]}...")

        return "\n".join(output)
    except Exception as e:
        return f"Vault query error: {e}"
