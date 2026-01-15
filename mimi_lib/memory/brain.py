import json
import re
from datetime import datetime
from mimi_lib.config import LOCAL_PROMPT_FILE, VAULT_PROMPT_FILE, MEMORY_ARCHIVE_FILE, MEMORY_STORE_FILE, MEMORY_VECTORS_FILE, PERSONA_CORE_FILE

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
        except: pass
        
    now = datetime.now()
    temporal = f"**Temporal Context:**\n- Date: {now.strftime('%A, %b %d, %Y')}\n- Time: {now.strftime('%H:%M')}\n\n"
    
    # Template Substitution
    content = content.replace("{{user}}", "Kuumin")
    content = content.replace("{{current_date}}", now.strftime('%A, %b %d, %Y'))
    
    return persona + temporal + content

def get_literal_matches(query: str, top_k: int = 2):
    if not MEMORY_ARCHIVE_FILE.exists():
        return []
    try:
        archive = json.loads(MEMORY_ARCHIVE_FILE.read_text())
        stop_words = {"about", "there", "their", "would", "could", "should"}
        words = re.findall(r"\b\w{5,}\b", query.lower())
        keywords = [w for w in words if w not in stop_words]
        
        if not keywords: return []
        
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
    archive = []
    if MEMORY_ARCHIVE_FILE.exists():
        try: archive = json.loads(MEMORY_ARCHIVE_FILE.read_text())
        except: pass
    
    mem_id = int(datetime.now().timestamp() * 1000)
    item = {
        "id": mem_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "content": content,
        "category": category
    }
    archive.append(item)
    MEMORY_ARCHIVE_FILE.write_text(json.dumps(archive, indent=2))
    
    # Also update active store
    store = []
    if MEMORY_STORE_FILE.exists():
        try: store = json.loads(MEMORY_STORE_FILE.read_text())
        except: pass
    store.append(item)
    MEMORY_STORE_FILE.write_text(json.dumps(store, indent=2))
    return mem_id
