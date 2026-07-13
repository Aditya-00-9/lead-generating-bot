"""Rough per-run OpenAI cost estimates for ingestion telemetry."""

from __future__ import annotations

from dataclasses import asdict, dataclass

# USD per 1M tokens (approximate; adjust as pricing changes).
_MODEL_RATES: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
}


@dataclass
class CostEstimate:
    web_searches: int = 0
    deep_extract_calls: int = 0
    chat_api_calls: int = 0
    est_input_tokens: int = 0
    est_output_tokens: int = 0
    est_cost_usd: float = 0.0
    models_used: dict[str, int] | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _chars_to_tokens(char_count: int) -> int:
    return max(1, char_count // 4)


def _model_rate(model: str) -> dict[str, float]:
    key = model.lower()
    for name, rates in _MODEL_RATES.items():
        if name in key:
            return rates
    return _MODEL_RATES["gpt-4o-mini"]


def estimate_run_cost(
    *,
    web_searches: int,
    deep_extract_calls: int,
    chat_api_calls: int,
    triage_chars: int = 0,
    enrich_chars: int = 0,
    extract_chars: int = 0,
    responses_model: str,
    chat_model: str,
    extract_model: str,
) -> CostEstimate:
    models_used: dict[str, int] = {}
    if web_searches:
        models_used[responses_model] = models_used.get(responses_model, 0) + web_searches
    extract_calls = deep_extract_calls
    if extract_calls:
        models_used[extract_model] = models_used.get(extract_model, 0) + extract_calls
    if chat_api_calls:
        models_used[chat_model] = models_used.get(chat_model, 0) + chat_api_calls

    # Heuristic token budgets per call type.
    search_input = web_searches * 1200
    search_output = web_searches * 800
    extract_input = extract_calls * max(2000, _chars_to_tokens(extract_chars))
    extract_output = extract_calls * 400
    chat_input = _chars_to_tokens(triage_chars + enrich_chars) + chat_api_calls * 400
    chat_output = chat_api_calls * 350

    est_input = search_input + extract_input + chat_input
    est_output = search_output + extract_output + chat_output

    cost = 0.0
    if web_searches:
        rates = _model_rate(responses_model)
        cost += (search_input / 1_000_000) * rates["input"] + (search_output / 1_000_000) * rates["output"]
    if extract_calls:
        rates = _model_rate(extract_model)
        cost += (extract_input / 1_000_000) * rates["input"] + (extract_output / 1_000_000) * rates["output"]
    if chat_api_calls:
        rates = _model_rate(chat_model)
        cost += (chat_input / 1_000_000) * rates["input"] + (chat_output / 1_000_000) * rates["output"]

    return CostEstimate(
        web_searches=web_searches,
        deep_extract_calls=deep_extract_calls,
        chat_api_calls=chat_api_calls,
        est_input_tokens=est_input,
        est_output_tokens=est_output,
        est_cost_usd=round(cost, 4),
        models_used=models_used,
    )
