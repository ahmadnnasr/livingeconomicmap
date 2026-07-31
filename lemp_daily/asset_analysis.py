from __future__ import annotations

import json

import httpx

from app.settings import get_settings

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-5"


class AssetAnalysisError(Exception):
    pass


def _build_prompt(
    macro: list[dict],
    beliefs: list[dict],
    regimes: list[dict],
) -> str:
    macro_lines = "\n".join(
        f"- {m['title']} ({m['series_id']}): {m['value']} {m.get('units', '')} "
        f"as of {m['observation_date']}"
        for m in macro
    ) or "none available"

    belief_lines = "\n".join(
        f"- {b['belief_key']}: {b['probability'] * 100:.1f}% "
        f"(confidence {b['confidence'] * 100:.0f}%)"
        for b in beliefs
    ) or "none available"

    regime_lines = "\n".join(
        f"- {r['regime_key']}: {r['probability'] * 100:.1f}%"
        for r in regimes
    ) or "none available"

    return f"""You are a market historian and portfolio strategist. Use web search \
to ground every historical claim in real, verifiable market history — never invent \
performance figures or dates.

CURRENT MACRO DATA:
{macro_lines}

CURRENT BELIEFS (model-derived probabilities):
{belief_lines}

CURRENT REGIMES (model-derived probabilities):
{regime_lines}

Task:
1. Identify 2-3 historical periods whose macro/liquidity conditions most closely \
resemble today's, searching the web to confirm real dates and real outcomes rather \
than relying on memory alone.
2. For each analog, note briefly which asset classes underperformed and which \
outperformed during and after that period, grounded in what you find.
3. Synthesize a general list of asset classes that have historically struggled in \
this type of environment, and a list that has historically held up or done well — \
each with a one-sentence rationale tied back to the analogs and current beliefs \
above.
4. Write a short overall synthesis (2-3 sentences).

This is historical pattern-matching for educational purposes, not personalized \
financial advice — do not phrase conclusions as direct buy/sell recommendations, \
and be honest about uncertainty; historical analogs are never perfect repeats.

Return ONLY valid JSON (no markdown fences, no prose outside the JSON) matching \
exactly this shape:
{{
  "historical_analogs": [
    {{"period": "e.g. 1994-1995", "similarity": "1-2 sentences on why this period resembles today, and what happened to markets then"}}
  ],
  "assets_to_avoid": [
    {{"asset_class": "e.g. Long-duration unprofitable growth equities", "rationale": "1 sentence, tied to the analogs/beliefs above"}}
  ],
  "assets_favored": [
    {{"asset_class": "e.g. Short-duration high-quality credit", "rationale": "1 sentence, tied to the analogs/beliefs above"}}
  ],
  "synthesis": "2-3 sentence overall takeaway"
}}

Include 2-3 analogs, 3-5 entries each in assets_to_avoid and assets_favored.
"""


def generate_asset_analysis(
    macro: list[dict],
    beliefs: list[dict],
    regimes: list[dict],
) -> dict:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise AssetAnalysisError(
            "ANTHROPIC_API_KEY is not configured"
        )

    prompt = _build_prompt(macro, beliefs, regimes)

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
                "tools": [
                    {"type": "web_search_20250305", "name": "web_search"},
                ],
            },
            timeout=httpx.Timeout(
                connect=15.0, read=180.0, write=30.0, pool=15.0
            ),
        )
    except httpx.HTTPError as exc:
        raise AssetAnalysisError(
            f"Request to Anthropic API failed: {exc}"
        ) from exc

    if response.status_code != 200:
        raise AssetAnalysisError(
            f"Anthropic API returned {response.status_code}: "
            f"{response.text[:500]}"
        )

    data = response.json()

    if data.get("stop_reason") == "max_tokens":
        raise AssetAnalysisError(
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
        raise AssetAnalysisError(
            f"Could not parse model response as JSON: {exc}. "
            f"Raw response started with: {raw_text[:200]}"
        ) from exc

    required_keys = ["historical_analogs", "assets_to_avoid", "assets_favored", "synthesis"]
    missing = [key for key in required_keys if key not in parsed]
    if missing:
        raise AssetAnalysisError(
            f"Model response missing required keys: {missing}. "
            f"Got: {list(parsed.keys())}"
        )

    return parsed
