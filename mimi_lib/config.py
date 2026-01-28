import os
from pathlib import Path
from dotenv import load_dotenv

# Path Discovery
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
DATA_DIR = PROJECT_ROOT / "data"
SESSION_DIR = DATA_DIR / "sessions"
MEMORY_DIR = DATA_DIR / "memories"

# Ensure directories exist
for d in [SESSION_DIR, MEMORY_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Native Storage Files (Replacing Jan dependencies)
MEMORY_ARCHIVE_FILE = MEMORY_DIR / "archive.json"
MEMORY_STORE_FILE = MEMORY_DIR / "active_store.json"
MEMORY_VECTORS_FILE = MEMORY_DIR / "vectors.json"
VAULT_VECTORS_FILE = MEMORY_DIR / "vault_vectors.json"
VAULT_INDEX_LOG = MEMORY_DIR / "vault_index_log.json"
PERSONA_CORE_FILE = MEMORY_DIR / "persona_core.json"
DIARY_STORE_FILE = MEMORY_DIR / "diary_store.json"
NOTES_STORE_FILE = MEMORY_DIR / "notes_store.json"
WORKING_SET_FILE = MEMORY_DIR / "working_set.json"
PROCESSED_LOG = MEMORY_DIR / "processed_ids.json"
COUNTER_FILE = MEMORY_DIR / "msg_counter.json"

# System Prompt Twin-Sync
LOCAL_PROMPT_FILE = DATA_DIR / "system_prompt.md"
VAULT_PROMPT_FILE = Path.home() / "Documents/kuumin/Mimi/SystemPrompt.md"

# Vault Integration
VAULT_PATH = Path.home() / "Documents/kuumin"
VAULT_SESSION_DIR = VAULT_PATH / "Mimi/Sessions"
OBSIDIAN_MEMORY_FILE = VAULT_PATH / "Mimi/LongTermMemory.md"
OBSIDIAN_DIARY_FILE = VAULT_PATH / "Mimi/Diary.md"
OBSIDIAN_NOTES_FILE = VAULT_PATH / "Mimi/Notes.md"

# Load Secrets
load_dotenv(PROJECT_ROOT / ".env")


def get_config():
    """Returns a dictionary of API keys and endpoints."""
    return {
        "deepseek_api_key": os.getenv("DEEPSEEK_API_KEY"),
        "openrouter_api_key": os.getenv("OPENROUTER_API_KEY"),
        "xai_api_key": os.getenv("XAI_API_KEY"),
        "openai_api_key": os.getenv("OPENAI_API_KEY"),
        "base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        "xai_base_url": os.getenv("XAI_BASE_URL", "https://api.x.ai/v1"),
        "openrouter_base_url": os.getenv(
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        ),
    }


AVAILABLE_MODELS = {
    "deepseek-chat": {
        "provider": "deepseek",
        "description": "Fast conversational model",
    },
    "deepseek-reasoner": {
        "provider": "deepseek",
        "description": "Chain-of-thought reasoning model",
    },
    "or/moonshotai/kimi-k2.5": {
        "provider": "openrouter",
        "description": "Moonshot AI multimodal model with agent capabilities",
    },
}
