from __future__ import annotations

import json
import re
from typing import Any

import pandas as pd
import requests

from .briefing import synthesis_prompt
from .core import SENTIMENTS, THEMES, validate_classifications


def _classification_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "classifications": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "visit_id": {"type": "string"},
                        "themes": {
                            "type": "array",
                            "items": {"type": "string", "enum": list(THEMES)},
                            "minItems": 1,
                        },
                        "sentiment": {"type": "string", "enum": list(SENTIMENTS)},
                        "rationale": {"type": "string"},
                    },
                    "required": ["visit_id", "themes", "sentiment", "rationale"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["classifications"],
        "additionalProperties": False,
    }


def _classification_prompt(visits: pd.DataFrame) -> tuple[str, str]:
    records = [
        {"visit_id": row.visit_id, "branch": row.branch, "comment": row.comment}
        for row in visits.itertuples()
    ]
    system = (
        "You classify cafe feedback at the visit level. Apply multiple themes when warranted. "
        "Use mixed when praise and a problem coexist. Use the unclear theme instead of inventing detail. "
        "Do not merge or omit visits."
    )
    user = (
        "Classify each visit exactly once using only the allowed taxonomy. Return JSON only.\n\n"
        f"Allowed themes: {json.dumps(THEMES)}\n"
        f"Visits: {json.dumps(records, ensure_ascii=False, indent=2)}"
    )
    return system, user


def _extract_json(text: str) -> dict:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1)
    else:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
    return json.loads(text)


class LLMClient:
    def __init__(self, provider: str, api_key: str, model: str, timeout: int = 90):
        if not api_key.strip():
            raise ValueError("An API key is required for the selected provider.")
        if not model.strip():
            raise ValueError("A model string is required.")
        self.provider = provider
        self.api_key = api_key.strip()
        self.model = model.strip()
        self.timeout = timeout

    def _openrouter(self, system: str, user: str, structured: bool) -> str:
        from openai import OpenAI

        client = OpenAI(
            api_key=self.api_key,
            base_url="https://openrouter.ai/api/v1",
            timeout=self.timeout,
            default_headers={"X-Title": "Juniper Cafe Operations Briefing"},
        )
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
        }
        if structured:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "visit_classifications",
                    "strict": True,
                    "schema": _classification_schema(),
                },
            }
        response = client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("The model returned an empty response.")
        return content

    def _anthropic(self, system: str, user: str) -> str:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self.model,
                "max_tokens": 4096,
                "temperature": 0,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
            timeout=self.timeout,
        )
        if not response.ok:
            try:
                detail = response.json().get("error", {}).get("message", response.text)
            except Exception:
                detail = response.text
            raise RuntimeError(f"Anthropic API error {response.status_code}: {detail[:500]}")
        payload = response.json()
        text_parts = [block.get("text", "") for block in payload.get("content", []) if block.get("type") == "text"]
        text = "\n".join(text_parts).strip()
        if not text:
            raise RuntimeError("The model returned an empty response.")
        return text

    def complete(self, system: str, user: str, structured: bool = False) -> str:
        if self.provider == "OpenRouter":
            return self._openrouter(system, user, structured)
        if self.provider == "Anthropic":
            return self._anthropic(system, user)
        raise ValueError(f"Unsupported provider: {self.provider}")

    def classify(self, visits: pd.DataFrame) -> pd.DataFrame:
        system, user = _classification_prompt(visits)
        if self.provider == "Anthropic":
            user += "\nReturn one JSON object matching this schema:\n" + json.dumps(_classification_schema())
        raw = self.complete(system, user, structured=True)
        payload = _extract_json(raw)
        result = pd.DataFrame(payload.get("classifications", []))
        return validate_classifications(visits, result)

    def synthesize(self, aggregates: dict, language: str) -> str:
        system, user = synthesis_prompt(aggregates, language)
        return self.complete(system, user, structured=False).strip()

