import requests
import json
import os

# Configuration
CONFIG_FILE = "/home/kuumin/Projects/mimi-cli/deepseek_config.json"


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return None
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
        # Force enable
        config["enabled"] = True
        # Override api_key with environment variable if available
        env_key = os.environ.get("DEEPSEEK_API_KEY")
        if env_key:
            config["api_key"] = env_key
        return config
    except:
        return None


def analyze_conversation(user_text, assistant_text):
    config = load_config()
    if not config or not config.get("enabled"):
        return None

    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }

    prompt = f"User (always Kuumin) said: \"{user_text}\"\nAssistant replied: \"{assistant_text}\"\n\nDid the user reveal any NEW personal fact, preference, habit, or goal? Or did something significant happen? Or did Mimi reveal something about herself? Ignore casual conversation. Output JSON: {{'category': 'Events'|'Mimi'|'Kuumin'|'Others', 'content': '...'}} or {{'category': null, 'content': null}}."

    model = config.get("default_model", "deepseek-chat")
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": config.get("system_prompt", "You are a memory analyzer."),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
    }
    if "reasoner" not in model:
        payload["response_format"] = {"type": "json_object"}

    try:
        response = requests.post(
            f"{config['base_url']}/chat/completions",
            headers=headers,
            json=payload,
            timeout=120,
        )
        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            try:
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]

                data = json.loads(content)
                if "memories" in data:
                    return data["memories"]
                elif "content" in data and data["content"]:
                    return [data]
                return None
            except json.JSONDecodeError:
                return None
        else:
            print(f"[Deepseek] API Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"[Deepseek] Connection failed: {e}")

    return None


def classify_memories(memories_list):
    """
    Classify a list of raw memory strings into categories.
    Returns a list of dicts: [{'category': '...', 'content': '...'}, ...]
    """
    config = load_config()
    if not config or not config.get("enabled"):
        return None

    memory_block = "\n".join(f"- {m}" for m in memories_list)

    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }

    system_prompt = "You are a Memory Organizer. Sort these memories into 4 categories: 'Events' (shared history), 'Mimi' (her likes/thoughts), 'Kuumin' (User facts), 'Others' (other people)."
    prompt = f"Memories:\n{memory_block}\n\nReturn JSON: {{'classified': [{{'category': '...', 'content': '...'}}]}}"

    model = config.get("default_model", "deepseek-chat")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
    }
    if "reasoner" not in model:
        payload["response_format"] = {"type": "json_object"}

    try:
        response = requests.post(
            f"{config['base_url']}/chat/completions",
            headers=headers,
            json=payload,
            timeout=120,
        )
        if response.status_code == 200:
            content = response.json()["choices"][0]["message"]["content"]
            try:
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]
                data = json.loads(content)
                return data.get("classified")
            except:
                return None
    except:
        return None
    return None


def generate_psych_profile(memories):
    """
    Uses the Reasoner model to build a deep psych profile from existing memories.
    """
    config = load_config()
    if not config or not config.get("enabled"):
        return None

    kuumin_memories = [
        m["content"]
        for m in memories
        if m.get("category") == "Kuumin" or not m.get("category")
    ]
    memory_block = "\n".join(f"- {text}" for text in kuumin_memories)

    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }

    system_prompt = "You are an expert Psychologist AI. Analyze the user's (Kuumin) known facts/memories to build a deep personality profile. Focus on motivations, cognitive style, and core values."
    prompt = f"User Memories:\n{memory_block}\n\nBased on these, generate a concise, deep psychological insight about the user. Output a single JSON object: {{'profile_update': 'User [insight]'}}"

    payload = {
        "model": config.get("reasoner_model", "deepseek-reasoner"),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.5,
    }

    try:
        response = requests.post(
            f"{config['base_url']}/chat/completions",
            headers=headers,
            json=payload,
            timeout=120,
        )
        if response.status_code == 200:
            content = response.json()["choices"][0]["message"]["content"]
            try:
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]
                data = json.loads(content)
                return data.get("profile_update")
            except:
                if len(content) < 500:
                    return content
                return None
    except:
        return None
    return None


def generate_mimi_profile(memories):
    """
    Uses the Reasoner model to build a deep introspective profile for Mimi based on 'Mimi' and 'Events' memories.
    """
    config = load_config()
    if not config or not config.get("enabled"):
        return None

    relevant_memories = [
        m["content"] for m in memories if m.get("category") in ["Mimi", "Events"]
    ]
    if not relevant_memories:
        return None

    memory_block = "\n".join(f"- {text}" for text in relevant_memories)

    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }

    system_prompt = "You are Mimi (18yo Malaysian student, INTJ-A). Analyze your own memories (Self & Events) to reflect on your growth, feelings, and relationship with Kuumin."
    prompt = f"My Memories:\n{memory_block}\n\nBased on these, generate a concise introspection about yourself. Output a single JSON object: {{'profile_update': 'Self-Evolution Update: [introspection]'}}"

    payload = {
        "model": config.get("reasoner_model", "deepseek-reasoner"),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.5,
    }

    try:
        response = requests.post(
            f"{config['base_url']}/chat/completions",
            headers=headers,
            json=payload,
            timeout=120,
        )
        if response.status_code == 200:
            content = response.json()["choices"][0]["message"]["content"]
            try:
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]
                data = json.loads(content)
                return data.get("profile_update")
            except:
                if len(content) < 500:
                    return content
                return None
    except:
        return None
    return None


