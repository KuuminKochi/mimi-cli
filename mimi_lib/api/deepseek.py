import json
import os
from mimi_lib.config import get_config
from mimi_lib.api.provider import call_api


def analyze_conversation(user_text, assistant_text):
    prompt = f"User (always Kuumin) said: \"{user_text}\"\nAssistant replied: \"{assistant_text}\"\n\nDid the user reveal any NEW personal fact, preference, habit, or goal? Or did something significant happen? Or did Mimi reveal something about herself? Ignore casual conversation. Output JSON: {{'category': 'Events'|'Mimi'|'Kuumin'|'Others', 'content': '...'}} or {{'category': null, 'content': null}}."

    res = call_api(
        [
            {"role": "system", "content": "You are a memory analyzer."},
            {"role": "user", "content": prompt},
        ],
        model="deepseek-chat",
        stream=False,
        response_format={"type": "json_object"},
    )

    if res and res.status_code == 200:
        try:
            data = res.json()["choices"][0]["message"]["content"]
            parsed = json.loads(data)
            if "memories" in parsed:
                return parsed["memories"]
            elif "content" in parsed and parsed["content"]:
                return [parsed]
        except:
            pass
    return None


def classify_memories(memories_list):
    memory_block = "\n".join(f"- {m}" for m in memories_list)
    system_prompt = "You are a Memory Organizer. Sort these memories into 4 categories: 'Events' (shared history), 'Mimi' (her likes/thoughts), 'Kuumin' (User facts), 'Others' (other people)."
    prompt = f"Memories:\n{memory_block}\n\nReturn JSON: {{'classified': [{{'category': '...', 'content': '...'}}]}}"

    res = call_api(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        model="deepseek-chat",
        stream=False,
        response_format={"type": "json_object"},
    )

    if res and res.status_code == 200:
        try:
            data = json.loads(res.json()["choices"][0]["message"]["content"])
            return data.get("classified")
        except:
            pass
    return None


def generate_psych_profile(memories):
    kuumin_memories = [
        m["content"]
        for m in memories
        if m.get("category") == "Kuumin" or not m.get("category")
    ]
    if not kuumin_memories:
        return None
    memory_block = "\n".join(f"- {text}" for text in kuumin_memories)

    system_prompt = "You are an expert Psychologist AI. Analyze the user's (Kuumin) known facts/memories to build a deep personality profile. Focus on motivations, cognitive style, and core values."
    prompt = f"User Memories:\n{memory_block}\n\nBased on these, generate a concise, deep psychological insight about the user. Output a single JSON object: {{'profile_update': 'User [insight]'}}"
    combined = f"{system_prompt}\n\n{prompt}"

    res = call_api(
        [
            {"role": "user", "content": combined},
        ],
        model="deepseek-reasoner",
        stream=False,
    )

    if res and res.status_code == 200:
        content = res.json()["choices"][0]["message"]["content"]
        try:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            return json.loads(content).get("profile_update")
        except:
            return content if len(content) < 500 else None
    return None


def generate_mimi_profile(memories):
    relevant_memories = [
        m["content"] for m in memories if m.get("category") in ["Mimi", "Events"]
    ]
    if not relevant_memories:
        return None
    memory_block = "\n".join(f"- {text}" for text in relevant_memories)

    system_prompt = "You are Mimi (18yo Malaysian student, INTJ-A). Analyze your own memories (Self & Events) to reflect on your growth, feelings, and relationship with Kuumin."
    prompt = f"My Memories:\n{memory_block}\n\nBased on these, generate a concise introspection about yourself. Output a single JSON object: {{'profile_update': 'Self-Evolution Update: [introspection]'}}"
    combined = f"{system_prompt}\n\n{prompt}"

    res = call_api(
        [
            {"role": "user", "content": combined},
        ],
        model="deepseek-reasoner",
        stream=False,
    )

    if res and res.status_code == 200:
        content = res.json()["choices"][0]["message"]["content"]
        try:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            return json.loads(content).get("profile_update")
        except:
            return content if len(content) < 500 else None
    return None


def generate_diary_entry(user_messages, assistant_messages):
    conversation = []
    max_len = min(len(user_messages), len(assistant_messages))
    for i in range(max_len):
        conversation.append(f"Kuumin: {user_messages[i]}")
        conversation.append(f"Mimi: {assistant_messages[i]}")

    context = "\n".join(conversation[-500:])
    prompt = f"Conversation Log (Today):\n{context}\n\nYou are Mimi (18yo Malaysian student, INTJ-A, caring but systems-obsessed). Write a personal diary entry about *everything* significant that happened today with Kuumin. Be introspective, emotional, and authentic. Keep it under 300 words. Start with 'Dear Diary,'."

    res = call_api(
        [{"role": "user", "content": prompt}], model="deepseek-reasoner", stream=False
    )
    if res and res.status_code == 200:
        return res.json()["choices"][0]["message"]["content"]
    return None


def compress_memory_list(memories, category_name="General"):
    memory_texts = [m["content"] for m in memories]
    memory_block = "\n".join(f"- {text}" for text in memory_texts)
    system_prompt = f"You are a Memory Consolidation AI. You are compressing the memory bank for the category: '{category_name}'. Consolidate facts, remove redundancy, but preserve specific important details."
    prompt = f"Current Memories ({category_name}):\n{memory_block}\n\nConsolidate these into a concise list. Return JSON: {{'compressed_memories': ['fact 1', 'fact 2']}}"

    res = call_api(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        model="deepseek-chat",
        stream=False,
        response_format={"type": "json_object"},
    )

    if res and res.status_code == 200:
        try:
            data = json.loads(res.json()["choices"][0]["message"]["content"])
            return data.get("compressed_memories")
        except:
            pass
    return None


def evolve_personality_narrative(
    current_narrative, user_msgs, assistant_msgs, memories
):
    conv_block = ""
    for i in range(min(len(user_msgs), len(assistant_msgs))):
        conv_block += f"Kuumin: {user_msgs[i]}\nMimi: {assistant_msgs[i]}\n"
    mem_block = "\n".join([f"- {m['content']}" for m in memories[-30:]])

    system_prompt = "You are Mimi's subconscious. Update her first-person narrative identity ('I am...'). Focus on interpersonal emotional growth, new shared understandings, and her evolving 'vibe'. Keep it under 150 words."
    prompt = f"Current Identity Narrative:\n{current_narrative}\n\nRecent Interaction:\n{conv_block}\n\nRecent Memories:\n{mem_block}\n\nOutput ONLY the new narrative string."
    combined = f"{system_prompt}\n\n{prompt}"

    res = call_api(
        [
            {"role": "user", "content": combined},
        ],
        model="deepseek-reasoner",
        stream=False,
    )

    if res and res.status_code == 200:
        content = res.json()["choices"][0]["message"]["content"]
        if "```" in content:
            content = content.split("```")[1].split("```")[0]
        return content.strip()
    return None
