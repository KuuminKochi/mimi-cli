import requests
from mimi_lib.config import get_config

_session = requests.Session()


def call_generic_api(messages, model, stream=True, tools=None, response_format=None):
    """
    Generic API handler for non-DeepSeek models.
    Routes based on model ID prefix:
    - "or/" → OpenRouter
    - "grok-" → xAI
    - "gpt-" → OpenAI

    Returns: requests.Response object or None
    """
    config = get_config()

    def get_params(target_model):
        headers = {"Content-Type": "application/json"}
        endpoint = None
        actual_model = target_model

        if target_model.startswith("or/"):
            endpoint = f"{config['openrouter_base_url']}/chat/completions"
            headers["Authorization"] = f"Bearer {config['openrouter_api_key']}"
            actual_model = target_model[3:]
        elif "grok" in target_model:
            endpoint = f"{config['xai_base_url']}/chat/completions"
            headers["Authorization"] = f"Bearer {config['xai_api_key']}"
        elif target_model.startswith("gpt-"):
            if config.get("openai_api_key"):
                endpoint = "https://api.openai.com/v1/chat/completions"
                headers["Authorization"] = f"Bearer {config['openai_api_key']}"
            else:
                return None, None, None
        else:
            return None, None, None

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

        if "messages" in payload:
            for m in payload["messages"]:
                if m.get("content") is None:
                    m["content"] = ""

        return endpoint, headers, payload

    endpoint, headers, payload = get_params(model)

    if not endpoint:
        print(f"[API] Error: Unknown model or missing API key for '{model}'")
        return None

    try:
        res = _session.post(
            endpoint, headers=headers, json=payload, stream=stream, timeout=120
        )
        res.raise_for_status()
        return res
    except Exception as e:
        print(f"[API] Error: {e}")
        return None
