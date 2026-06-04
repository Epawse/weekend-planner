# LLM Provider Selection & Fallback

> How `app/llm/provider.py` chooses which model answers, and the env wiring behind it.
> Executable contract — read before touching provider order, adding a provider, or wiring an LLM env key.

---

## 1. Scope / Trigger

Apply this spec when you:
- Change which LLM is "primary" / reorder the fallback chain
- Add or remove a provider
- Wire a new `*_API_KEY` env var for an LLM
- Debug "why is model X (not Y) answering?"

---

## 2. Signatures (`app/llm/provider.py`)

```python
class LLMProviderFactory:
    def get_provider_order(self) -> list[str]:
        """Keyed providers in priority order. Order: qwen → gemini → deepseek → openai.
        A provider is included ONLY if its API key is configured."""

    def get_model(self, provider: str | None = None, temperature: float = 0.7,
                  tools: list | None = None) -> BaseChatModel:
        """target = provider or settings.default_llm_provider. Raises ValueError on unknown provider."""

    async def invoke_with_fallback(self, messages: list, temperature: float = 0.7,
                                   tools: list | None = None):
        """Try get_provider_order() in sequence; return first success.
        Raises ProviderUnavailableError if none configured or all fail."""

llm_factory = LLMProviderFactory()  # module singleton
```

The orchestrator's **sole** LLM entry point is `llm_factory.invoke_with_fallback(...)` (`app/agents/orchestrator.py`). Nothing calls `get_model(provider=None)`.

---

## 3. Contracts (env wiring)

| Env key | `settings` field | Provider id | Model | In `get_provider_order()`? |
|---------|------------------|-------------|-------|----------------------------|
| `DASHSCOPE_API_KEY` | `dashscope_api_key` | `qwen` | `qwen-plus` | ✅ 1st |
| `GEMINI_API_KEY` | `gemini_api_key` | `gemini` | `gemini-3.5-flash` | ✅ 2nd |
| `DEEPSEEK_API_KEY` | `deepseek_api_key` | `deepseek` | `deepseek-v4-flash` | ✅ 3rd |
| `OPENAI_API_KEY` | `openai_api_key` | `openai` | `gpt-4o-mini` | ✅ 4th |
| `ANTHROPIC_API_KEY` | `anthropic_api_key` | — | — | ❌ **NOT wired** (no `factory_map`/order branch) |
| `DEFAULT_LLM_PROVIDER` | `default_llm_provider` | — | — | ❌ **does not affect fallback path** |

Canonical demo setup: **Gemini primary, DeepSeek fallback** (demo env has only `GEMINI_API_KEY` + `DEEPSEEK_API_KEY`, so order resolves to `["gemini", "deepseek"]`).

---

## 4. Validation & Error Matrix

| Condition | Behavior |
|-----------|----------|
| `get_model("unknown")` | raises `ValueError(f"Unknown provider: {target}")` |
| `invoke_with_fallback` + no keyed providers | raises `ProviderUnavailableError("No LLM providers configured")` |
| First provider raises, later one succeeds | logs `llm_provider_failed`, returns later provider's response |
| All keyed providers raise | raises `ProviderUnavailableError("All LLM providers failed. Last error: ...")` |

---

## 5. Good / Base / Bad Cases

- **Good**: only `GEMINI`+`DEEPSEEK` keys set → `get_provider_order() == ["gemini", "deepseek"]`; Gemini answers, DeepSeek covers Gemini failures.
- **Base**: all four keys set → `["qwen", "gemini", "deepseek", "openai"]`.
- **Bad**: no keys set → `get_provider_order() == []` → `invoke_with_fallback` raises `ProviderUnavailableError`.

---

## 6. Tests Required (assertion points)

`backend/tests/test_llm/test_provider.py` (monkeypatch `app.config.settings` keys + patch `get_model`; never construct a real client / hit network):
- `get_provider_order`: only gemini+deepseek → `["gemini","deepseek"]`; all four → full order; none → `[]`.
- `get_model("unknown")` → `ValueError`.
- `invoke_with_fallback`: first-success short-circuits (2nd never called); first-raises-then-success returns 2nd; all-raise → `ProviderUnavailableError`; none-configured → `ProviderUnavailableError`.

---

## 7. Wrong vs Correct

> **Gotcha**: `DEFAULT_LLM_PROVIDER` is effectively cosmetic. It is read only by `get_model(provider=None)` (which has no caller) and a startup log — **never** by `invoke_with_fallback()`. Setting it in `.env` has **zero effect** on which model answers. (A real `.env` once had `DEFAULT_LLM_PROVIDER=deepseek` while Gemini was actually answering.)

### Wrong — trying to change the primary via env default
```bash
# .env — has NO effect on the fallback path
DEFAULT_LLM_PROVIDER=deepseek
```

### Correct — change the order (and ensure the provider has a key)
```python
# app/llm/provider.py — reorder get_provider_order()
def get_provider_order(self) -> list[str]:
    providers = []
    if settings.deepseek_api_key:   # move deepseek first to make it primary
        providers.append("deepseek")
    if settings.gemini_api_key:
        providers.append("gemini")
    ...
```

To add a provider (e.g. Anthropic), you must wire **all three**: a `_create_<name>` factory, an entry in `get_model`'s `factory_map`, and an `if settings.<key>: providers.append(...)` line in `get_provider_order()`. Adding only the env key + `settings` field (as `anthropic_api_key` currently is) does nothing.
