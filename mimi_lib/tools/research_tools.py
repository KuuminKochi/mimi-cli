import concurrent.futures
from mimi_lib.tools.registry import register_tool
from mimi_lib.tools.web_tools import _web_search, _web_fetch


@register_tool(
    "deep_research",
    "Conduct an autonomous deep dive into a topic (Search -> Read 3 Links -> Summarize).",
    {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "The research question or topic.",
            }
        },
        "required": ["topic"],
    },
)
def deep_research(topic: str) -> str:
    """
    Performs a single-shot deep research loop:
    1. Search for the topic.
    2. Extract up to 3 diverse URLs.
    3. Fetch content in parallel.
    4. Compile a raw dossier for Mimi to analyze.
    """
    # 1. Search
    search_res = _web_search(topic)
    if "No results" in search_res:
        return f"Deep Research Failed: No initial search results for '{topic}'."

    # 2. Extract URLs (Simple extraction from markdown format [Title](Url))
    import re

    urls = re.findall(r"\]\((https?://[^)]+)\)", search_res)
    # Deduplicate and limit to top 3
    unique_urls = []
    seen = set()
    for u in urls:
        if u not in seen and "youtube.com" not in u:  # Skip youtube for text reading
            seen.add(u)
            unique_urls.append(u)
            if len(unique_urls) >= 3:
                break

    if not unique_urls:
        return (
            f"Deep Research: Found search results but no readable links.\n{search_res}"
        )

    # 3. Parallel Fetch
    fetched_content = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(_web_fetch, url): url for url in unique_urls}
        for future in concurrent.futures.as_completed(futures):
            url = futures[future]
            try:
                content = future.result()
                # Truncate each page to 5000 chars to fit context
                fetched_content.append(f"=== SOURCE: {url} ===\n{content[:5000]}\n")
            except Exception as e:
                fetched_content.append(f"=== FAILED: {url} ===\n{str(e)}\n")

    # 4. Compile
    dossier = f"**Deep Research Dossier for '{topic}'**\n\n"
    dossier += "\n".join(fetched_content)

    return dossier
