"""LLM Factory — Create chat models for any supported provider.

Supports Anthropic (Claude) and OpenAI providers via LangChain.
"""

from typing import Any

# Provider → model options mapping
LLM_PROVIDERS = {
    "Anthropic": {
        "models": [
            "claude-sonnet-4-5-20250929",
            "claude-haiku-4-5-20251001",
            "claude-opus-4-6",
        ],
        "default_model": "claude-sonnet-4-5-20250929",
        "key_placeholder": "sk-ant-...",
        "key_label": "Anthropic API Key",
    },
    "OpenAI": {
        "models": [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
        ],
        "default_model": "gpt-4o",
        "key_placeholder": "sk-...",
        "key_label": "OpenAI API Key",
    },
}

DEFAULT_PROVIDER = "Anthropic"


def create_llm(
    provider: str,
    model: str,
    api_key: str,
    temperature: float = 0.0,
    **kwargs: Any,
):
    """Create a LangChain chat model for the given provider.

    Args:
        provider: "Anthropic" or "OpenAI"
        model: Model identifier (e.g. "claude-sonnet-4-5-20250929", "gpt-4o")
        api_key: API key for the provider
        temperature: Sampling temperature
        **kwargs: Additional keyword arguments passed to the model constructor

    Returns:
        A LangChain BaseChatModel instance
    """
    if provider == "Anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model,
            api_key=api_key,
            temperature=temperature,
            **kwargs,
        )
    elif provider == "OpenAI":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            api_key=api_key,
            temperature=temperature,
            **kwargs,
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")
