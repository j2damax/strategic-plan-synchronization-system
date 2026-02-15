"""In-memory LLM call logger for debugging.

Stores prompts, responses, parse results, token counts, latency,
and cost data from all LLM calls so they can be inspected in the
dashboard debug page.
"""

from datetime import datetime
from typing import Any

_llm_logs: list[dict[str, Any]] = []

# Estimated cost per 1K tokens (USD) by model family
_MODEL_COST_PER_1K: dict[str, dict[str, float]] = {
    "claude-opus-4": {"input": 0.015, "output": 0.075},
    "claude-sonnet-4": {"input": 0.003, "output": 0.015},
    "claude-haiku-4": {"input": 0.0008, "output": 0.004},
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-4": {"input": 0.03, "output": 0.06},
}


def log_llm_call(
    *,
    caller: str,
    prompt: str,
    response: str | None = None,
    parsed_result: Any = None,
    error: str | None = None,
    layer: int | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    latency_ms: int | None = None,
    model: str | None = None,
    cached: bool = False,
) -> None:
    """Record an LLM call.

    Args:
        caller: Identifier like "ClassName.method_name"
        prompt: The full prompt sent to the LLM
        response: Raw response text from the LLM
        parsed_result: Parsed/structured result (if any)
        error: Error message (if parsing failed)
        layer: Pipeline layer number (1-4)
        input_tokens: Number of input/prompt tokens
        output_tokens: Number of output/completion tokens
        latency_ms: Call latency in milliseconds
        model: Model identifier (e.g. "gpt-4o")
        cached: Whether this response was served from cache
    """
    _llm_logs.append(
        {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "caller": caller,
            "prompt": prompt,
            "response": response,
            "parsed_result": parsed_result,
            "error": error,
            "layer": layer,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": latency_ms,
            "model": model,
            "cached": cached,
        }
    )


def get_llm_logs() -> list[dict[str, Any]]:
    """Return all recorded LLM calls (newest first)."""
    return list(reversed(_llm_logs))


def get_llm_stats() -> dict[str, Any]:
    """Aggregate statistics across all logged LLM calls.

    Returns:
        Dictionary with:
        - total_calls: Total number of LLM calls
        - cached_calls: Number of cache hits
        - total_input_tokens: Sum of input tokens (where tracked)
        - total_output_tokens: Sum of output tokens (where tracked)
        - total_tokens: Sum of all tokens
        - estimated_cost_usd: Estimated total cost based on model pricing
        - total_latency_ms: Sum of latency across all calls
        - avg_latency_ms: Average latency per non-cached call
        - per_layer: Dict keyed by layer number with per-layer breakdowns
        - per_model: Dict keyed by model name with per-model breakdowns
    """
    total_calls = len(_llm_logs)
    cached_calls = sum(1 for log in _llm_logs if log.get("cached"))
    total_input = sum(log.get("input_tokens") or 0 for log in _llm_logs)
    total_output = sum(log.get("output_tokens") or 0 for log in _llm_logs)
    total_latency = sum(log.get("latency_ms") or 0 for log in _llm_logs)

    non_cached_with_latency = [
        log for log in _llm_logs
        if not log.get("cached") and log.get("latency_ms") is not None
    ]
    non_cached_latency_sum = sum(
        log.get("latency_ms") or 0 for log in non_cached_with_latency
    )
    avg_latency = (
        non_cached_latency_sum / len(non_cached_with_latency)
        if non_cached_with_latency
        else 0.0
    )

    # Estimate cost
    estimated_cost = 0.0
    for log in _llm_logs:
        model = log.get("model") or ""
        # Match model to cost table (prefix match)
        cost_entry = None
        for model_key in _MODEL_COST_PER_1K:
            if model.startswith(model_key):
                cost_entry = _MODEL_COST_PER_1K[model_key]
                break
        if cost_entry:
            inp = (log.get("input_tokens") or 0) / 1000.0
            out = (log.get("output_tokens") or 0) / 1000.0
            estimated_cost += inp * cost_entry["input"] + out * cost_entry["output"]

    # Per-layer breakdown
    per_layer: dict[int, dict[str, Any]] = {}
    for log in _llm_logs:
        layer = log.get("layer")
        if layer is None:
            continue
        if layer not in per_layer:
            per_layer[layer] = {
                "calls": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "latency_ms": 0,
                "errors": 0,
            }
        per_layer[layer]["calls"] += 1
        per_layer[layer]["input_tokens"] += log.get("input_tokens") or 0
        per_layer[layer]["output_tokens"] += log.get("output_tokens") or 0
        per_layer[layer]["latency_ms"] += log.get("latency_ms") or 0
        if log.get("error"):
            per_layer[layer]["errors"] += 1

    # Per-model breakdown
    per_model: dict[str, dict[str, Any]] = {}
    for log in _llm_logs:
        model = log.get("model")
        if model is None:
            continue
        if model not in per_model:
            per_model[model] = {
                "calls": 0,
                "input_tokens": 0,
                "output_tokens": 0,
            }
        per_model[model]["calls"] += 1
        per_model[model]["input_tokens"] += log.get("input_tokens") or 0
        per_model[model]["output_tokens"] += log.get("output_tokens") or 0

    return {
        "total_calls": total_calls,
        "cached_calls": cached_calls,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_tokens": total_input + total_output,
        "estimated_cost_usd": round(estimated_cost, 6),
        "total_latency_ms": total_latency,
        "avg_latency_ms": round(avg_latency, 1),
        "per_layer": per_layer,
        "per_model": per_model,
    }


def clear_llm_logs() -> None:
    """Clear all recorded LLM calls."""
    _llm_logs.clear()
