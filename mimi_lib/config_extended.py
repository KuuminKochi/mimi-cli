from typing import Dict, Any, Optional

MODEL_ALIASES = {
    # DeepSeek (backward compatible)
    "chat": {
        "id": "deepseek-chat",
        "provider": "deepseek",
        "description": "Fast conversational model",
    },
    "reasoner": {
        "id": "deepseek-reasoner",
        "provider": "deepseek",
        "description": "Chain-of-thought reasoning model",
    },
    # OpenRouter (Moonshot)
    "kimi": {
        "id": "or/moonshotai/kimi-k2.5",
        "provider": "openrouter",
        "description": "Moonshot AI K2.5 multimodal with agent swarm",
    },
}


def resolve_alias(alias: str) -> Optional[Dict[str, Any]]:
    """Resolve alias to full model config."""
    return MODEL_ALIASES.get(alias)
