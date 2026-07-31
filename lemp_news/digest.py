from __future__ import annotations

import json

import httpx

from app.settings import get_settings

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-5"


class NewsDigestError(Exception):
    pass


def _build_prompt(articles: list[dict]) -> str:
    lines = []
    for a in articles:
        tickers = ", ".join(a.get("tickers") or [])
        published = a.get("published_at")
        published_str = published.isoformat() if hasattr(published, "isoformat") else str(published)
        teaser = a.get("teaser") or ""
        lines.append(f"- [{tickers}] {a['title']} ({published_str}): {teaser}")

    articles_block = "\n".join(lines) or "No articles in this window."

    return f"""You are a portfolio-focused news analyst. Below are recent news \
items covering the user's watchlist tickers.

ARTICLES:
{articles_block}

Write a single consolidated digest covering what happened across these holdings \
— group related items by ticker or theme where it makes sense, skip pure noise \
(routine analyst reiterations with no new information, thin PR pieces), and \
flag anything that looks genuinely material (earnings surprises, guidance \
changes, M&A, regulatory action, executive changes).

This is a factual news summary, not investment advice — do not phrase anything \
as a buy/sell recommendation.

Return ONLY valid JSON (no markdown fences, no prose outside the JSON) matching \
exactly this shape:
{{
  "digest": "the consolidated summary, several paragraphs, plain text with \\n\\n between paragraphs",
  "highlights": ["short bullet strings for the 2-5 most material items, empty list if nothing stood out"]
}}
"""


def generate_news_digest(articles: list[dict]) -> dict:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise NewsDigestError("ANTHROPIC_API_KEY is not configured")

    if not articles:
        return {"digest": "No news for your watchlist in this window.", "highlights": []}

    prompt = _build_prompt(articles)

    try:
        response = httpx.post(
            ANTHROPIC_URL,
            headers={
                "x-api-key": settings.anthropic_api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": MODEL,
                "max_tokens": 4096,
                "messages": [
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=httpx.Timeout(
                connect=15.0, read=120.0, write=30.0, pool=15.0
            ),
        )
    except httpx.HTTPError as exc:
        raise NewsDigestError(
            f"Request to Anthropic API failed: {exc}"
        ) from exc

    if response.status_code != 200:
        raise NewsDigestError(
            f"Anthropic API returned {response.status_code}: "
            f"{response.text[:500]}"
        )

    data = response.json()

    if data.get("stop_reason") == "max_tokens":
        raise NewsDigestError(
            "Response was cut off at the max_tokens limit before finishing "
            "the JSON — the model needed more room than 4096 tokens allowed."
        )

    text_blocks = [
        block["text"]
        for block in data.get("content", [])
        if block.get("type") == "text"
    ]
    raw_text = "\n".join(text_blocks).strip()
    cleaned = raw_text.replace("```json", "").replace("```", "").strip()

    try:
        parsed = json.loads(cleaned, strict=False)
    except json.JSONDecodeError as exc:
        raise NewsDigestError(
            f"Could not parse model response as JSON: {exc}. "
            f"Raw response started with: {raw_text[:200]}"
        ) from exc

    if "digest" not in parsed:
        raise NewsDigestError(
            f"Model response missing required key 'digest'. Got: {list(parsed.keys())}"
        )

    return parsed
