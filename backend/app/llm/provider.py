"""Multi-provider LLM factory with priority-based fallback."""

import structlog
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.config import settings

logger = structlog.get_logger()


class ProviderUnavailableError(Exception):
    """All LLM providers failed."""


class LLMProviderFactory:
    """Multi-provider LLM with priority-based fallback.

    Priority order: Qwen (DashScope) -> DeepSeek -> OpenAI
    All use OpenAI-compatible interface for consistency.
    """

    def _create_qwen(self, temperature: float = 0.7) -> BaseChatModel:
        return ChatOpenAI(
            model="qwen-plus",
            api_key=settings.dashscope_api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            temperature=temperature,
        )

    def _create_deepseek(self, temperature: float = 0.7) -> BaseChatModel:
        return ChatOpenAI(
            model="deepseek-chat",
            api_key=settings.deepseek_api_key,
            base_url="https://api.deepseek.com/v1",
            temperature=temperature,
        )

    def _create_openai(self, temperature: float = 0.7) -> BaseChatModel:
        return ChatOpenAI(
            model="gpt-4o-mini",
            api_key=settings.openai_api_key,
            temperature=temperature,
        )

    def get_provider_order(self) -> list[str]:
        """Return providers in priority order, only those with configured keys."""
        providers = []
        if settings.dashscope_api_key:
            providers.append("qwen")
        if settings.deepseek_api_key:
            providers.append("deepseek")
        if settings.openai_api_key:
            providers.append("openai")
        return providers

    def get_model(
        self,
        provider: str | None = None,
        temperature: float = 0.7,
        tools: list | None = None,
    ) -> BaseChatModel:
        """Get a model instance, optionally with tools bound.

        Args:
            provider: Specific provider name, or None for default.
            temperature: Sampling temperature.
            tools: Optional list of tools to bind.

        Returns:
            A configured chat model instance.
        """
        target = provider or settings.default_llm_provider

        factory_map = {
            "qwen": self._create_qwen,
            "deepseek": self._create_deepseek,
            "openai": self._create_openai,
        }

        if target not in factory_map:
            raise ValueError(f"Unknown provider: {target}")

        model = factory_map[target](temperature=temperature)
        if tools:
            model = model.bind_tools(tools)
        return model

    async def invoke_with_fallback(
        self,
        messages: list,
        temperature: float = 0.7,
        tools: list | None = None,
    ):
        """Try providers in priority order, switch on failure.

        Args:
            messages: List of messages to send.
            temperature: Sampling temperature.
            tools: Optional tools to bind.

        Returns:
            LLM response from the first successful provider.

        Raises:
            ProviderUnavailableError: If all providers fail.
        """
        providers = self.get_provider_order()
        if not providers:
            raise ProviderUnavailableError("No LLM providers configured")

        last_error: Exception | None = None
        for name in providers:
            try:
                model = self.get_model(provider=name, temperature=temperature, tools=tools)
                response = await model.ainvoke(messages)
                logger.info("llm_invoke_success", provider=name)
                return response
            except Exception as e:
                logger.warning("llm_provider_failed", provider=name, error=str(e))
                last_error = e
                continue

        raise ProviderUnavailableError(f"All LLM providers failed. Last error: {last_error}")


# Singleton instance
llm_factory = LLMProviderFactory()
