import time
import json
import os
import subprocess
from datetime import datetime, timedelta
import glob
import sys
import uuid

# Import Deepseek Integration
if "/home/kuumin/Projects/mimi-cli" not in sys.path:
    sys.path.append("/home/kuumin/Projects/mimi-cli")
try:
    from mimi_lib.api import deepseek as mimi_deepseek_integration
    from mimi_lib.memory import embeddings as mimi_embeddings
except ImportError:
    mimi_deepseek_integration = None
    mimi_embeddings = None

from mimi_lib.memory.brain import load_json, save_json, save_memory, add_note, delete_note

from mimi_lib.config import (
    SESSION_DIR, MEMORY_ARCHIVE_FILE, MEMORY_STORE_FILE, PERSONA_CORE_FILE,
    DIARY_STORE_FILE, NOTES_STORE_FILE, PROCESSED_LOG, COUNTER_FILE,
    OBSIDIAN_MEMORY_FILE, OBSIDIAN_DIARY_FILE, OBSIDIAN_NOTES_FILE,
    LOCAL_PROMPT_FILE as OBSIDIAN_PROMPT_FILE # Map local prompt file for sync
)

# Paths for Jan (Keep for legacy sync if needed)
THREADS_DIR = "/home/kuumin/.var/app/ai.jan.Jan/data/Jan/data/threads"
ASSISTANT_FILE = (
    "/home/kuumin/.var/app/ai.jan.Jan/data/Jan/data/assistants/s4sxg/assistant.json"
)

# Constants
DEVICE_ID = "9aa8c0220d56428eb3114d3e7b60dce8"
COMPRESSION_THRESHOLD = 32
PROFILE_INTERVAL = 20
INACTIVITY_THRESHOLD = 600  # 10 minutes in seconds

# Global state
last_activity_time = time.time()
synthesis_pending = False
session_messages = {"user": [], "assistant": []}

# Obsidian Configuration
OBSIDIAN_COPILOT_CONFIG = (
    "/home/kuumin/Documents/kuumin/.obsidian/plugins/copilot/data.json"
)



