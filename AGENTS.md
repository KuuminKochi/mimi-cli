# Agent Operational Guide for Mimi Zenith (v6.5)

This guide is intended for AI agents (Mimi, Opencode, Cursor, etc.) working in this repository. It outlines the modular architecture, development standards, and operational protocols for maintaining and extending Mimi Cyber-TTY.

## 1. Modular Architecture

Mimi is structured for high portability and modularity. Avoid bloating the root directory; most logic should reside in `mimi_lib/`.

- `mimi_lib/api/`: Handles communication with LLM providers (DeepSeek, OpenRouter, xAI).
    - `provider.py`: Centralized API caller with session persistence and fallback logic.
    - `deepseek.py`: Specialized analysis logic (personality evolution, diary, psych profiles).
- `mimi_lib/memory/`: 
    - `brain.py`: Core system prompt logic and keyword-based reminiscence.
    - `embeddings.py`: Semantic search utilities (OpenAI/OpenRouter embeddings).
    - `vault_indexer.py`: Manages semantic indexing of the user's Obsidian vault ("The Vault").
- `mimi_lib/skills/`: Specialized modular mindset blueprints (Engineering, Researcher, etc.).
- `mimi_lib/ui/`: All TTY interface logic (ANSI sequences, Vim-inspired input, Markdown printer).
    - `ansi.py`: Raw escape sequences for colors and cursor movement.
    - `printer.py`: Streaming Markdown renderer with support for thinking blocks.
    - `input.py`: Vim-inspired readline handler with history and multiline support.
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
- **Run Specific Test**: `pytest test_mimi_cli.py::TestANSIHelpers::test_clear_screen_output`
- **Run Specific Class**: `pytest test_mimi_cli.py::TestANSIHelpers`
- **Manual Verification**: Run `./mimi` to ensure the TTY interface initializes correctly.
- **Legacy Compatibility**: Tests use `unittest` structure; `python3 -m unittest test_mimi_cli.py` is also supported.

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
- **Docstrings**: Use triple double quotes (`"""`). Follow the Google Style for parameter descriptions.

### Naming Conventions
- **Variables & Functions**: `snake_case`.
- **Classes**: `PascalCase`.
- **Constants**: `UPPER_SNAKE_CASE` (defined in `mimi_lib/config.py`).
- **File Names**: `snake_case`.

### Error Handling
- **Tools**: NEVER raise exceptions that propagate to the main loop. Wrap logic in `try...except` and return a descriptive error string (prefixed with `Error:`).
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
   ```python
   @register_tool(
       "my_tool", 
       "Description of what it does", 
       {
           "type": "object", 
           "properties": {"param": {"type": "string"}}
       }
   )
   def my_tool(param: str) -> str:
       return f"Result: {param}"
   ```
3. Import the module in `mimi_lib/tools/__init__.py` or specifically in `mimi_lib/app.py`.
4. Ensure the tool returns a `str` or a JSON-serializable object.
5. If the tool modifies files in the Vault, ensure it triggers a background `vault_index`.

## 7. The Vault & RAG Integration

- **The Vault**: `~/Documents/kuumin/` is the source of truth for knowledge and thoughts.
- **Indexing**: `vault_indexer.py` manages the vector store. It uses incremental indexing based on `mtime`.
- **Context Injection**: Use `get_reminiscence` in `MimiApp` to provide context from the vault and session memory.
- **WikiLinks**: Always prefer `[[WikiLinks]]` for internal vault references.

## 8. Recursive Context Management

- **Summarization**: When conversation history exceeds 40 messages, the oldest 20 are summarized into a "Session Chronicle" block.
- **Deduplication**: Periodically prune short-term memories to remove redundancy.
- **Persistence**: Use `requests.Session()` for persistent AI connections to reduce latency.

## 9. UI & UX Standards
- **ANSI Colors**: Use the `Colors` class in `mimi_lib.utils.text`.
- **Layout**: Always calculate dynamic width using `get_layout(config)` to respect terminal resizing.
- **Thinking Blocks**: Use `StreamPrinter.process(content, reasoning=True)` to render thoughts in a distinct style (usually dim/italic).

## 10. Operational Protocols for Agents

1. **Atomic Commits**: Group related changes (e.g., a new tool and its registration) into a single commit.
2. **Always Push**: After successfully completing a task, staging changes, and committing, always run `git push origin main`.
3. **Safety First**: Before running destructive commands (`rm`, `git reset --hard`), verify the path and impact.
4. **Consistency**: Maintain the architectural boundary between `mimi_lib` (logic) and root (execution/entry).
5. **Proactive Skills**: If the task shifts to a specialized domain (Math, Research, Refactoring), load the corresponding Skill persona.
6. **Surgical Reads**: For large files, use `read_file` with `offset`, `limit`, or `pattern` instead of reading the whole file.

## 11. External Rules & Standards
- **Cursor/Copilot**: No specific rule files (`.cursorrules`, etc.) detected in project. Follow standard Python modular patterns and PEP 8 where not overridden by this guide.
- **DeepSeek Integration**: Use `mimi_lib/api/deepseek.py` for any logic requiring Chain-of-Thought or reasoning-specific parsing.

---
*Mimi Zenith v6.5 - Cyber-TTY System*
