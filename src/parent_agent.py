import os
import json
import requests


EXTRACTION_PROMPT = """Analyze these life decisions and extract transferable wisdom patterns.
PRIVACY — no names, companies, places, amounts, or identifying details.
Decisions: {decisions}
Return ONLY a JSON array, no other text. Each item:
{{"id":"wp_{{n:03d}}","principle":"2-6 word title","insight":"1-2 sentence wisdom","category":"career|relationships|finance|values|risk","strength":0.0}}"""

CONFLICT_PROMPT = """Generate exactly 5 wisdom patterns for a parent whose core values are stability, family presence, and pragmatism — values that create genuine tension with mission-driven idealism.
PRIVACY — no names, companies, or identifying details.
Return ONLY a JSON array, no other text. Each item:
{{"id":"cp_{{n:03d}}","principle":"2-6 word title","insight":"1-2 sentence wisdom","category":"career|relationships|finance|values|risk","strength":0.0}}"""

GITHUB_PROMPT = """Analyze these git commit messages as evidence of a developer's engineering values and decision-making patterns.
PRIVACY — no usernames, repo names, or project identifiers.
Commits: {commits}
Return ONLY a JSON array, no other text. Each item:
{{"id":"gp_{{n:03d}}","principle":"2-6 word title","insight":"1-2 sentence wisdom","category":"career|values|relationships|finance|risk","strength":0.0}}"""


def _groq(prompt: str) -> str:
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not configured")
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1024,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _parse(text: str) -> list:
    text = text.strip()
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            for v in result.values():
                if isinstance(v, list):
                    return v
    except json.JSONDecodeError:
        pass
    import re
    m = re.search(r'\[[\s\S]*\]', text)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return []


class ParentAgent:
    def extract_wisdom(self, decisions: list) -> list:
        prompt = EXTRACTION_PROMPT.format(decisions=json.dumps(decisions))
        text = _groq(prompt)
        patterns = _parse(text)
        for i, p in enumerate(patterns):
            if "id" not in p:
                p["id"] = f"wp_{i+1:03d}"
        return patterns

    def conflict_patterns(self) -> list:
        text = _groq(CONFLICT_PROMPT)
        patterns = _parse(text)
        for i, p in enumerate(patterns):
            if "id" not in p:
                p["id"] = f"cp_{i+1:03d}"
        return patterns

    def github_patterns(self, commits: list) -> list:
        prompt = GITHUB_PROMPT.format(commits=json.dumps(commits[:30]))
        text = _groq(prompt)
        patterns = _parse(text)
        for i, p in enumerate(patterns):
            if "id" not in p:
                p["id"] = f"gp_{i+1:03d}"
        return patterns
