import json
import requests
from mimi_lib.config import get_config

def call_api(messages, model="deepseek-reasoner", stream=True, tools=None):
    config = get_config()
    headers = {
        "Authorization": f"Bearer {config['deepseek_api_key']}",
        "Content-Type": "application/json",
    }
    
    # Simple provider mapping logic
    endpoint = f"{config['base_url']}/chat/completions"
    if "grok" in model:
        endpoint = f"{config['xai_base_url']}/chat/completions"
        headers["Authorization"] = f"Bearer {config['xai_api_key']}"
    elif "mimo" in model:
        endpoint = f"{config['openrouter_base_url']}/chat/completions"
        headers["Authorization"] = f"Bearer {config['openrouter_api_key']}"

    payload = {
        "model": model,
        "messages": messages,
        "stream": stream,
        "temperature": 0.5,
    }
    if tools:
        payload["tools"] = tools

    try:
        res = requests.post(endpoint, headers=headers, json=payload, stream=stream, timeout=120)
        res.raise_for_status()
        return res
    except Exception as e:
        print(f"[API] Error: {e}")
        return None

def analyze_conversation(user_text, assistant_text):
    prompt = f"User said: \"{user_text}\"\nAssistant replied: \"{assistant_text}\"\n\nDid the user reveal any NEW personal fact? Output JSON: {{'category': 'Events'|'Mimi'|'Kuumin'|'Others', 'content': '...'}}"
    res = call_api([{"role": "user", "content": prompt}], model="deepseek-chat", stream=False)
    if res:
        try:
            content = res.json()["choices"][0]["message"]["content"]
            # Basic cleanup
            if "```json" in content: content = content.split("```json")[1].split("```")[0]
            data = json.loads(content)
            return [data] if data.get("content") else None
        except: return None
    return None

def compress_memories(memories, category="General"):
    memory_block = "\n".join(f"- {m['content']}" for m in memories)
    prompt = f"Consolidate these {category} memories into a concise list. Return JSON: {{'compressed': ['fact 1', ...]}}\n\n{memory_block}"
    res = call_api([{"role": "user", "content": prompt}], model="deepseek-chat", stream=False)
    if res:
        try:
            content = res.json()["choices"][0]["message"]["content"]
            if "```json" in content: content = content.split("```json")[1].split("```")[0]
            return json.loads(content).get("compressed")
        except: return None
    return None
