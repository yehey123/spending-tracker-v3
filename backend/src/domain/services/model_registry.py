"""Hardcoded model registry — seed floor for model_cache table.
Live API data overwrites entries with source='api' on sync.
"""

SEED: dict[str, list[tuple[str, str, int | None]]] = {
    "gemini": [
        ("gemini-2.5-flash", "Gemini 2.5 Flash", 65536),
        ("gemini-2.5-pro",   "Gemini 2.5 Pro",   65536),
        ("gemini-2.0-flash", "Gemini 2.0 Flash",   8192),
    ],
    "vertex": [
        ("gemini-2.5-flash", "Gemini 2.5 Flash", 65536),
        ("gemini-2.5-pro",   "Gemini 2.5 Pro",   65536),
        ("gemini-2.0-flash", "Gemini 2.0 Flash",   8192),
    ],
    "openai": [
        ("gpt-4o",       "GPT-4o",       16384),
        ("gpt-4o-mini",  "GPT-4o Mini",  16384),
        ("gpt-4.1",      "GPT-4.1",      32768),
        ("gpt-4.1-mini", "GPT-4.1 Mini", 32768),
        ("o3",           "o3",          100000),
        ("o4-mini",      "o4-mini",     100000),
    ],
    "claude": [
        ("claude-opus-4-8",           "Claude Opus 4.8",   32000),
        ("claude-sonnet-4-6",         "Claude Sonnet 4.6", 64000),
        ("claude-haiku-4-5-20251001", "Claude Haiku 4.5",  64000),
    ],
}

LIMITS: dict[str, int] = {
    model_id: tokens
    for entries in SEED.values()
    for model_id, _, tokens in entries
    if tokens is not None
}


def get_limit(model_id: str) -> int | None:
    """Return known max_output_tokens, stripping google/ prefix."""
    return LIMITS.get(model_id.removeprefix("google/"))
