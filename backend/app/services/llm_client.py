import json
import logging
from typing import AsyncGenerator, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Клиент для работы с OpenAI-совместимым API llama.cpp."""

    def __init__(self) -> None:
        self.base_url: str = settings.llm_base_url
        self.api_key: str = settings.llm_api_key
        self.model: str = settings.llm_model
        self.default_max_tokens: int = settings.llm_max_tokens
        self.temperature: float = settings.llm_temperature
        self.timeout: int = settings.llm_timeout

    async def generate(
        self,
        prompt: str,
        system: str = "",
        max_tokens: Optional[int] = None,
    ) -> str:
        """Полный (не стриминговый) запрос к LLM. Возвращает текст ответа."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": prompt},
                        ],
                        "max_tokens": max_tokens or self.default_max_tokens,
                        "temperature": self.temperature,
                        "stream": False,
                    },
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                response.raise_for_status()
                data: dict = response.json()
                return str(data["choices"][0]["message"]["content"])
        except httpx.TimeoutException:
            logger.error("Таймаут при запросе к LLM", exc_info=True)
        except httpx.HTTPStatusError as e:
            logger.error("HTTP ошибка при запросе к LLM: %s", e)
        except Exception as e:
            logger.error("Ошибка при запросе к LLM: %s", e)
        return "AI-сервис временно недоступен."

    async def stream_generate(
        self,
        prompt: str,
        system: str = "",
    ) -> AsyncGenerator[str, None]:
        """Потоковый запрос к LLM. Читает SSE-события от llama.cpp."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": prompt},
                        ],
                        "max_tokens": self.default_max_tokens,
                        "temperature": self.temperature,
                        "stream": True,
                    },
                    headers={"Authorization": f"Bearer {self.api_key}"},
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                data = json.loads(data_str)
                                delta = (
                                    data.get("choices", [{}])[0]
                                    .get("delta", {})
                                    .get("content", "")
                                )
                                if delta:
                                    yield delta
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            logger.error("Ошибка при стриминге LLM: %s", e)
