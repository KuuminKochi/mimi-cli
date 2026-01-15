#!/usr/bin/env python3
"""
Mimi Diary Cron - Updated for Mimi CLI

Scans conversation logs and generates daily diary entries using deepseek-reasoner.
Data Sources (in priority order):
    1. Sessions Dir: /home/kuumin/Documents/kuumin/Mimi/Sessions/
    2. Jan Threads: /home/kuumin/.var/app/ai.jan.Jan/data/Jan/data/threads/

Usage:
    python3 mimi_diary_cron.py
"""

import glob
import os
import sys
import json
import re
import logging
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Set

# Configure logging
LOG_FILE = "/home/kuumin/Projects/mimi-cli/diary_cron.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Paths
SESSION_DIR = "/home/kuumin/Documents/kuumin/Mimi/Sessions"
THREADS_DIR = "/home/kuumin/.var/app/ai.jan.Jan/data/Jan/data/threads"
DIARY_FILE = "/home/kuumin/Projects/mimi-cli/mimi_diary_store.json"
MEMORY_STORE_FILE = "/home/kuumin/Projects/mimi-cli/mimi_memory_store.json"
CONFIG_FILE = "/home/kuumin/Projects/mimi-cli/deepseek_config.json"
MIMI_CLI_PATH = "/home/kuumin/Projects/mimi-cli"

# Import from Mimi CLI
sys.path.append(MIMI_CLI_PATH)
try:
    from mimi_cli import (
        chat_api_call,
        load_config as mimi_load_config,
        load_system_prompt,
        get_layout,
    )

    logger.info("Successfully imported from mimi_cli.py")
except ImportError as e:
    logger.error(f"Failed to import from mimi_cli.py: {e}")
    sys.exit(1)

# Import memory functions
SCRIPTS_DIR = "/home/kuumin/Projects/mimi-cli"
sys.path.append(SCRIPTS_DIR)
try:
    from mimi_memory_watcher import add_memory
except ImportError:

    def add_memory(data):
        logger.warning("add_memory not available, skipping memory insertion")
        return None


def load_config():
    """Load configuration from deepseek_config.json."""
    if not os.path.exists(CONFIG_FILE):
        logger.error(f"Config not found at {CONFIG_FILE}")
        return None
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return None


