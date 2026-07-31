from __future__ import annotations

import json

import httpx

from app.settings import get_settings

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-5"


class NarrativeGenerationError(Exception):
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

    belief_and_regime_keys = [b["belief_key"] for b in beliefs] + [
        r["regime_key"] for r in regimes
    ]

    return f"""You are a macro research analyst writing for a knowledgeable investor \
who already understands markets but wants a clear, honest read on current conditions.

CURRENT MACRO DATA:
{macro_lines}

CURRENT BELIEFS (model-derived probabilities, 0-100%):
{belief_lines}

CURRENT REGIMES (model-derived probabilities, 0-100%):
{regime_lines}

Return ONLY valid JSON (no markdown fences, no prose outside the JSON) matching \
exactly this shape:
{{
  "narrative": "2-4 paragraphs synthesizing what these conditions mean TOGETHER \
-- an actual interpretation of how they connect and what it implies, not a \
restatement of the list above. Be direct about uncertainty; don't claim more \
confidence than the data supports.",
  "glossary": {{
    "<key>": "one plain-English sentence defining what this belief or regime \
represents and how to read a high vs. low value"
  }}
}}

The glossary must include exactly one entry for each of these keys, no more, \
no fewer: {", ".join(belief_and_regime_keys) or "none"}
"""


def generate_narrative(
    macro: list[dict],
    beliefs: list[dict],
    regimes: list[dict],
) -> dict:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise NarrativeGenerationError(
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
            },
            timeout=httpx.Timeout(
                connect=15.0, read=120.0, write=30.0, pool=15.0
            ),
        )
    except httpx.HTTPError as exc:
        raise NarrativeGenerationError(
            f"Request to Anthropic API failed: {exc}"
        ) from exc

    if response.status_code != 200:
        raise NarrativeGenerationError(
            f"Anthropic API returned {response.status_code}: "
            f"{response.text[:500]}"
        )

    data = response.json()

    if data.get("stop_reason") == "max_tokens":
        raise NarrativeGenerationError(
            "Response was cut off at the max_tokens limit before finishing "
            "the JSON — the model needed more room than 4096 tokens allowed. "
            "Raise max_tokens further or shorten the requested glossary."
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
        raise NarrativeGenerationError(
            f"Could not parse model response as JSON: {exc}. "
            f"Raw response started with: {raw_text[:200]}"
        ) from exc

    if "narrative" not in parsed or "glossary" not in parsed:
        raise NarrativeGenerationError(
            f"Model response missing required keys. Got: {list(parsed.keys())}"
        )

    return parsed
