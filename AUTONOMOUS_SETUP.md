# Autonomous Setup Guide for Mimi CLI

This guide enables an AI agent to set up the Mimi CLI environment autonomously on a new machine.

## Prerequisites
- Python 3.10+
- Git

## Step-by-Step Autonomous Setup

### 1. Clone the Repository
```bash
git clone https://github.com/kuumin/mimi-cli.git
cd mimi-cli
```

### 2. Configure Environment
Create a `.env` file in the project root. You must obtain the API keys from the user or a secure secret store.
```bash
cp .env.example .env
# Agent: Prompt the user to fill in DEEPSEEK_API_KEY, etc.
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Initialize Data Structure
The application automatically creates the necessary directories in `data/` on first run, but you can pre-verify:
```bash
mkdir -p data/sessions data/memories
```

### 5. Migration (Optional)
If the user has old Jan threads to migrate:
```bash
# Agent: Ensure JAN_THREADS_DIR in migration/migrate_jan.py is correct for the new OS
python3 migration/migrate_jan.py
```

### 6. Verify Installation
Run the help command to ensure bootstrapping works.
```bash
./mimi --help
```

## Agent Tips for Setup
- **Path Resolution**: The project uses `pathlib` for portability. Always use absolute paths when reading/writing files during setup.
- **Background Processes**: The `./mimi` script automatically starts the `mimi_memory_watcher.py` in the background. Ensure `pgrep` is available on the system.
- **Syncing**: If the user uses Obsidian, ensure the `VAULT_PATH` in `mimi_lib/config.py` is updated to point to the correct local vault location.
