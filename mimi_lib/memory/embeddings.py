import json
import math
import requests
from typing import List, Dict, Optional
from mimi_lib.config import get_config, MEMORY_VECTORS_FILE, MEMORY_ARCHIVE_FILE

# Global Session
_http_session = None


def get_session():
    global _http_session
    if _http_session is None:
        _http_session = requests.Session()
    return _http_session


def get_embedding(text: str) -> Optional[List[float]]:
    config = get_config()
    session = get_session()

    # Using OpenRouter by default as per existing code
    url = f"{config['openrouter_base_url']}/embeddings"
    headers = {
        "Authorization": f"Bearer {config['openrouter_api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "openai/text-embedding-3-small",
        "input": text.replace("\n", " "),
    }

    try:
        # Increased timeout to 60 seconds and added basic retry
        res = session.post(url, headers=headers, json=payload, timeout=60)
        if res.ok:
            return res.json()["data"][0]["embedding"]
        else:
            print(f"[Embeddings] API Error: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"[Embeddings] Connection failed: {e}")
    return None


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot_product = sum(a * b for a, b in zip(v1, v2))
    magnitude1 = math.sqrt(sum(a * a for a in v1))
    magnitude2 = math.sqrt(sum(b * b for b in v2))
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
    return dot_product / (magnitude1 * magnitude2)


def load_vectors() -> Dict[str, List[float]]:
    if not MEMORY_VECTORS_FILE.exists():
        return {}
    try:
        with open(MEMORY_VECTORS_FILE, "r") as f:
            return json.load(f)
    except:
        return {}


def save_vectors(vectors: Dict[str, List[float]]):
    with open(MEMORY_VECTORS_FILE, "w") as f:
        json.dump(vectors, f)


def semantic_search(
    query_text: str, top_k: int = 3, vectors_cache: Optional[Dict] = None
) -> List[Dict]:
    query_vector = get_embedding(query_text)
    if not query_vector:
        return []

    vectors = vectors_cache if vectors_cache is not None else load_vectors()
    if not vectors or not MEMORY_ARCHIVE_FILE.exists():
        return []

    with open(MEMORY_ARCHIVE_FILE, "r") as f:
        archive = json.load(f)

    scored_memories = []
    for item in archive:
        mem_id = str(item.get("id"))
        if mem_id in vectors:
            sim = cosine_similarity(query_vector, vectors[mem_id])
            if sim > 0.3:
                scored_memories.append((sim, item))

    scored_memories.sort(key=lambda x: x[0], reverse=True)
    return [item for score, item in scored_memories[:top_k]]
