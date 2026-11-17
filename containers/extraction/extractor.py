"""CSIP extraction service: crawl4ai in a Linux container.

Runs on the host as a loopback-only HTTP service. This machine's Windows
Application Control policy blocks crawl4ai's compiled dependencies on the
host, so extraction runs inside Linux Docker instead (see
docs/runbooks/local-development.md).

Endpoints
- GET  /healthz          liveness
- POST /extract_raw      extract from ALREADY-CAPTURED artifact HTML (no
                         network) — the pipeline-preferred path: extraction
                         from stored artifacts keeps acquisition governed
                         and idempotent.
- POST /extract          fetch + extract a URL. Callers MUST only pass URLs
                         authorized by an approved SourceProfile/policy plan;
                         this service performs no policy checks itself.

The LLM never performs extraction or persistence; this service returns
deterministic structured output only (blueprint invariant).
"""

from __future__ import annotations

import json
import sys
from typing import Any

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.async_crawler_strategy import AsyncHTTPCrawlerStrategy
from fastapi import FastAPI
from pydantic import BaseModel, Field

try:
    from crawl4ai import LXMLWebScrapingStrategy  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - fallback import path
    from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy  # type: ignore[no-redef]

app = FastAPI(title="csip-extraction", version="0.1.0")


class RawExtractRequest(BaseModel):
    """Extract from already-captured artifact HTML (no network access)."""

    html: str = Field(min_length=1)
    url: str = Field(default="artifact://local", description="Reference label only; never fetched")
    base_url: str | None = Field(default=None, description="Optional base URL for link resolution")


class UrlExtractRequest(BaseModel):
    url: str = Field(min_length=1, description="MUST be policy-authorized by the caller")


def _result_payload(result: Any, url: str) -> dict[str, Any]:
    markdown = getattr(result, "markdown", "")
    # 0.9.x returns a MarkdownGenerationResult; older builds a plain string.
    if hasattr(markdown, "raw_markdown"):
        markdown_text = markdown.raw_markdown
        fit_markdown = getattr(markdown, "fit_markdown", "") or markdown_text
    else:
        markdown_text = str(markdown or "")
        fit_markdown = markdown_text
    return {
        "url": url,
        "success": bool(getattr(result, "success", True)),
        "title": getattr(result, "title", None),
        "markdown": markdown_text,
        "fit_markdown": fit_markdown,
        "metadata": dict(getattr(result, "metadata", None) or {}),
        "links": _safe_links(getattr(result, "links", None)),
        "error": getattr(result, "error_message", None),
    }


def _safe_links(links: Any) -> dict[str, list[str]]:
    if not links:
        return {}
    try:
        return {
            "internal": [link.get("href", "") for link in links.get("internal", [])],
            "external": [link.get("href", "") for link in links.get("external", [])],
        }
    except Exception:
        return {}


async def _extract_html(html: str | None, url: str, base_url: str | None = None) -> dict[str, Any]:
    crawler = AsyncWebCrawler(crawler_strategy=AsyncHTTPCrawlerStrategy())
    if html is not None:
        # crawl4ai's HTTP strategy supports raw content via the "raw://" URL
        # scheme; base_url (optional) resolves relative links.
        crawl_url = "raw://" + html
        run_config = CrawlerRunConfig(
            scraping_strategy=LXMLWebScrapingStrategy(), base_url=base_url
        )
    else:
        crawl_url = url
        run_config = CrawlerRunConfig(scraping_strategy=LXMLWebScrapingStrategy())
    try:
        result = await crawler.arun(url=crawl_url, config=run_config)
        return _result_payload(result, url)
    finally:
        await crawler.close()


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "csip-extraction"}


@app.post("/extract_raw")
async def extract_raw(request: RawExtractRequest) -> dict[str, Any]:
    return await _extract_html(request.html, request.url, request.base_url)


@app.post("/extract")
async def extract(request: UrlExtractRequest) -> dict[str, Any]:
    if not request.url.lower().startswith(("http://", "https://")):
        return {"success": False, "error": "only http(s) URLs are supported", "url": request.url}
    return await _extract_html(None, request.url)


def selftest() -> int:
    """Offline smoke test: extract from embedded fixture HTML, print JSON."""
    import asyncio

    fixture = (
        "<html><head><title>Widget A</title></head><body>"
        "<h1>Widget A</h1><p>Price: $12.50</p><p>SKU: A-1001</p>"
        "</body></html>"
    )
    payload = asyncio.run(_extract_html(fixture, "artifact://selftest"))
    compact = {
        "success": payload["success"],
        "title": payload["title"],
        "has_markdown": bool(payload["markdown"]),
        "markdown_head": payload["markdown"][:60],
    }
    print(json.dumps(compact, indent=2))
    return 0 if payload["success"] else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8100)
