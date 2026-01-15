import requests
import json
import os
import math
from typing import List, Dict, Optional

# Paths
CONFIG_FILE = "/home/kuumin/Projects/mimi-cli/deepseek_config.json"
VECTORS_FILE = "/home/kuumin/Projects/mimi-cli/mimi_memory_vectors.json"

# Caches
_config_cache = None
_http_session = None


def load_config():
    global _config_cache
    if _config_cache:
        return _config_cache
    if not os.path.exists(CONFIG_FILE):
        return None
    try:
        with open(CONFIG_FILE, "r") as f:
            _config_cache = json.load(f)
            return _config_cache
    except:
        return None


def get_session():
    global _http_session
    if _http_session is None:
        _http_session = requests.Session()
    return _http_session


def get_embedding(text: str) -> Optional[List[float]]:
    config = load_config()
    if not config:
        return None

    session = get_session()
    url = f"{config.get('openrouter_base_url', 'https://openrouter.ai/api/v1')}/embeddings"
    headers = {
        "Authorization": f"Bearer {config.get('openrouter_api_key')}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.get("embedding_model", "openai/text-embedding-3-small"),
        "input": text.replace("\n", " "),
    }

    try:
        res = session.post(url, headers=headers, json=payload, timeout=10)
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
    if not os.path.exists(VECTORS_FILE):
        return {}
    try:
        with open(VECTORS_FILE, "r") as f:
            return json.load(f)
    except:
        return {}


def save_vectors(vectors: Dict[str, List[float]]):
    with open(VECTORS_FILE, "w") as f:
        json.dump(vectors, f)


def semantic_search(
    query_text: str, top_k: int = 3, vectors_cache: Optional[Dict] = None
) -> List[Dict]:
    """Returns the most relevant memories from the archive using semantic similarity."""
    query_vector = get_embedding(query_text)
    if not query_vector:
        return []

    vectors = vectors_cache if vectors_cache is not None else load_vectors()
    if not vectors:
        return []

    archive_path = "/home/kuumin/Projects/mimi-cli/mimi_memory_archive.json"
    if not os.path.exists(archive_path):
        return []

    with open(archive_path, "r") as f:
        archive = json.load(f)

    scored_memories = []
    for item in archive:
        mem_id = str(item.get("id"))
        if mem_id in vectors:
            sim = cosine_similarity(query_vector, vectors[mem_id])
            if sim > 0.3:  # Minimum similarity threshold
                scored_memories.append((sim, item))

    scored_memories.sort(key=lambda x: x[0], reverse=True)
    return [item for score, item in scored_memories[:top_k]]


def index_missing_memories():
    """Checks the archive and generates embeddings for any memory not yet indexed."""
    archive_path = "/home/kuumin/Projects/mimi-cli/mimi_memory_archive.json"
    if not os.path.exists(archive_path):
        return

    with open(archive_path, "r") as f:
        archive = json.load(f)

    vectors = load_vectors()
    changed = False

    print(f"[Embeddings] Checking {len(archive)} memories for missing vectors...")

    for item in archive:
        mem_id = str(item.get("id"))
        if mem_id not in vectors:
            print(f"[Embeddings] Indexing: {item.get('content')[:50]}...")
            vector = get_embedding(item.get("content"))
            if vector:
                vectors[mem_id] = vector
                changed = True
                if len(vectors) % 10 == 0:
                    save_vectors(vectors)

    if changed:
        save_vectors(vectors)
        print("[Embeddings] Indexing complete.")
    else:
        print("[Embeddings] All memories already indexed.")


if __name__ == "__main__":
    index_missing_memories()
