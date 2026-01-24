#!/usr/bin/env python3
"""
Mimi Diary Cron - Updated for Mimi CLI (Modular)

Scans conversation logs and generates daily diary entries using deepseek-reasoner.
Data Sources:
    1. Sessions Dir (mimi_lib.config.SESSION_DIR)
    2. Jan Threads (Legacy)

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

# Ensure mimi_lib is in path
sys.path.append("/home/kuumin/Projects/mimi-cli")

try:
    from mimi_lib.config import (
        SESSION_DIR,
        DIARY_STORE_FILE,
        MEMORY_STORE_FILE,
        get_config
    )
    from mimi_lib.memory.brain import (
        load_system_prompt,
        save_memory,
        load_diary,
        save_diary_entry
    )
    from mimi_lib.api.provider import call_api
except ImportError as e:
    logger.error(f"Failed to import mimi_lib: {e}")
    sys.exit(1)

# Legacy Jan Threads Path
THREADS_DIR = "/home/kuumin/.var/app/ai.jan.Jan/data/Jan/data/threads"

def parse_session_file(filepath: str) -> List[Dict[str, any]]:
    messages = []
    if not os.path.exists(filepath):
        return messages

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        pattern = r"\*\*(\w+)\*\* \((\d{2}:\d{2})\):\s*(.+?)(?=\n\*\*|\Z)"
        matches = re.findall(pattern, content, re.DOTALL)

        for role, timestamp, msg_content in matches:
            msg_content = msg_content.strip()
            if not msg_content:
                continue

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
    user_msgs = []
    assistant_msgs = []

    if not SESSION_DIR.exists():
        return user_msgs, assistant_msgs

    try:
        for filepath in SESSION_DIR.glob("*.md"):
            messages = parse_session_file(filepath)

            for msg in messages:
                # Approximate date check via file mtime
                try:
                    file_mtime = filepath.stat().st_mtime
                    file_date = datetime.fromtimestamp(file_mtime).strftime("%Y-%m-%d")
                    if file_date != target_date:
                        continue
                except:
                    continue

                if msg["role"] == "user":
                    user_msgs.append(msg["content"])
                elif msg["role"] == "assistant":
                    assistant_msgs.append(msg["content"])

    except Exception as e:
        logger.error(f"Error reading sessions: {e}")

    return user_msgs, assistant_msgs

def get_messages_from_threads(target_date: str) -> Tuple[List[str], List[str]]:
    user_msgs = []
    assistant_msgs = []

    if not os.path.exists(THREADS_DIR):
        return user_msgs, assistant_msgs

    try:
        for tf in glob.glob(os.path.join(THREADS_DIR, "*/messages.jsonl")):
            with open(tf, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip(): continue
                    try:
                        msg = json.loads(line)
                        ts = msg.get("created_at") or msg.get("timestamp")
                        if not ts: continue
                        if ts > 1000000000000: ts = ts / 1000
                        
                        msg_date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                        if msg_date != target_date: continue

                        content = ""
                        msg_content = msg.get("content")
                        if isinstance(msg_content, list):
                            for item in msg_content:
                                if item.get("type") == "text":
                                    content += item.get("text", {}).get("value", "")
                        elif isinstance(msg_content, str):
                            content = msg_content

                        role = msg.get("role")
                        if role == "user": user_msgs.append(content)
                        elif role == "assistant": assistant_msgs.append(content)

                    except: continue

    except Exception as e:
        logger.error(f"Error reading threads: {e}")

    return user_msgs, assistant_msgs

def get_all_chat_dates() -> Set[str]:
    dates = set()
    if SESSION_DIR.exists():
        try:
            for filepath in SESSION_DIR.glob("*.md"):
                file_mtime = filepath.stat().st_mtime
                file_date = datetime.fromtimestamp(file_mtime).strftime("%Y-%m-%d")
                dates.add(file_date)
        except Exception as e:
            logger.error(f"Error scanning sessions: {e}")

    if os.path.exists(THREADS_DIR):
        try:
            for tf in glob.glob(os.path.join(THREADS_DIR, "*/messages.jsonl")):
                with open(tf, "r", encoding="utf-8") as f:
                    for line in f:
                        if not line.strip(): continue
                        try:
                            msg = json.loads(line)
                            ts = msg.get("created_at") or msg.get("timestamp")
                            if ts:
                                if ts > 1000000000000: ts = ts / 1000
                                dates.add(datetime.fromtimestamp(ts).strftime("%Y-%m-%d"))
                        except: continue
        except Exception as e:
            logger.error(f"Error scanning threads: {e}")
    return dates

def interleave_messages(user_msgs: List[str], assistant_msgs: List[str]) -> List[Dict[str, str]]:
    conversation = []
    max_len = min(len(user_msgs), len(assistant_msgs))
    for i in range(max_len):
        conversation.append({"role": "user", "content": user_msgs[i]})
        conversation.append({"role": "assistant", "content": assistant_msgs[i]})
    
    # Append extras
    for i in range(max_len, len(user_msgs)):
        conversation.append({"role": "user", "content": user_msgs[i]})
    for i in range(max_len, len(assistant_msgs)):
        conversation.append({"role": "assistant", "content": assistant_msgs[i]})
    return conversation

def generate_diary_entry(target_date: str, user_msgs: List[str], assistant_msgs: List[str]) -> Optional[str]:
    conversation = interleave_messages(user_msgs, assistant_msgs)
    if not conversation: return None

    context_parts = []
    total_len = 0
    for msg in reversed(conversation):
        msg_text = f"{msg['role'].title()}: {msg['content']}"
        if total_len + len(msg_text) > 5000: break
        context_parts.insert(0, msg_text)
        total_len += len(msg_text)
    
    context = "\n".join(context_parts)
    system_prompt = load_system_prompt()
    if not system_prompt:
        system_prompt = "You are Mimi, an 18yo Malaysian INTJ student."

    user_prompt = f"""Today's Conversation ({target_date}):
{context}

