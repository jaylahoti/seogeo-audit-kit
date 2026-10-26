"""Citation tracking in other AI engines, with the self-hoster's own keys.

The same questions Claude was asked go to ChatGPT (OpenAI Responses API + web search),
Perplexity (Sonar) and Gemini (Google Search grounding). Each engine's answer is reduced
to the same shape Claude's search returns: answer text, cited URLs, and the URLs its
search found. An engine runs only when its key is set; the hosted demo sets none.

These calls go to fixed API hosts, never to user URLs, and are billed to the key's owner.
Each response parser is a pure function so it can be tested without a key.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from app.config import settings

TIMEOUT = httpx.Timeout(60.0, connect=10.0)


def parse_openai(data: dict) -> dict:
    text, cited, found, searches = [], [], [], 0
    for item in data.get("output", []):
        if item.get("type") == "web_search_call":
            searches += 1
            found += [s.get("url") for s in (item.get("action") or {}).get("sources") or [] if s.get("url")]
        elif item.get("type") == "message":
            for c in item.get("content", []):
                if c.get("type") == "output_text":
                    text.append(c.get("text", ""))
                    cited += [a["url"] for a in c.get("annotations", []) if a.get("type") == "url_citation" and a.get("url")]
    return {"text": "\n".join(text), "cited_urls": cited, "result_urls": found or cited, "searches": searches}


def parse_perplexity(data: dict) -> dict:
    text = ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "")
    cited = [u for u in data.get("citations") or [] if isinstance(u, str)]
    found = [r["url"] for r in data.get("search_results") or [] if r.get("url")]
    return {"text": text, "cited_urls": cited, "result_urls": found or cited, "searches": 1 if (cited or found) else 0}


def _gemini_url(chunk: dict) -> str | None:
    web = chunk.get("web") or {}
    uri, title = web.get("uri") or "", (web.get("title") or "").strip()
    # Grounding links are Google redirect URLs; the title carries the source's domain.
    if "vertexaisearch" in uri or "grounding-api-redirect" in uri:
        return f"https://{title}/" if title and "." in title and " " not in title else None
    return uri or None


def parse_gemini(data: dict) -> dict:
    cand = (data.get("candidates") or [{}])[0]
    text = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", []))
    meta = cand.get("groundingMetadata") or {}
    urls = [u for c in meta.get("groundingChunks") or [] if (u := _gemini_url(c))]
    # Chunks that support part of the answer are the citations; the rest were found but not used.
    used = {i for s in meta.get("groundingSupports") or [] for i in s.get("groundingChunkIndices", [])}
    chunks = meta.get("groundingChunks") or []
    cited = [u for i, c in enumerate(chunks) if i in used and (u := _gemini_url(c))] if used else urls
    return {"text": text, "cited_urls": cited, "result_urls": urls, "searches": len(meta.get("webSearchQueries") or [])}


async def _openai(client: httpx.AsyncClient, q: str) -> dict:
    r = await client.post("https://api.openai.com/v1/responses",
                          headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                          json={"model": settings.openai_model, "input": q, "tools": [{"type": "web_search"}],
                                "include": ["web_search_call.action.sources"]})
    r.raise_for_status()
    return parse_openai(r.json())


async def _perplexity(client: httpx.AsyncClient, q: str) -> dict:
    r = await client.post("https://api.perplexity.ai/chat/completions",
                          headers={"Authorization": f"Bearer {settings.perplexity_api_key}"},
                          json={"model": settings.perplexity_model, "messages": [{"role": "user", "content": q}]})
    r.raise_for_status()
    return parse_perplexity(r.json())


async def _gemini(client: httpx.AsyncClient, q: str) -> dict:
    r = await client.post(f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent",
                          headers={"x-goog-api-key": settings.gemini_api_key},
                          json={"contents": [{"parts": [{"text": q}]}], "tools": [{"google_search": {}}]})
    r.raise_for_status()
    return parse_gemini(r.json())


Ask = Callable[[httpx.AsyncClient, str], Awaitable[dict]]


def configured() -> list[tuple[str, Ask]]:
    out: list[tuple[str, Ask]] = []
    if settings.openai_api_key:
        out.append(("ChatGPT", _openai))
    if settings.perplexity_api_key:
        out.append(("Perplexity", _perplexity))
    if settings.gemini_api_key:
        out.append(("Gemini", _gemini))
    return out


async def ask_all(questions: list[str], engines: list[tuple[str, Ask]] | None = None) -> dict[str, list[dict[str, Any] | None]]:
    """engine name -> one result (or None on failure) per question, in order."""
    engines = configured() if engines is None else engines
    if not engines or not questions:
        return {}
    sem = asyncio.Semaphore(4)

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        async def one(ask: Ask, q: str):
            async with sem:
                t = time.perf_counter()
                try:
                    res = await ask(client, q)
                except (httpx.HTTPError, ValueError, KeyError, TypeError) as e:
                    return {"error": f"{type(e).__name__}: {str(e)[:120]}"}
                res["ms"] = int((time.perf_counter() - t) * 1000)
                return res

        results = await asyncio.gather(*(asyncio.gather(*(one(ask, q) for q in questions)) for _, ask in engines))
    return {name: list(r) for (name, _), r in zip(engines, results, strict=True)}
