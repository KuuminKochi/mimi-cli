import os
import json
import threading
import time
from pathlib import Path
from datetime import datetime
from mimi_lib.config import VAULT_PATH, VAULT_VECTORS_FILE, VAULT_INDEX_LOG
from mimi_lib.memory.embeddings import get_embedding, cosine_similarity

# Global Lock to prevent multiple indexers running at once
_INDEX_LOCK = threading.Lock()
# Flag to indicate if an indexing run is currently active
_IS_INDEXING = False
# Flag to indicate if another run was requested while one was active
_RERUN_REQUESTED = False

# --- PERFORMANCE CACHE ---
_VECTOR_CACHE = None
_VECTOR_CACHE_MTIME = 0
_CACHE_LOCK = threading.Lock()


def _load_vectors_cached():
    """Thread-safe cached loading of vectors."""
    global _VECTOR_CACHE, _VECTOR_CACHE_MTIME

    if not VAULT_VECTORS_FILE.exists():
        return {}

    current_mtime = VAULT_VECTORS_FILE.stat().st_mtime

    with _CACHE_LOCK:
        if _VECTOR_CACHE is not None and current_mtime == _VECTOR_CACHE_MTIME:
            return _VECTOR_CACHE

        try:
            vectors = json.loads(VAULT_VECTORS_FILE.read_text())
            _VECTOR_CACHE = vectors
            _VECTOR_CACHE_MTIME = current_mtime
            return vectors
        except:
            return {}


def _update_vector_cache(vectors):
    """Directly update cache after indexing."""
    global _VECTOR_CACHE, _VECTOR_CACHE_MTIME
    with _CACHE_LOCK:
        _VECTOR_CACHE = vectors
        if VAULT_VECTORS_FILE.exists():
            _VECTOR_CACHE_MTIME = VAULT_VECTORS_FILE.stat().st_mtime


def chunk_text(text, max_chars=1500):
    """Simple chunking by paragraphs or sentences."""
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = ""

    for p in paragraphs:
        if len(current_chunk) + len(p) < max_chars:
            current_chunk += p + "\n\n"
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = p + "\n\n"

    if current_chunk:
        chunks.append(current_chunk.strip())
    return chunks


def get_vault_files():
    """Recursively find all markdown files in the vault, excluding hidden dirs."""
    files = []
    for root, dirs, filenames in os.walk(VAULT_PATH):
        # Skip hidden directories like .obsidian, .git
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in filenames:
            if f.startswith("."):
                continue
            if f.endswith(".md"):
                files.append(Path(root) / f)
    return files


def _run_indexing_logic(force=False, silent=True):
    """Internal function that performs the actual indexing logic (synchronous)."""
    index_log = {}
    if VAULT_INDEX_LOG.exists():
        try:
            index_log = json.loads(VAULT_INDEX_LOG.read_text())
        except:
            pass

    # Load initial vectors (uncached here as we are modifying)
    vectors = {}
    if VAULT_VECTORS_FILE.exists():
        try:
            vectors = json.loads(VAULT_VECTORS_FILE.read_text())
        except:
            pass

    files = get_vault_files()
    updated_count = 0

    for fpath in files:
        rel_path = str(fpath.relative_to(VAULT_PATH))
        mtime = fpath.stat().st_mtime

        # Skip if not changed
        if (
            not force
            and rel_path in index_log
            and index_log[rel_path]["mtime"] == mtime
        ):
            continue

        if not silent:
            print(f"Indexing: {rel_path}")
        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
            if not content.strip():
                # Update log for empty files to prevent re-indexing loop
                index_log[rel_path] = {
                    "mtime": mtime,
                    "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                }
                # Remove from vectors if it exists (file became empty)
                if rel_path in vectors:
                    del vectors[rel_path]
                updated_count += 1
                continue

            chunks = chunk_text(content)
            file_vectors = []

            for i, chunk in enumerate(chunks):
                # Add context (filename) to the chunk for better retrieval
                contextual_chunk = f"File: {rel_path}\nContent: {chunk}"
                embedding = get_embedding(contextual_chunk)
                if embedding:
                    file_vectors.append(
                        {"chunk_index": i, "text": chunk, "embedding": embedding}
                    )

            if file_vectors:
                vectors[rel_path] = file_vectors
                index_log[rel_path] = {
                    "mtime": mtime,
                    "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                }
                updated_count += 1

            # Periodically save progress every 5 files
            if updated_count % 5 == 0:
                VAULT_VECTORS_FILE.write_text(json.dumps(vectors))
                VAULT_INDEX_LOG.write_text(json.dumps(index_log, indent=2))

        except Exception as e:
            if not silent:
                print(f"Failed to index {rel_path}: {e}")

    if updated_count > 0:
        VAULT_VECTORS_FILE.write_text(json.dumps(vectors))
        VAULT_INDEX_LOG.write_text(json.dumps(index_log, indent=2))

        # UPDATE CACHE
        _update_vector_cache(vectors)

    return f"Indexed {updated_count} new/updated files. Total files in index: {len(index_log)}"


def _indexer_worker(force=False, silent=True):
    """Worker thread that keeps running as long as reruns are requested."""
    global _IS_INDEXING, _RERUN_REQUESTED

    while True:
        try:
            _run_indexing_logic(force, silent=silent)
        except Exception as e:
            if not silent:
                print(f"Indexer crashed: {e}")

        # Check if a rerun was requested while we were working
        with _INDEX_LOCK:
            if not _RERUN_REQUESTED:
                _IS_INDEXING = False
                break
            # Reset flag and loop again
            _RERUN_REQUESTED = False
            if not silent:
                print("Processing queued index request...")
            # We don't break, so the loop repeats


def trigger_background_index(force=False, silent=True):
    """
    Thread-safe non-blocking trigger for vault indexing.
    If an indexer is already running, queues a rerun after it finishes.
    """
    global _IS_INDEXING, _RERUN_REQUESTED

    with _INDEX_LOCK:
        if _IS_INDEXING:
            _RERUN_REQUESTED = True
            return "Indexing queued (another process is active)."

        _IS_INDEXING = True
        threading.Thread(
            target=_indexer_worker, args=(force, silent), daemon=True
        ).start()
        return "Background indexing started."


def index_vault(force=False):
    """
    Public API: triggers indexing and waits for result (or returns status message).
    kept for backward compatibility with direct calls, but operates async now
    or logic could be adapted if synchronous behavior is strictly required by some caller.

    For now, we map this to trigger_background_index to enforce safety everywhere.
    """
    return trigger_background_index(force)


def search_vault(query, top_k=5):
    """Semantic search across the vault vectors with attribution and caching."""
    query_vector = get_embedding(query)
    if not query_vector:
        return []

    # Use Cache
    vectors = _load_vectors_cached()
    if not vectors:
        return []

    results = []
    for rel_path, chunks in vectors.items():
        for chunk_data in chunks:
            sim = cosine_similarity(query_vector, chunk_data["embedding"])
            if sim > 0.4:  # Similarity threshold
                text = chunk_data["text"]

                # --- ATTRIBUTION LOGIC ---
                is_mimi = False
                if "Mimi/Sessions" in rel_path:
                    is_mimi = True
                elif "mimi_signed: true" in text or "Signed by Mimi" in text:
                    is_mimi = True
                elif "_Signed by Mimi" in text:
                    is_mimi = True

                if is_mimi:
                    attributed_text = f"[AUTHOR: Mimi (Auto-Memory)]\n{text}"
                else:
                    attributed_text = f"[AUTHOR: Kuumin]\n{text}"

                results.append(
                    {"score": sim, "path": rel_path, "text": attributed_text}
                )

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]