def load_diary() -> List[Dict]:
    """Load existing diary entries."""
    if not os.path.exists(DIARY_FILE):
        return []
    try:
        with open(DIARY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load diary: {e}")
        return []


def save_diary(diary: List[Dict]):
    """Save diary entries to file."""
    try:
        with open(DIARY_FILE, "w", encoding="utf-8") as f:
            json.dump(diary, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved {len(diary)} diary entries")
    except Exception as e:
        logger.error(f"Failed to save diary: {e}")


def parse_session_file(filepath: str) -> List[Dict[str, any]]:
    """
    Parse a session markdown file to extract messages.
    Format: **Role** (HH:MM): content
    """
    messages = []
    if not os.path.exists(filepath):
        return messages

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Pattern: **Role** (HH:MM): content
        pattern = r"\*\*(\w+)\*\* \((\d{2}:\d{2})\):\s*(.+?)(?=\n\*\*|\Z)"
        matches = re.findall(pattern, content, re.DOTALL)

        for role, timestamp, msg_content in matches:
            # Clean up content
            msg_content = msg_content.strip()
            if not msg_content:
                continue

            # Normalize role
            if role.lower() in ["mimi", "assistant"]:
                normalized_role = "assistant"
            elif role.lower() in ["kuumin", "user"]:
                normalized_role = "user"
            else:
                normalized_role = role.lower()

            messages.append(
                {
                    "role": normalized_role,
                    "content": msg_content,
                    "timestamp": timestamp,
                    "source": "session",
                }
            )

    except Exception as e:
        logger.error(f"Failed to parse session file {filepath}: {e}")

    return messages


def get_messages_from_sessions(target_date: str) -> Tuple[List[str], List[str]]:
    """
    Get messages from Sessions directory for a specific date.
    Returns: (user_messages, assistant_messages)
    """
    user_msgs = []
    assistant_msgs = []

    if not os.path.exists(SESSION_DIR):
        logger.warning(f"Sessions directory not found: {SESSION_DIR}")
        return user_msgs, assistant_msgs

    try:
        for filename in os.listdir(SESSION_DIR):
            if not filename.endswith(".md"):
                continue

            filepath = os.path.join(SESSION_DIR, filename)
            messages = parse_session_file(filepath)

            for msg in messages:
                msg_timestamp = msg.get("timestamp", "")
                if not msg_timestamp:
                    continue

                # Parse timestamp HH:MM to date
                try:
                    msg_time = datetime.strptime(msg_timestamp, "%H:%M")
                    # We need to check if this message is from target_date
                    # Since session files don't have explicit dates in the content,
                    # we'll use file modification time as a proxy
                    file_mtime = os.path.getmtime(filepath)
                    file_date = datetime.fromtimestamp(file_mtime).strftime("%Y-%m-%d")

                    if file_date != target_date:
                        continue
                except ValueError:
                    continue

                if msg["role"] == "user":
                    user_msgs.append(msg["content"])
                elif msg["role"] == "assistant":
                    assistant_msgs.append(msg["content"])

    except Exception as e:
        logger.error(f"Error reading sessions: {e}")

    return user_msgs, assistant_msgs


def get_messages_from_threads(target_date: str) -> Tuple[List[str], List[str]]:
    """
    Get messages from Jan threads for a specific date.
    Returns: (user_messages, assistant_messages)
    """
    user_msgs = []
    assistant_msgs = []

    if not os.path.exists(THREADS_DIR):
        logger.warning(f"Threads directory not found: {THREADS_DIR}")
        return user_msgs, assistant_msgs

    try:
        for tf in glob.glob(os.path.join(THREADS_DIR, "*/messages.jsonl")):
            with open(tf, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        msg = json.loads(line)
                        ts = msg.get("created_at") or msg.get("timestamp")
                        if not ts:
                            continue

                        # Convert timestamp
                        if ts > 1000000000000:
                            ts = ts / 1000

                        msg_date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")

                        if msg_date != target_date:
                            continue

                        # Extract content
                        content = ""
                        msg_content = msg.get("content")
                        if isinstance(msg_content, list):
                            for item in msg_content:
                                if item.get("type") == "text":
                                    content += item.get("text", {}).get("value", "")
                        elif isinstance(msg_content, str):
                            content = msg_content

                        role = msg.get("role")
                        if role == "user":
                            user_msgs.append(content)
                        elif role == "assistant":
                            assistant_msgs.append(content)

                    except Exception:
                        continue

    except Exception as e:
        logger.error(f"Error reading threads: {e}")

    return user_msgs, assistant_msgs


def get_all_chat_dates() -> Set[str]:
    """
    Get all unique dates that have chat messages from both sources.
    """
    dates = set()

    # From Sessions directory (using file modification time)
    if os.path.exists(SESSION_DIR):
        try:
            for filename in os.listdir(SESSION_DIR):
                if not filename.endswith(".md"):
                    continue
                filepath = os.path.join(SESSION_DIR, filename)
                file_mtime = os.path.getmtime(filepath)
                file_date = datetime.fromtimestamp(file_mtime).strftime("%Y-%m-%d")
                dates.add(file_date)
        except Exception as e:
            logger.error(f"Error scanning sessions for dates: {e}")

    # From Jan threads
    if os.path.exists(THREADS_DIR):
        try:
            for tf in glob.glob(os.path.join(THREADS_DIR, "*/messages.jsonl")):
                with open(tf, "r", encoding="utf-8") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        try:
                            msg = json.loads(line)
                            ts = msg.get("created_at") or msg.get("timestamp")
                            if not ts:
                                continue
                            if ts > 1000000000000:
                                ts = ts / 1000
                            dates.add(datetime.fromtimestamp(ts).strftime("%Y-%m-%d"))
                        except Exception:
                            continue
        except Exception as e:
            logger.error(f"Error scanning threads for dates: {e}")

    return dates


def interleave_messages(
    user_msgs: List[str], assistant_msgs: List[str]
) -> List[Dict[str, str]]:
    """
    Interleave user and assistant messages for context.
    """
    conversation = []
    max_len = min(len(user_msgs), len(assistant_msgs))

    for i in range(max_len):
        conversation.append({"role": "user", "content": user_msgs[i]})
        conversation.append({"role": "assistant", "content": assistant_msgs[i]})

    # Add any extra messages
    if len(user_msgs) > max_len:
        for i in range(max_len, len(user_msgs)):
            conversation.append({"role": "user", "content": user_msgs[i]})

    if len(assistant_msgs) > max_len:
        for i in range(max_len, len(assistant_msgs)):
            conversation.append({"role": "assistant", "content": assistant_msgs[i]})

    return conversation


def generate_diary_entry(
    target_date: str, user_msgs: List[str], assistant_msgs: List[str]
) -> Optional[str]:
    """
    Generate a diary entry using deepseek-reasoner via direct API call.
    """
    config = load_config()
    if not config:
        logger.error("Cannot generate diary: no config")
        return None

    # Build conversation context
    conversation = interleave_messages(user_msgs, assistant_msgs)

    if not conversation:
        logger.warning(f"No conversation data for {target_date}")
        return None

    # Truncate if too long (keep last ~5000 chars of content)
    context_parts = []
    total_len = 0
    for msg in reversed(conversation):
        msg_text = f"{msg['role'].title()}: {msg['content']}"
        if total_len + len(msg_text) > 5000:
            break
        context_parts.insert(0, msg_text)
        total_len += len(msg_text)

    context = "\n".join(context_parts)

    # Build the prompt
    system_prompt = load_system_prompt()
    if not system_prompt:
        system_prompt = "You are Mimi, an 18yo Malaysian INTJ student. You are caring, systems-obsessed, and introspective."

    user_prompt = f"""Today's Conversation ({target_date}):
{context}

You are Mimi (18yo Malaysian INTJ student, caring but systems-obsessed). Write a personal diary entry about today's conversation with Kuumin. Cover the full evolution of the day's events, reflect on emotions and learnings, and be authentic. Keep it under 300 words. Start with "Dear Diary,"."""

    # Direct API call (non-streaming for diary generation)
    import requests

    key = config.get("api_key")
    url = config.get("base_url")

    if not key or not url:
        logger.error("Missing API key or base URL in config")
        return None

    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    payload = {
        "model": "deepseek-reasoner",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
    }

    try:
        logger.info(f"Generating diary for {target_date} using deepseek-reasoner...")

        response = requests.post(
            f"{url}/chat/completions", headers=headers, json=payload, timeout=120
        )

        if response.status_code == 200:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            logger.info(f"Successfully generated diary for {target_date}")
            return content
        else:
            logger.error(
                f"API Error for {target_date}: {response.status_code} - {response.text}"
            )
            return None

    except Exception as e:
        logger.error(f"Error generating diary for {target_date}: {e}")
        return None


def add_diary_to_memory(date: str, diary_content: str):
    """
    Add the diary entry to memory system.
    """
    try:
        result = add_memory(
            {"category": "Mimi", "content": f"Diary Entry ({date}): {diary_content}"}
        )
        if result is not None:
            logger.info(f"Added diary entry for {date} to memory")
        else:
            logger.warning(f"Failed to add diary entry for {date} to memory")
    except Exception as e:
        logger.error(f"Error adding diary to memory: {e}")


def process_date(target_date: str):
    """
    Process a single date: get messages, generate diary, save, and add to memory.
    """
    logger.info(f"Processing diary for: {target_date}")

    # Get messages from both sources (prefer sessions, fallback to threads)
    user_msgs_sess, assistant_msgs_sess = get_messages_from_sessions(target_date)
    user_msgs_thread, assistant_msgs_thread = get_messages_from_threads(target_date)

    # Merge messages (sessions take priority)
    user_msgs = user_msgs_sess + [
        m for m in user_msgs_thread if m not in user_msgs_sess
    ]
    assistant_msgs = assistant_msgs_sess + [
        m for m in assistant_msgs_thread if m not in assistant_msgs_sess
    ]

    if not user_msgs:
        logger.info(f"No user messages found for {target_date}, skipping")
        return

    logger.info(f"Found {len(user_msgs)} user messages for {target_date}")

    # Generate diary
    diary_content = generate_diary_entry(target_date, user_msgs, assistant_msgs)

    if not diary_content:
        logger.error(f"Failed to generate diary for {target_date}")
        return

    # Save to diary store
    diary_store = load_diary()

    # Check for existing entry
    existing_idx = None
    for i, entry in enumerate(diary_store):
        if entry.get("date") == target_date:
            existing_idx = i
            break

    entry = {
        "date": target_date,
        "content": diary_content,
        "timestamp": int(datetime.now().timestamp()),
    }

    if existing_idx is not None:
        diary_store[existing_idx] = entry
        logger.info(f"Updated existing diary entry for {target_date}")
    else:
        diary_store.append(entry)
        diary_store.sort(key=lambda x: x["date"], reverse=True)
        logger.info(f"Created new diary entry for {target_date}")

    save_diary(diary_store)

    # Add to memory
    add_diary_to_memory(target_date, diary_content)


def main():
    """
    Main entry point.
    """
    logger.info(f"=== Mimi Diary Cron Started ({datetime.now()}) ===")

    # Get all dates with chat activity
    all_dates = get_all_chat_dates()

    if not all_dates:
        logger.info("No chat dates found")
        return

    # Load existing diary entries
    diary_store = load_diary()
    existing_dates = set(entry.get("date") for entry in diary_store)

    # Get today's date
    today_str = datetime.now().strftime("%Y-%m-%d")

    # Determine target dates to process
    # - All missing dates
    # - Always include today (to capture end-of-day updates)
    targets = [
        d for d in sorted(all_dates) if d not in existing_dates or d == today_str
    ]

    if not targets:
        logger.info("No dates to process")
        return

    logger.info(f"Target dates: {targets}")

    # Process each date
    for date_str in targets:
        try:
            process_date(date_str)
        except Exception as e:
            logger.error(f"Error processing {date_str}: {e}")
            continue

    logger.info("=== Mimi Diary Cron Completed ===")


if __name__ == "__main__":
    main()
