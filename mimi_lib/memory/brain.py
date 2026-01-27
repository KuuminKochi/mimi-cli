import json
import re
import uuid
from datetime import datetime
from mimi_lib.config import (
    LOCAL_PROMPT_FILE,
    VAULT_PROMPT_FILE,
    MEMORY_ARCHIVE_FILE,
    MEMORY_STORE_FILE,
    PERSONA_CORE_FILE,
    DIARY_STORE_FILE,
    NOTES_STORE_FILE,
)


def load_json(path, default=None):
    if not path.exists():
        return default if default is not None else []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except:
        return default if default is not None else []


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_system_prompt():
    # Sync logic: Obsidian is master if it exists
    content = "You are Mimi, a helpful AI assistant."
    if VAULT_PROMPT_FILE.exists():
        content = VAULT_PROMPT_FILE.read_text(encoding="utf-8")
        LOCAL_PROMPT_FILE.write_text(content, encoding="utf-8")
    elif LOCAL_PROMPT_FILE.exists():
        content = LOCAL_PROMPT_FILE.read_text(encoding="utf-8")

    # Inject Persona
    persona = ""
    if PERSONA_CORE_FILE.exists():
        try:
            data = json.loads(PERSONA_CORE_FILE.read_text())
            persona = f"**Identity Narrative:**\n{data.get('narrative', '')}\n\n"
        except:
            pass

    now = datetime.now()
    temporal = f"**Temporal Context:**\n- Date: {now.strftime('%A, %b %d, %Y')}\n- Time: {now.strftime('%H:%M')}\n\n"

    # Template Substitution
    content = content.replace("{{user}}", "Kuumin")
    content = content.replace("{{current_date}}", now.strftime("%A, %b %d, %Y"))

    return persona + temporal + content


def get_literal_matches(query: str, top_k: int = 2):
    if not MEMORY_ARCHIVE_FILE.exists():
        return []
    try:
        archive = json.loads(MEMORY_ARCHIVE_FILE.read_text())
        stop_words = {"about", "there", "their", "would", "could", "should"}
        words = re.findall(r"\b\w{5,}\b", query.lower())
        keywords = [w for w in words if w not in stop_words]

        if not keywords:
            return []

        matches = []
        for item in archive:
            content = item.get("content", "").lower()
            score = sum(1 for kw in keywords if kw in content)
            if score > 0:
                matches.append((score, item))

        matches.sort(key=lambda x: x[0], reverse=True)
        return [m[1] for m in matches[:top_k]]
    except:
        return []


def save_memory(content, category="Kuumin"):
    archive = load_json(MEMORY_ARCHIVE_FILE)
    mem_id = int(datetime.now().timestamp() * 1000)
    item = {
        "id": mem_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "content": content,
        "category": category,
    }

    if not any(m.get("content") == content for m in archive):
        archive.append(item)
        save_json(MEMORY_ARCHIVE_FILE, archive)

    # Also update active store
    store = load_json(MEMORY_STORE_FILE)
    if not any(m.get("content") == content for m in store):
        store.append(item)
        save_json(MEMORY_STORE_FILE, store)
    return mem_id


def delete_memory(mem_id):
    try:
        target_id = int(mem_id)
    except:
        return False

    deleted = False
    # Store
    store = load_json(MEMORY_STORE_FILE)
    new_store = [m for m in store if m.get("id") != target_id]
    if len(new_store) < len(store):
        save_json(MEMORY_STORE_FILE, new_store)
        deleted = True

    # Archive
    archive = load_json(MEMORY_ARCHIVE_FILE)
    new_archive = [m for m in archive if m.get("id") != target_id]
    if len(new_archive) < len(archive):
        save_json(MEMORY_ARCHIVE_FILE, new_archive)
        deleted = True

    return deleted


def add_note(content, priority="Medium", tags=None):
    if tags is None:
        tags = []
    notes = load_json(NOTES_STORE_FILE)
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
    save_json(NOTES_STORE_FILE, notes)
    return note_id


def delete_note(note_id):
    notes = load_json(NOTES_STORE_FILE)
    initial_len = len(notes)
    notes = [n for n in notes if n.get("id") != note_id]
    if len(notes) < initial_len:
        save_json(NOTES_STORE_FILE, notes)
        return True
    return False


def load_diary():
    return load_json(DIARY_STORE_FILE)


def save_diary_entry(content, date=None):
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    diary = load_json(DIARY_STORE_FILE)
    entry = {
        "date": date,
        "content": content,
        "timestamp": int(datetime.now().timestamp()),
    }
    # Update existing or append
    existing_idx = next((i for i, d in enumerate(diary) if d["date"] == date), None)
    if existing_idx is not None:
        diary[existing_idx] = entry
    else:
        diary.append(entry)
    save_json(DIARY_STORE_FILE, diary)
    return True


def delete_diary_entry(date):
    diary = load_json(DIARY_STORE_FILE)
    initial_len = len(diary)
    diary = [d for d in diary if d["date"] != date]
    if len(diary) < initial_len:
        save_json(DIARY_STORE_FILE, diary)
        return True
    return False