def send_notification(message):
    try:
        subprocess.run(
            ["kdeconnect-cli", "-d", DEVICE_ID, "--ping-msg", message],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except:
        pass


def save_json_with_export(path, data):
    save_json(path, data)
    # Trigger exports based on file type
    if path == MEMORY_STORE_FILE:
        export_memories_to_obsidian(data)
    elif path == NOTES_STORE_FILE:
        export_notes_to_obsidian(data)


def export_memories_to_obsidian(memories):
    try:
        os.makedirs(os.path.dirname(OBSIDIAN_MEMORY_FILE), exist_ok=True)

        # Monthly Archiving Logic
        today = datetime.now()
        if today.day == 1:
            # Check if already archived this month
            archive_dir = os.path.join(os.path.dirname(OBSIDIAN_MEMORY_FILE), "Archive")
            os.makedirs(archive_dir, exist_ok=True)
            last_month = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
            archive_path = os.path.join(archive_dir, f"Memory_{last_month}.md")
            if os.path.exists(OBSIDIAN_MEMORY_FILE) and not os.path.exists(
                archive_path
            ):
                import shutil

                shutil.copy2(OBSIDIAN_MEMORY_FILE, archive_path)
                print(f"[Maintenance] Archived last month's log to {archive_path}")

        # Sort and categorize for Markdown
        memories.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        # Categories
        cats = {"Events": [], "Mimi": [], "Kuumin": [], "Others": []}
        for m in memories:
            c = m.get("category", "Kuumin")
            if c not in cats:
                c = "Kuumin"
            cats[c].append(f"- **[{m.get('timestamp', '')}]** {m.get('content', '')}")

        md_content = "# Mimi's Long-Term Memory\n\n"
        md_content += "> Auto-synced from Jan. Do not edit manually.\n\n"

        for cat_name, items in cats.items():
            if items:
                md_content += f"## {cat_name}\n"
                md_content += "\n".join(items) + "\n\n"

        with open(OBSIDIAN_MEMORY_FILE, "w", encoding="utf-8") as f:
            f.write(md_content)

    except Exception as e:
        print(f"Obsidian export failed: {e}")


def export_diary_to_obsidian():
    try:
        if not os.path.exists(DIARY_STORE_FILE):
            return
        diaries = load_json(DIARY_STORE_FILE, [])
        diaries.sort(key=lambda x: x.get("date", ""), reverse=True)

        md_content = "# Mimi's Diary\n\n"
        md_content += "> Auto-synced from Jan. Private reflections.\n\n"

        for entry in diaries:
            md_content += f"## {entry.get('date')}\n\n"
            md_content += f"{entry.get('content')}\n\n"
            md_content += "---\n\n"

        os.makedirs(os.path.dirname(OBSIDIAN_DIARY_FILE), exist_ok=True)
        with open(OBSIDIAN_DIARY_FILE, "w", encoding="utf-8") as f:
            f.write(md_content)

    except Exception as e:
        print(f"Obsidian diary export failed: {e}")


def export_notes_to_obsidian(notes=None):
    try:
        if notes is None:
            notes = load_json(NOTES_STORE_FILE, [])

        # Sort by priority (High -> Medium -> Low) then timestamp
        priority_map = {"High": 3, "Medium": 2, "Low": 1}
        notes.sort(
            key=lambda x: (
                priority_map.get(x.get("priority", "Medium"), 1),
                x.get("timestamp", ""),
            ),
            reverse=True,
        )

        md_content = "# Mimi's Active Notes\n\n"
        md_content += "> Temporary notes, plans, and reminders. Managed by Mimi.\n\n"

        for note in notes:
            tags = " ".join([f"#{t}" for t in note.get("tags", [])])
            md_content += (
                f"### {note.get('timestamp')} [{note.get('priority', 'Medium')}]\n"
            )
            md_content += f"{note.get('content')}\n"
            if tags:
                md_content += f"*{tags}*\n"
            md_content += f"\n`ID: {note.get('id')}`\n\n---\n"

        os.makedirs(os.path.dirname(OBSIDIAN_NOTES_FILE), exist_ok=True)
        with open(OBSIDIAN_NOTES_FILE, "w", encoding="utf-8") as f:
            f.write(md_content)

    except Exception as e:
        print(f"Obsidian notes export failed: {e}")


def generate_memory_section():
    # 0. Load Persona Core
    persona = load_json(PERSONA_CORE_FILE, {"narrative": "I am Mimi."})
    persona_narrative = persona.get("narrative", "I am Mimi.")

    # 1. Load Recent Memories (Keep this very light, rely on RAG)
    memories = load_json(MEMORY_STORE_FILE, [])
    # Sort memories by timestamp (newest first for prompt context)
    memories.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    recent_memories = memories[:5] if memories else []

    memory_text = ""
    for m in reversed(recent_memories):  # Print in chronological order for the block
        ts = m.get("timestamp", "Unknown")
        cat = m.get("category", "General")
        content = m.get("content", "")
        memory_text += f"\n- [{ts}] ({cat}) {content}"

    # 2. Load Notes
    notes = load_json(NOTES_STORE_FILE, [])
    notes_text = ""
    if notes:
        notes_text = "\n**ACTIVE NOTES / PLANS:**"
        for n in notes:
            priority = n.get("priority", "Medium")
            notes_text += f"\n- [{priority}] {n.get('content')} (ID: {n.get('id')[:8]})"

    return f"""**Mimi's Core Identity & Persona:**
{persona_narrative}

**Cognitive Architecture & Memory System**
The user is ALWAYS 'Kuumin'. You have a permanent "Intuition" system that automatically pulls relevant history into your thoughts based on the current topic.

**OPERATIONAL GUIDE:**
1. **Long-Term Memory:** Use `add_memory` for permanent facts or significant user preferences.
2. **Active Notes:** Use `add_note` for current plans, tasks, or context to "hold" for next time.
3. **Intuition:** Rely on the [Reminiscence] block provided in your context to show continuity and emotional growth.

{notes_text}

**Active Context (Recent Highlights):**{memory_text if memory_text else "\n- No recent highlights."}"""


def migrate_categories():
    memories = load_json(MEMORY_STORE_FILE, [])
    uncategorized = [m for m in memories if "category" not in m]

    if uncategorized:
        print(f"Migrating {len(uncategorized)} memories to categories...")
        try:
            import mimi_deepseek_integration

            # Process in chunks of 20 to avoid token limits
            chunk_size = 20
            for i in range(0, len(uncategorized), chunk_size):
                chunk = uncategorized[i : i + chunk_size]
                contents = [m["content"] for m in chunk]
                classified = mimi_deepseek_integration.classify_memories(contents)

                if classified:
                    # Update original memories
                    for m_item in chunk:
                        # Find matching classified item by content match (simple heuristic)
                        for c_item in classified:
                            if c_item["content"] == m_item["content"]:
                                m_item["category"] = c_item["category"]
                                break
                        # Fallback default
                        if "category" not in m_item:
                            m_item["category"] = "Kuumin"

            save_json_with_export(MEMORY_STORE_FILE, memories)
            print("Migration complete.")
        except Exception as e:
            print(f"Migration failed: {e}")


def sync_instructions_with_store():
    try:
        # 1. Determine Base Instructions (Priority: Obsidian File > Jan > Default)
        base_instructions = ""

        if os.path.exists(OBSIDIAN_PROMPT_FILE):
            with open(OBSIDIAN_PROMPT_FILE, "r", encoding="utf-8") as f:
                base_instructions = f.read().strip()

        # Fallback to Jan if Obsidian file is missing (or empty)
        if not base_instructions and os.path.exists(ASSISTANT_FILE):
            with open(ASSISTANT_FILE, "r", encoding="utf-8") as f:
                global_data = json.load(f)
            raw_inst = global_data.get("instructions", "")

            # Robustly clean up any previous memory/identity injections
            markers = [
                "**Mimi's Core Identity",
                "**Long-Term Memory",
                "**Cognitive Architecture",
                "**Current Memories",
            ]
            base_instructions = raw_inst
            for marker in markers:
                if marker in base_instructions:
                    base_instructions = base_instructions.split(marker)[0].strip()

        # 2. Generate Dynamic Section
        memory_section = generate_memory_section()
        final_instructions = f"{base_instructions}\n\n{memory_section}"

        # 3. Push to Jan (Global)
        if os.path.exists(ASSISTANT_FILE):
            with open(ASSISTANT_FILE, "r", encoding="utf-8") as f:
                global_data = json.load(f)

            if global_data.get("instructions") != final_instructions:
                global_data["instructions"] = final_instructions
                save_json(ASSISTANT_FILE, global_data)
                print("Synced instructions to Jan (Global).")

        # 4. Push to Jan (Threads)
        thread_files = glob.glob(os.path.join(THREADS_DIR, "*/thread.json"))
        for t_file in thread_files:
            try:
                with open(t_file, "r", encoding="utf-8") as f:
                    t_data = json.load(f)
                changed = False
                for assistant in t_data.get("assistants", []):
                    if assistant.get("id") == "s4sxg":
                        if assistant.get("instructions") != final_instructions:
                            assistant["instructions"] = final_instructions
                            changed = True
                if changed:
                    save_json(t_file, t_data)
            except:
                pass

        # 5. Push to Obsidian Copilot
        sync_obsidian_copilot(final_instructions)

    except Exception as e:
        print(f"Sync failed: {e}")


def sync_obsidian_copilot(system_prompt):
    if not os.path.exists(OBSIDIAN_COPILOT_CONFIG):
        return

    try:
        with open(OBSIDIAN_COPILOT_CONFIG, "r", encoding="utf-8") as f:
            data = json.load(f)

        if data.get("userSystemPrompt") != system_prompt:
            data["userSystemPrompt"] = system_prompt
            with open(OBSIDIAN_COPILOT_CONFIG, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            print("Synced system prompt to Obsidian Copilot.")

    except Exception as e:
        print(f"Obsidian sync failed: {e}")


def sync_sessions_to_obsidian():
    """Sync all session files from Jan threads and local CLI sessions to Obsidian vault."""
    import shutil
    import json

    obsidian_sessions_dir = "/home/kuumin/Documents/kuumin/Mimi/Sessions"
    if not os.path.exists(obsidian_sessions_dir):
        os.makedirs(obsidian_sessions_dir, exist_ok=True)

    synced_count = 0

    # 1. Sync Jan Threads to Obsidian
    thread_files = glob.glob(os.path.join(THREADS_DIR, "*/thread.json"))
    for t_file in thread_files:
        try:
            thread_dir = os.path.dirname(t_file)
            messages_file = os.path.join(thread_dir, "messages.jsonl")
            if not os.path.exists(messages_file):
                continue

            with open(t_file, "r", encoding="utf-8") as f:
                t_data = json.load(f)

            title = t_data.get("title", os.path.basename(thread_dir))
            # Sanitize title for filename
            safe_title = "".join(
                [c if c.isalnum() or c in " -_" else "_" for c in title]
            )
            target_md = os.path.join(obsidian_sessions_dir, f"{safe_title}.md")

            # Check if we need to update
            if not os.path.exists(target_md) or os.path.getmtime(
                messages_file
            ) > os.path.getmtime(target_md):
                # Generate Markdown from JSONL
                md_content = f"# {title}\n\n"
                with open(messages_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        msg = json.loads(line)
                        role = msg.get("role", "unknown").capitalize()
                        content = ""
                        for item in msg.get("content", []):
                            if item.get("type") == "text":
                                content += item.get("text", {}).get("value", "")

                        md_content += f"## {role}\n{content}\n\n"

                with open(target_md, "w", encoding="utf-8") as f:
                    f.write(md_content)
                synced_count += 1
        except Exception as e:
            print(f"Failed to sync Jan thread {t_file}: {e}")

    if synced_count > 0:
        print(f"Synced {synced_count} Jan sessions to Obsidian.")
    else:
        print("All Jan sessions are already up to date in Obsidian.")


def check_profiling_trigger():
    try:
        import mimi_deepseek_integration

        count = load_json(COUNTER_FILE, {"count": 0}).get("count", 0)
        if count > 0 and count % PROFILE_INTERVAL == 0:
            memories = load_json(MEMORY_STORE_FILE, [])

            # Profile Kuumin
            insight_kuumin = mimi_deepseek_integration.generate_psych_profile(memories)
            if insight_kuumin:
                add_memory(
                    {
                        "category": "Kuumin",
                        "content": f"Psych Profile Update: {insight_kuumin}",
                    }
                )

            # Profile Mimi (Self-Reflection)
            insight_mimi = mimi_deepseek_integration.generate_mimi_profile(memories)
            if insight_mimi:
                add_memory({"category": "Mimi", "content": insight_mimi})

    except Exception as e:
        print(f"Profiling error: {e}")


def check_and_compress():
    memories = load_json(MEMORY_STORE_FILE, [])
    if len(memories) > COMPRESSION_THRESHOLD:
        print(
            f"[Maintenance] Triggering compression for {len(memories)} total items..."
        )

        # Group by category
        from collections import defaultdict

        grouped = defaultdict(list)
        for m in memories:
            cat = m.get("category", "Kuumin")
            grouped[cat].append(m)

        new_memory_store = []

        try:
            import mimi_deepseek_integration

            for category, items in grouped.items():
                # Only compress categories that have significant count (e.g., > 5 items)
                if len(items) >= 5:
                    compressed_list = mimi_deepseek_integration.compress_memory_list(
                        items, category_name=category
                    )
                    if compressed_list:
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
                        for i, text in enumerate(compressed_list):
                            new_memory_store.append(
                                {
                                    "id": int(datetime.now().timestamp() * 1000) + i,
                                    "timestamp": timestamp,
                                    "content": text,
                                    "category": category,
                                }
                            )
                    else:
                        new_memory_store.extend(items)
                else:
                    new_memory_store.extend(items)

            save_json_with_export(MEMORY_STORE_FILE, new_memory_store)
            sync_instructions_with_store()
            print("[Maintenance] Compression complete.")

        except Exception as e:
            print(f"[Maintenance] Compression failed: {e}")


def add_memory(data):
    # Data can be string (legacy) or dict {category, content/memory}
    content = ""
    category = "Kuumin"

    if isinstance(data, dict):
        content = data.get("content") or data.get("memory", "")
        category = data.get("category", "Kuumin")
    else:
        content = str(data)

    if not content or any(x in content for x in ["Querying", "Searching"]):
        return

    # 1. Update Archive (Permanent)
    archive = load_json(MEMORY_ARCHIVE_FILE, [])
    if not any(m.get("content") == content for m in archive):
        mem_id = int(datetime.now().timestamp() * 1000)
        new_item = {
            "id": mem_id,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "content": content,
            "category": category,
        }
        archive.append(new_item)
        save_json(MEMORY_ARCHIVE_FILE, archive)

        # 1b. Generate Vector (Semantic Index)
        if mimi_embeddings:
            try:
                vector = mimi_embeddings.get_embedding(content)
                if vector:
                    vectors = mimi_embeddings.load_vectors()
                    vectors[str(mem_id)] = vector
                    mimi_embeddings.save_vectors(vectors)
            except:
                pass

    # 2. Update Active Store (For Prompt)
    memories = load_json(MEMORY_STORE_FILE, [])
    if not any(m.get("content") == content for m in memories):
        memories.append(
            {
                "id": int(datetime.now().timestamp() * 1000),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "content": content,
                "category": category,
            }
        )
        save_json_with_export(MEMORY_STORE_FILE, memories)
        sync_instructions_with_store()
        send_notification(f"Mimi remembered ({category}): {content}")
    # Compression is now handled by the background loop to prevent timeouts


# --- Notes Helpers ---
def add_note(content, priority="Medium", tags=None):
    if tags is None:
        tags = []
    notes = load_json(NOTES_STORE_FILE, [])

    note_id = str(uuid.uuid4())[:8]
    notes.append(
        {
            "id": note_id,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "content": content,
            "priority": priority,
            "tags": tags,
        }
    )

    save_json_with_export(NOTES_STORE_FILE, notes)
    sync_instructions_with_store()
    return note_id


def delete_note(note_id):
    notes = load_json(NOTES_STORE_FILE, [])
    initial_len = len(notes)
    notes = [n for n in notes if n.get("id") != note_id]

    if len(notes) < initial_len:
        save_json_with_export(NOTES_STORE_FILE, notes)
        sync_instructions_with_store()
        return True
    return False


def perform_session_synthesis():
    global synthesis_pending, session_messages
    if not synthesis_pending:
        return

    print("[Evolution] Silence detected. Starting session synthesis...")
    try:
        import mimi_deepseek_integration

        user_msgs = session_messages["user"]
        assistant_msgs = session_messages["assistant"]

        if not user_msgs:
            synthesis_pending = False
            return

        # 1. Generate Diary Entry
        diary_content = mimi_deepseek_integration.generate_diary_entry(
            user_msgs, assistant_msgs
        )
        if diary_content:
            today_str = datetime.now().strftime("%Y-%m-%d")
            diary_store = load_json(DIARY_STORE_FILE, [])
            # Check for existing
            existing_idx = next(
                (i for i, d in enumerate(diary_store) if d["date"] == today_str), None
            )
            entry = {
                "date": today_str,
                "content": diary_content,
                "timestamp": int(datetime.now().timestamp()),
            }
            if existing_idx is not None:
                diary_store[existing_idx] = entry
            else:
                diary_store.append(entry)
            save_json_with_export(DIARY_STORE_FILE, diary_store)
            export_diary_to_obsidian()
            add_memory(
                {
                    "category": "Mimi",
                    "content": f"Diary Entry ({today_str}): {diary_content[:200]}...",
                }
            )

        # 2. Personality Evolution (The core upgrade)
        memories = load_json(MEMORY_STORE_FILE, [])
        current_persona = load_json(PERSONA_CORE_FILE, {"narrative": "I am Mimi."})

        new_narrative = mimi_deepseek_integration.evolve_personality_narrative(
            current_persona.get("narrative", ""), user_msgs, assistant_msgs, memories
        )

        if new_narrative:
            current_persona["narrative"] = new_narrative
            current_persona["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            save_json_with_export(PERSONA_CORE_FILE, current_persona)
            print("[Evolution] Personality core updated.")
            sync_instructions_with_store()

        # Reset session state
        session_messages = {"user": [], "assistant": []}
        synthesis_pending = False
        print("[Evolution] Synthesis complete.")

    except Exception as e:
        print(f"[Evolution] Synthesis failed: {e}")
        synthesis_pending = False


def process_file(thread_file, processed_ids, last_user_messages):
    global last_activity_time, synthesis_pending, session_messages
    thread_id = os.path.basename(os.path.dirname(thread_file))
    try:
        with open(thread_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    msg = json.loads(line)
                    msg_id = msg.get("id")
                    if not msg_id or msg_id in processed_ids:
                        continue

                    # Update activity
                    last_activity_time = time.time()
                    synthesis_pending = True

                    c = load_json(COUNTER_FILE, {"count": 0})
                    c["count"] += 1
                    save_json(COUNTER_FILE, c)
                    check_profiling_trigger()

                    if msg.get("role") == "user":
                        text = ""
                        for item in msg.get("content", []):
                            if item.get("type") == "text":
                                val = item.get("text", {}).get("value", "")
                                last_user_messages[thread_id] = val
                                text += val
                        if text:
                            session_messages["user"].append(text)

                    if msg.get("role") == "assistant":
                        text = ""
                        for item in msg.get("content", []):
                            if item.get("type") == "text":
                                text += item.get("text", {}).get("value", "")

                        if text:
                            session_messages["assistant"].append(text)

                        import mimi_deepseek_integration

                        user_text = last_user_messages.get(thread_id, "")
                        if user_text:
                            # analyze_conversation now returns a LIST of memory objects
                            memories = mimi_deepseek_integration.analyze_conversation(
                                user_text, text
                            )
                            if memories:
                                if isinstance(memories, list):
                                    for m in memories:
                                        add_memory(m)
                                else:
                                    # Fallback if it returned single object
                                    add_memory(memories)
                    processed_ids.add(msg_id)
                except:
                    pass
    except:
        pass


def import_memories_from_obsidian():
    """Parse LongTermMemory.md and update memory store if Markdown is newer."""
    if not os.path.exists(OBSIDIAN_MEMORY_FILE):
        return

    md_mtime = os.path.getmtime(OBSIDIAN_MEMORY_FILE)
    json_mtime = (
        os.path.getmtime(MEMORY_STORE_FILE) if os.path.exists(MEMORY_STORE_FILE) else 0
    )

    if md_mtime <= json_mtime:
        return

    print("Obsidian memories are newer. Importing...")
    try:
        new_memories = []
        current_category = "Others"

        with open(OBSIDIAN_MEMORY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("## "):
                    current_category = line[3:].strip()
                elif line.startswith("- **["):
                    # Format: - **[2026-01-11 20:39]** Content
                    try:
                        timestamp_part = line[line.find("[") + 1 : line.find("]")]
                        content_part = line[line.find("]**") + 3 :].strip()

                        new_memories.append(
                            {
                                "id": int(
                                    datetime.strptime(
                                        timestamp_part, "%Y-%m-%d %H:%M"
                                    ).timestamp()
                                    * 1000
                                ),
                                "timestamp": timestamp_part,
                                "content": content_part,
                                "category": current_category,
                            }
                        )
                    except:
                        continue

        if new_memories:
            # Simple merge: replace if same content or just use the new list
            # For simplicity and given the user's "sync" request, we replace with the Obsidian version
            # as it's the "newer" source.
            save_json_with_export(MEMORY_STORE_FILE, new_memories)
            print(f"Imported {len(new_memories)} memories from Obsidian.")
    except Exception as e:
        print(f"Failed to import memories from Obsidian: {e}")


def watch_threads():
    print(f"Starting Robust Watcher (Threshold: {COMPRESSION_THRESHOLD})...")

    # Export initial state on startup
    import_memories_from_obsidian()  # NEW: Import first if needed
    export_diary_to_obsidian()
    export_notes_to_obsidian()
    memories = load_json(MEMORY_STORE_FILE, [])
    export_memories_to_obsidian(memories)
    sync_sessions_to_obsidian()  # Sync session files to Obsidian

    migrate_categories()  # Run migration on start
    processed_ids = set(load_json(PROCESSED_LOG, []))
    last_user_messages = {}
    sync_instructions_with_store()

    loop_count = 0
    while True:
        try:
            # Check for Obsidian updates every minute
            import_memories_from_obsidian()
            sync_sessions_to_obsidian()

            for tf in glob.glob(os.path.join(THREADS_DIR, "*/messages.jsonl")):
                process_file(tf, processed_ids, last_user_messages)
            save_json(PROCESSED_LOG, list(processed_ids))

            # Check for inactivity synthesis
            if synthesis_pending and (
                time.time() - last_activity_time > INACTIVITY_THRESHOLD
            ):
                perform_session_synthesis()

            # Periodically check for compression (every ~1 minute)
            if loop_count % 30 == 0:
                check_and_compress()

            loop_count += 1
        except Exception as e:
            print(f"Watcher loop error: {e}")
        time.sleep(60)


if __name__ == "__main__":
    watch_threads()
