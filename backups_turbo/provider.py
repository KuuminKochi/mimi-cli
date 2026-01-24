import json
import requests
from mimi_lib.config import get_config

# Global Session for persistent connections
_session = requests.Session()
_cache = {}


def call_api(
    messages, model="deepseek-reasoner", stream=True, tools=None, response_format=None
):
    config = get_config()

    def get_params(target_model):
        headers = {
            "Content-Type": "application/json",
        }
        endpoint = f"{config['base_url']}/chat/completions"
        actual_model = target_model

        # Provider mapping
        if "grok" in target_model:
            endpoint = f"{config['xai_base_url']}/chat/completions"
            headers["Authorization"] = f"Bearer {config['xai_api_key']}"
        elif "mimo" in target_model:
            endpoint = f"{config['openrouter_base_url']}/chat/completions"
            headers["Authorization"] = f"Bearer {config['openrouter_api_key']}"
        elif target_model.startswith("or/"):
            endpoint = f"{config['openrouter_base_url']}/chat/completions"
            headers["Authorization"] = f"Bearer {config['openrouter_api_key']}"
            actual_model = target_model[3:]  # Remove 'or/' prefix
        else:
            # Default DeepSeek
            headers["Authorization"] = f"Bearer {config['deepseek_api_key']}"

        payload = {
            "model": actual_model,
            "messages": messages,
            "stream": stream,
            "temperature": 0.5,
        }
        if tools:
            payload["tools"] = tools
        if response_format:
            payload["response_format"] = response_format

        # Sanitize Payload: Ensure content is never None
        if "messages" in payload:
            for m in payload["messages"]:
                if m.get("content") is None:
                    m["content"] = ""

        return endpoint, headers, payload

    # First Attempt
    endpoint, headers, payload = get_params(model)
    try:
        # Use persistent session
        res = _session.post(
            endpoint, headers=headers, json=payload, stream=stream, timeout=120
        )

        # Check for credit exhaustion
        if res.status_code in [402, 403, 400]:
            is_credit_err = False
            try:
                err_json = res.json()
                msg = str(err_json).lower()
                if any(
                    x in msg for x in ["insufficient", "balance", "credit", "payment"]
                ):
                    is_credit_err = True
            except:
                if res.status_code == 402:
                    is_credit_err = True

            if is_credit_err:
                raise Exception(
                    f"DeepSeek Credit Exhaustion (Status {res.status_code})"
                )

        res.raise_for_status()
        return res
    except Exception as e:
        # Fallback to OpenRouter for DeepSeek models
        is_deepseek = any(x in model.lower() for x in ["deepseek", "reasoner"])
        # Check for credit failures or 400 errors (often due to R1 limitations)
        is_recoverable = any(
            x in str(e).lower() for x in ["insufficient", "balance", "credit", "402", "400"]
        )

        if is_deepseek and is_recoverable and config.get("openrouter_api_key"):
            print(f"\n[API] DeepSeek failed ({e}). Falling back to OpenRouter...")
            fallback_model = (
                "deepseek/deepseek-r1"
                if "reasoner" in model
                else "deepseek/deepseek-chat"
            )
            # Recursive call with fallback model
            return call_api(messages, model=f"or/{fallback_model}", stream=stream, tools=tools, response_format=response_format)
        else:
            print(f"[API] Error: {e}")
            return None


def analyze_conversation(user_text, assistant_text):
    prompt = f"User (always Kuumin) said: \"{user_text}\"\nAssistant replied: \"{assistant_text}\"\n\nDid the user reveal any NEW personal fact, preference, habit, or goal? Or did something significant happen? Or did Mimi reveal something about herself? Output JSON: {{'category': 'Events'|'Mimi'|'Kuumin'|'Others', 'content': '...'}}."
    res = call_api(
        [{"role": "user", "content": prompt}],
        model="deepseek-chat",
        stream=False,
        response_format={"type": "json_object"},
    )
    if res:
        try:
            content = res.json()["choices"][0]["message"]["content"]
            data = json.loads(content)
            return [data] if data.get("content") else None
        except:
            return None
    return None


def compress_memories(memories, category="General"):
    memory_block = "\n".join(f"- {m['content']}" for m in memories)
    prompt = f"Consolidate these {category} memories into a concise list. Return JSON: {{'compressed': ['fact 1', ...]}}\n\n{memory_block}"
    res = call_api(
        [{"role": "user", "content": prompt}],
        model="deepseek-chat",
        stream=False,
        response_format={"type": "json_object"},
    )
    if res:
        try:
            content = res.json()["choices"][0]["message"]["content"]
            return json.loads(content).get("compressed")
        except:
            return None
    return None
