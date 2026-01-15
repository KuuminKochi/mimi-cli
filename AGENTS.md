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

## 2. Development Workflow

### Build & Lint
- **Format**: `ruff format .` (Ensures Black-compatible formatting).
- **Lint**: `ruff check .` (Catches syntax errors, unused imports, etc.).
- **Fix**: `ruff check . --fix` (Automatically fixes common issues).

### Testing
- **Run All Tests**: `pytest`
- **Run Single File**: `pytest test_mimi_cli.py`
- **Run Specific Test**: `pytest test_mimi_cli.py::TestMimiApp::test_handle_command`
- **Manual Verification**: Run `./mimi` to ensure the TTY interface initializes correctly.

## 3. Code Style Guidelines

### Imports
Organize imports into three sections separated by a newline:
1. Standard library imports (e.g., `os`, `sys`, `json`).
2. Third-party imports (e.g., `requests`, `dotenv`, `typing`).
3. Local project imports (e.g., `from mimi_lib.config import ...`).
Within each group, imports should be sorted alphabetically.

### Formatting & Style
- **Indentation**: 4 spaces.
- **Line Length**: 88 characters (Black standard).
- **Strings**: Use double quotes (`"`) for user-facing content and long strings; use single quotes (`'`) for dictionary keys and internal identifiers.
- **Type Hinting**: Required for all function signatures and class attributes. Use `typing.List`, `typing.Dict`, `typing.Optional`, etc.

### Naming Conventions
- **Variables & Functions**: `snake_case`.
- **Classes**: `PascalCase`.
- **Constants**: `UPPER_SNAKE_CASE` (defined in `mimi_lib/config.py`).
- **File Names**: `snake_case`.

### Error Handling
- **Tools**: NEVER raise exceptions that propagate to the main loop. Wrap logic in `try...except` and return a descriptive error string.
- **API/IO**: Use specific exception handling (e.g., `requests.exceptions.RequestException`) and log errors to `data/mimi_api_debug.log`.
- **Validation**: Use `json.loads` safely within `try` blocks when processing LLM outputs.

## 4. Environment & Path Management

- **Absolute Paths**: Never use relative paths like `open("../data/...")`.
- **Path Registry**: Use `mimi_lib/config.py` for all file references. Import paths like `SESSION_DIR`, `MEMORY_DIR`, or `PROJECT_ROOT`.
- **Example**:
  ```python
  from mimi_lib.config import DATA_DIR
  config_path = DATA_DIR / "config.json"
  ```
- **Secrets**: Store all keys in a `.env` file. Use `os.getenv` or `load_dotenv`. Never commit real keys.

## 5. Thread Safety & TTY Protocols

- **Output Locking**: Mimi uses a streaming architecture. If a tool needs to print directly to the terminal, wrap it in `with app.print_lock:` to prevent interweaving with the AI's response.
- **Non-Interactive**: Avoid using `input()` in tools. Use the `VimInput` handler if interaction is required, though most tool executions should be autonomous.

## 6. Extending Mimi (Adding Tools)

To add a new capability:
1. Create a module in `mimi_lib/tools/`.
2. Use the `@register_tool` decorator with a clear JSON schema for parameters.
3. Import the module in `mimi_lib/app.py` or `mimi_lib/tools/__init__.py`.
4. Ensure the tool returns a `str` or a JSON-serializable object.

## 7. Obsidian & RAG Integration

- **Vault Path**: `~/Documents/kuumin/` is the source of truth for knowledge.
- **Indexing**: `vault_indexer.py` manages the vector store.
- **Context Injection**: Use `get_reminiscence` in `MimiApp` to provide context from the vault and session memory on every turn.

## 8. Operational Protocols for Agents

1. **Atomic Commits**: Group related changes (e.g., a new tool and its registration) into a single commit.
2. **Always Push**: After successfully completing a task, staging changes, and committing, always run `git push origin main`.
3. **Safety First**: Before running destructive commands (`rm`, `git reset --hard`), verify the path and impact.
4. **Consistency**: Maintain the architectural boundary between `mimi_lib` (logic) and root (execution/entry).

---
*Mimi Zenith v6.0 - Cyber-TTY System*
