from mimi_lib.tools.registry import register_tool
from mimi_lib.memory.brain import save_memory, get_literal_matches
import subprocess
import os
import uuid
from datetime import datetime
from mimi_lib.config import NOTES_STORE_FILE
import json

@register_tool(
    "add_note",
    "Add a task/reminder to the active notebook.",
    {
        "type": "object", 
        "properties": {
            "content": {"type": "string"},
            "priority": {"type": "string", "enum": ["High", "Medium", "Low"]},
            "tags": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["content"]
    }
)
def add_note(content: str, priority: str = "Medium", tags: list = None):
    tags = tags or []
    notes = []
    if NOTES_STORE_FILE.exists():
        try: notes = json.loads(NOTES_STORE_FILE.read_text())
        except: pass
    
    note_id = str(uuid.uuid4())[:8]
    notes.append({
        "id": note_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "content": content,
        "priority": priority,
        "tags": tags
    })
    
    NOTES_STORE_FILE.write_text(json.dumps(notes, indent=2))
    return f"Note added (ID: {note_id})."

@register_tool(
    "delete_note",
    "Delete a completed note by ID.",
    {"type": "object", "properties": {"note_id": {"type": "string"}}, "required": ["note_id"]}
)
def delete_note(note_id: str):
    if not NOTES_STORE_FILE.exists(): return "No notes found."
    try:
        notes = json.loads(NOTES_STORE_FILE.read_text())
        initial = len(notes)
        notes = [n for n in notes if n["id"] != note_id]
        if len(notes) < initial:
            NOTES_STORE_FILE.write_text(json.dumps(notes, indent=2))
            return f"Note {note_id} deleted."
        return "Note ID not found."
    except: return "Error reading notes."
