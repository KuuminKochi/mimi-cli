# Agent Operational Guide for Mimi Zenith (v6.0)

This guide is intended for AI agents (Mimi, Opencode, Cursor, etc.) working in this repository. It outlines the modular architecture, development standards, and operational protocols for maintaining and extending Mimi Cyber-TTY.

## 1. Modular Architecture

Mimi is structured for high portability and modularity. Avoid bloating the root directory; most logic should reside in `mimi_lib/`.

- `mimi_lib/api/`: Handles communication with LLM providers (DeepSeek, OpenRouter, xAI).
- `mimi_lib/memory/`: 
    - `brain.py`: Core system prompt logic and keyword-based reminiscence.
    - `embeddings.py`: Semantic search utilities (OpenAI/OpenRouter embeddings).
    - `vault_indexer.py`: Manages semantic indexing of the user's Obsidian vault.
- `mimi_lib/ui/`: All TTY interface logic.
    - `ansi.py`: Low-level terminal escape sequences.
    - `input.py`: Vim-inspired input handling.
    - `printer.py`: Markdown-aware streaming output with reasoning support.
- `mimi_lib/tools/`: Extension point for Mimi's capabilities.
- `mimi_lib/utils/`: Shared helper functions for text, system info, and filesystem.
- `data/`: Local state storage (sessions, memories, vector indexes).

## 2. Environment & Data

- **Local Storage**: `data/memories/` contains persistent JSON stores for memories, notes, and vectors.
- **Obsidian Sync**: The "Vault Brain" automatically indexes the user's Obsidian vault at `~/Documents/kuumin/`.
- **Secrets**: Use a `.env` file at the root. Never hardcode API keys.
- **Portability**: All file paths MUST be derived from `mimi_lib.config.PROJECT_ROOT`.

## 3. Development Guidelines

### Code Style
- **Indentation**: 4 spaces.
- **Strings**: Prefer double quotes (`"`) for content, single quotes (`'`) for keys/identifiers.
- **Naming**: 
    - `snake_case` for functions, variables, and file names.
    - `PascalCase` for classes.
    - `UPPER_SNAKE_CASE` for constants in `config.py`.
- **Type Hinting**: Required for all function signatures (PEP 484).
- **Error Handling**: 
    - Tools should return a string error message rather than raising exceptions that crash the TTY.
    - Use `try...except` blocks in I/O and network operations.

### Thread Safety
- Mimi uses a streaming architecture. When implementing tools that print to stdout, wrap the output in `with app.print_lock:` if the tool is called during a generation. However, standard tool return values are handled safely by the `MimiApp` tool executor.

### Absolute Paths
- **Rule**: Never use relative paths like `open("../data/...")`.
- **Fix**: Import paths from `mimi_lib.config`:
  ```python
  from mimi_lib.config import MEMORY_DIR
  target_file = MEMORY_DIR / "my_data.json"
  ```

## 4. Extending Mimi (Adding Tools)

To add a new capability:
1. Create a module in `mimi_lib/tools/` (e.g., `research_tools.py`).
2. Use the `@register_tool` decorator:
   ```python
   from mimi_lib.tools.registry import register_tool

   @register_tool(
       "tool_name",
       "Clear description of what the tool does.",
       {
           "type": "object",
           "properties": {
               "arg1": {"type": "string", "description": "Arg description"}
           },
           "required": ["arg1"]
       }
   )
   def my_tool_func(arg1: str):
       # Logic here
       return "Result string"
   ```
3. Import the module in `mimi_lib/app.py` or `mimi_lib/tools/__init__.py` to ensure registration.

## 5. Build, Lint & Test

### Commands
- **Main Entry**: `./mimi` (Ensure it has `+x` permissions).
- **Format**: `ruff format .`
- **Lint**: `ruff check .`
- **Test (All)**: `pytest` or `python3 -m unittest discover`
- **Test (Single File)**: `pytest test_mimi_cli.py` or `python3 test_mimi_cli.py`
- **Sync Vault**: `python3 -c "from mimi_lib.memory.vault_indexer import index_vault; index_vault()"`

### Test Requirements
- New features should include a test in a new `test_*.py` file at the root or a `tests/` directory.
- Use `unittest.mock` for any network or hardware-dependent calls.

## 6. Obsidian Copilot Integration

Mimi is designed to be an Obsidian copilot. 
- **Vault Path**: Defined in `mimi_lib.config.VAULT_PATH`.
- **Indexing**: Uses `vault_indexer.py` to create a semantic map of notes.
- **RAG**: The `get_reminiscence` method in `MimiApp` queries the vault vector store (`vault_vectors.json`) on every turn to provide context.
- **Manual Sync**: User can run `/vault_index` in the TTY to refresh knowledge.

## 7. Operational Protocols for Agents

1. **Safety First**: Before running destructive bash commands (like `rm` or `git reset`), verify the target path.
2. **Context Awareness**: Always check `mimi_lib/config.py` first when adding new data storage requirements.
3. **Atomic Changes**: When editing files, keep changes localized to the relevant module.
4. **Verification**: After modifying core logic, run `python3 test_mimi_cli.py` to ensure TTY components still function.

---
*Mimi Zenith v6.0 - Cyber-TTY System*
