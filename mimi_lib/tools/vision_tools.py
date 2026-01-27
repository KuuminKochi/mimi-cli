import requests
import base64
import os
from mimi_lib.tools.registry import register_tool
from mimi_lib.config import get_config


@register_tool(
    "describe_image",
    "Analyze an image using a vision model.",
    {
        "type": "object",
        "properties": {"image_path": {"type": "string"}, "prompt": {"type": "string"}},
        "required": ["image_path"],
    },
)
def describe_image(image_path: str, prompt: str = "Describe this image in detail."):
    config = get_config()
    api_key = config.get("xai_api_key")
    if not api_key:
        return "Error: XAI API key not found."

    try:
        with open(os.path.expanduser(image_path), "rb") as img_file:
            base64_image = base64.b64encode(img_file.read()).decode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        payload = {
            "model": "grok-vision-beta",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            },
                        },
                    ],
                }
            ],
            "stream": False,
            "temperature": 0.5,
        }

        res = requests.post(
            "https://api.x.ai/v1/chat/completions", headers=headers, json=payload
        )
        if res.status_code != 200:
            return f"Vision API Error: {res.text}"
        return res.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Vision analysis failed: {e}"
