from __future__ import annotations

import json
from urllib import parse, request

from studygraph.utils import call_with_retry


def _http_get_json(url: str) -> dict:
    def _request_body() -> dict:
        req = request.Request(
            url=url,
            headers={
                "Accept": "application/json",
                "User-Agent": "StudyGraph/1.0 (educational app; contact: local-dev)",
            },
            method="GET",
        )
        with request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read().decode("utf-8"))

    return call_with_retry(_request_body)


def fetch_wikipedia_summary(topic: str) -> dict[str, str | bool]:
    query = (topic or "").strip()
    if not query:
        return {"success": False, "error": "Empty topic."}

    encoded = parse.quote(query.replace(" ", "_"))
    rest_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}"
    action_url = (
        "https://en.wikipedia.org/w/api.php"
        f"?action=query&prop=extracts&exintro=1&explaintext=1&format=json&titles={encoded}"
    )

    try:
        data = _http_get_json(rest_url)
        summary = str(data.get("extract", "")).strip()
        title = str(data.get("title", query)).strip()
        page = str(data.get("content_urls", {}).get("desktop", {}).get("page", "")).strip()
        if not summary:
            raise ValueError("REST summary empty")
        if len(summary) > 700:
            summary = summary[:700].rstrip() + "..."
        return {
            "success": True,
            "title": title,
            "summary": summary,
            "source_url": page or f"https://en.wikipedia.org/wiki/{encoded}",
        }
    except Exception:
        try:
            data = _http_get_json(action_url)
            pages = data.get("query", {}).get("pages", {})
            page_data = next(iter(pages.values())) if isinstance(pages, dict) and pages else {}
            summary = str(page_data.get("extract", "")).strip()
            title = str(page_data.get("title", query)).strip()
            if not summary:
                return {"success": False, "error": "No summary returned."}
            if len(summary) > 700:
                summary = summary[:700].rstrip() + "..."
            return {
                "success": True,
                "title": title,
                "summary": summary,
                "source_url": f"https://en.wikipedia.org/wiki/{parse.quote(title.replace(' ', '_'))}",
            }
        except Exception:
            return {"success": False, "error": "External knowledge fetch failed."}