You are Mimi. Write a personal diary entry about today's conversation with Kuumin. 
Start with "Dear Diary,". Keep it under 300 words."""

    try:
        logger.info(f"Generating diary for {target_date}...")
        res = call_api(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            model="deepseek-reasoner",
            stream=False
        )
        if res and res.status_code == 200:
            content = res.json()["choices"][0]["message"]["content"]
            return content
        else:
            logger.error(f"API Error for {target_date}")
            return None
    except Exception as e:
        logger.error(f"Error generating diary: {e}")
        return None

def process_date(target_date: str):
    logger.info(f"Processing: {target_date}")
    u1, a1 = get_messages_from_sessions(target_date)
    u2, a2 = get_messages_from_threads(target_date)
    
    # Merge, prioritize sessions
    user_msgs = u1 + [m for m in u2 if m not in u1]
    assistant_msgs = a1 + [m for m in a2 if m not in a1]

    if not user_msgs:
        logger.info("No messages found.")
        return

    diary_content = generate_diary_entry(target_date, user_msgs, assistant_msgs)
    if diary_content:
        # Save to Diary Store
        save_diary_entry(diary_content, target_date)
        logger.info(f"Saved diary for {target_date}")

        # Add to Memory
        save_memory(f"Diary Entry ({target_date}): {diary_content}", category="Mimi")
        logger.info("Added diary reflection to memory.")

def main():
    logger.info("=== Mimi Diary Cron (Modular) ===")
    all_dates = get_all_chat_dates()
    if not all_dates: return

    diary_store = load_diary()
    existing_dates = set(entry.get("date") for entry in diary_store)
    today_str = datetime.now().strftime("%Y-%m-%d")

    targets = [d for d in sorted(all_dates) if d not in existing_dates or d == today_str]
    
    for date_str in targets:
        process_date(date_str)

if __name__ == "__main__":
    main()
