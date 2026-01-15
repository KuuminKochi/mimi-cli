import requests
import concurrent.futures
from typing import List
from mimi_lib.tools.registry import register_tool

def _web_search(query: str) -> str:
    try:
        from ddgs import DDGS
        results = list(DDGS().text(query, max_results=3))
        if not results:
            return "No results found."
        return "\n\n".join([f"[{r['title']}]({r['href']})\n{r['body']}" for r in results])
    except Exception as e:
        return f"Search error: {e}"

def _web_fetch(url: str) -> str:
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()

        content_type = res.headers.get("Content-Type", "").lower()
        if "application/pdf" in content_type or url.lower().endswith(".pdf"):
            import pypdf
            from io import BytesIO
            reader = pypdf.PdfReader(BytesIO(res.content))
            text = [page.extract_text() for page in reader.pages]
            return f"--- PDF Content ({url}) ---\n" + "\n".join(text)[:20000]

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(res.text, "html.parser")
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        text = soup.get_text(separator="\n")
        lines = (line.strip() for line in text.splitlines())
        return "\n".join(line for line in lines if line)[:15000]
    except Exception as e:
        return f"Fetch error: {e}"

@register_tool(
    "web_search",
    "Search the internet for up-to-date information.",
    {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
)
def web_search(query: str):
    return _web_search(query)

@register_tool(
    "web_batch_search",
    "Search multiple queries in parallel for efficiency.",
    {"type": "object", "properties": {"queries": {"type": "array", "items": {"type": "string"}}}, "required": ["queries"]}
)
def web_batch_search(queries: List[str]):
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(_web_search, q): q for q in queries}
        for future in concurrent.futures.as_completed(futures):
            results.append(f"--- Results for: {futures[future]} ---\n{future.result()}")
    return "\n\n".join(results)

@register_tool(
    "web_fetch",
    "Read the content of a specific URL (HTML or PDF).",
    {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}
)
def web_fetch(url: str):
    return _web_fetch(url)
