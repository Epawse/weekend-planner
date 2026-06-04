"""Tests for the multi-provider LLM factory.

All network access is avoided: get_provider_order() is driven by monkeypatching
``app.config.settings`` keys, and invoke_with_fallback() is driven by replacing the
factory's ``get_model`` with fakes that either return an async-invokable stub or
raise. No real ChatOpenAI client is ever constructed.
"""

import pytest

from app.config import settings
from app.llm.provider import LLMProviderFactory, ProviderUnavailableError

# --- get_provider_order: filtering + ordering -------------------------------


def _clear_all_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    for attr in ("dashscope_api_key", "gemini_api_key", "deepseek_api_key", "openai_api_key"):
        monkeypatch.setattr(settings, attr, "")


def test_get_provider_order_demo_env_gemini_then_deepseek(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_all_keys(monkeypatch)
    monkeypatch.setattr(settings, "gemini_api_key", "g-key")
    monkeypatch.setattr(settings, "deepseek_api_key", "d-key")

    assert LLMProviderFactory().get_provider_order() == ["gemini", "deepseek"]


def test_get_provider_order_all_four_in_priority_order(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "dashscope_api_key", "q-key")
    monkeypatch.setattr(settings, "gemini_api_key", "g-key")
    monkeypatch.setattr(settings, "deepseek_api_key", "d-key")
    monkeypatch.setattr(settings, "openai_api_key", "o-key")

    assert LLMProviderFactory().get_provider_order() == ["qwen", "gemini", "deepseek", "openai"]


def test_get_provider_order_none_configured_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_all_keys(monkeypatch)
    assert LLMProviderFactory().get_provider_order() == []


# --- get_model: unknown provider --------------------------------------------


def test_get_model_unknown_provider_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Unknown provider"):
        LLMProviderFactory().get_model(provider="unknown")


# --- invoke_with_fallback: success / fallback / exhaustion ------------------


class _FakeModel:
    """Minimal stand-in for a bound chat model with an async invoke."""

    def __init__(self, name: str, response: str) -> None:
        self.name = name
        self._response = response
        self.called = False

    async def ainvoke(self, messages: list) -> str:
        self.called = True
        return self._response


def _patch_get_model(monkeypatch: pytest.MonkeyPatch, factory: LLMProviderFactory, behavior: dict) -> dict:
    """Replace factory.get_model so it never builds a real client.

    ``behavior`` maps provider name -> either a _FakeModel (success) or an
    Exception instance (raised when that provider is selected). Returns a dict
    recording which providers were requested, in order.
    """
    requested: dict = {"order": []}

    def fake_get_model(provider: str | None = None, temperature: float = 0.7, tools: list | None = None):
        requested["order"].append(provider)
        outcome = behavior[provider]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(factory, "get_model", fake_get_model)
    return requested


async def test_invoke_with_fallback_first_provider_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_all_keys(monkeypatch)
    monkeypatch.setattr(settings, "gemini_api_key", "g-key")
    monkeypatch.setattr(settings, "deepseek_api_key", "d-key")

    factory = LLMProviderFactory()
    gemini = _FakeModel("gemini", "gemini-response")
    deepseek = _FakeModel("deepseek", "deepseek-response")
    requested = _patch_get_model(monkeypatch, factory, {"gemini": gemini, "deepseek": deepseek})

    result = await factory.invoke_with_fallback([{"role": "user", "content": "hi"}])

    assert result == "gemini-response"
    assert gemini.called is True
    # Second provider never consulted because the first succeeded.
    assert deepseek.called is False
    assert requested["order"] == ["gemini"]


async def test_invoke_with_fallback_falls_back_on_first_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_all_keys(monkeypatch)
    monkeypatch.setattr(settings, "gemini_api_key", "g-key")
    monkeypatch.setattr(settings, "deepseek_api_key", "d-key")

    factory = LLMProviderFactory()
    deepseek = _FakeModel("deepseek", "deepseek-response")
    requested = _patch_get_model(
        monkeypatch,
        factory,
        {"gemini": RuntimeError("rate limit"), "deepseek": deepseek},
    )

    result = await factory.invoke_with_fallback([{"role": "user", "content": "hi"}])

    assert result == "deepseek-response"
    assert deepseek.called is True
    # Both providers were tried, in priority order.
    assert requested["order"] == ["gemini", "deepseek"]


async def test_invoke_with_fallback_all_fail_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_all_keys(monkeypatch)
    monkeypatch.setattr(settings, "gemini_api_key", "g-key")
    monkeypatch.setattr(settings, "deepseek_api_key", "d-key")

    factory = LLMProviderFactory()
    _patch_get_model(
        monkeypatch,
        factory,
        {"gemini": RuntimeError("boom-1"), "deepseek": RuntimeError("boom-2")},
    )

    with pytest.raises(ProviderUnavailableError, match="All LLM providers failed"):
        await factory.invoke_with_fallback([{"role": "user", "content": "hi"}])


async def test_invoke_with_fallback_no_providers_configured_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_all_keys(monkeypatch)

    factory = LLMProviderFactory()
    with pytest.raises(ProviderUnavailableError, match="No LLM providers configured"):
        await factory.invoke_with_fallback([{"role": "user", "content": "hi"}])