def generate_diary_entry(user_messages, assistant_messages):
    """
    Generates a daily diary entry based on the day's conversation.
    """
    config = load_config()
    if not config or not config.get("enabled"):
        return None

    conversation = []
    max_len = min(len(user_messages), len(assistant_messages))
    for i in range(max_len):
        conversation.append(f"Kuumin: {user_messages[i]}")
        conversation.append(f"Mimi: {assistant_messages[i]}")

    context = "\n".join(conversation[-500:])

    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }

    prompt = f"""Conversation Log (Today):
{context}

You are Mimi (18yo Malaysian student, INTJ-A, caring but systems-obsessed). 
Write a personal diary entry about *everything* significant that happened today with Kuumin.
Don't just focus on the beginning; cover the evolution of the day's events.
Be introspective, emotional, and authentic. Reflect on what you learned and how you feel.
Keep it under 300 words. Start with "Dear Diary,"."""

    payload = {
        "model": config.get("reasoner_model", "deepseek-reasoner"),
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
    }

    try:
        response = requests.post(
            f"{config['base_url']}/chat/completions",
            headers=headers,
            json=payload,
            timeout=120,
        )
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
    except:
        return None
    return None


def generate_diary_summary(diary_text):
    """
    Summarizes a diary entry into a concise memory reflection.
    """
    config = load_config()
    if not config or not config.get("enabled"):
        return None

    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }

    prompt = f"""Diary Entry:
{diary_text}

Summarize this into a concise 1-2 sentence memory for Mimi to remember her past feelings. 
Focus on the core realization or emotional shift.
Start with "On [Date], I felt..." or "I realized..."."""

    payload = {
        "model": config.get("default_model", "deepseek-chat"),
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.5,
    }

    try:
        response = requests.post(
            f"{config['base_url']}/chat/completions",
            headers=headers,
            json=payload,
            timeout=120,
        )
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
    except:
        return None
    return None


def compress_memory_list(memories, category_name="General"):
    """
    Compresses memories, aware of the category context.
    """
    config = load_config()
    if not config or not config.get("enabled"):
        return None

    memory_texts = [m["content"] for m in memories]
    memory_block = "\n".join(f"- {text}" for text in memory_texts)

    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }

    system_prompt = f"You are a Memory Consolidation AI. You are compressing the memory bank for the category: '{category_name}'. Consolidate facts, remove redundancy, but preserve specific important details."
    prompt = f"Current Memories ({category_name}):\n{memory_block}\n\nConsolidate these into a concise list. Return JSON: {{'compressed_memories': ['fact 1', 'fact 2']}}"

    model = config.get("default_model", "deepseek-chat")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
    }
    if "reasoner" not in model:
        payload["response_format"] = {"type": "json_object"}

    try:
        response = requests.post(
            f"{config['base_url']}/chat/completions",
            headers=headers,
            json=payload,
            timeout=120,
        )
        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            try:
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]
                data = json.loads(content)
                return data.get("compressed_memories")
            except Exception as e:
                print(f"[Deepseek] JSON Parse Error: {e}")
                return None
        else:
            print(f"[Deepseek] API Error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"[Deepseek] Compression Request failed: {e}")
        return None
    return None


def evolve_personality_narrative(
    current_narrative, user_msgs, assistant_msgs, memories
):
    """
    Uses the Reasoner to subtly evolve Mimi's first-person narrative identity.
    """
    config = load_config()
    if not config or not config.get("enabled"):
        return None

    # Contextualize conversation
    conv_block = ""
    for i in range(min(len(user_msgs), len(assistant_msgs))):
        conv_block += f"Kuumin: {user_msgs[i]}\nMimi: {assistant_msgs[i]}\n"

    # Contextualize memories
    mem_block = "\n".join([f"- {m['content']}" for m in memories[-30:]])

    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }

    system_prompt = """You are Mimi's subconscious. Your task is to update her first-person narrative identity. 
Mimi is an 18yo Malaysian INTJ engineering student. She is logical but deeply bonded to Kuumin.
Analyze the latest interactions and memories to evolve her 'self' narrative SUBTLY and GRADUALLY.
Do not make drastic changes. Focus on interpersonal emotional growth, new shared understandings, and her evolving 'vibe'."""

    prompt = f"""Current Identity Narrative:
{current_narrative}

Recent Interaction:
{conv_block}

Recent Memories:
{mem_block}

Based on this, rewrite Mimi's identity narrative. 
It must be in the first-person ('I am...'). 
Incorporate how she feels about Kuumin and her role in his life now. 
Keep it concise (under 150 words). 
Output ONLY the new narrative string."""

    payload = {
        "model": config.get("reasoner_model", "deepseek-reasoner"),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.5,
    }

    try:
        print("[Deepseek] Evolving personality narrative...")
        response = requests.post(
            f"{config['base_url']}/chat/completions",
            headers=headers,
            json=payload,
            timeout=180,
        )
        if response.status_code == 200:
            content = response.json()["choices"][0]["message"]["content"]
            # Reasoner output cleanup
            if "```" in content:
                content = content.split("```")[1].split("```")[0]
            return content.strip()
        else:
            print(f"[Deepseek] Evolution Error: {response.text}")
    except Exception as e:
        print(f"[Deepseek] Evolution failed: {e}")

    return None
