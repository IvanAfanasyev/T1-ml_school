import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


class LLMClient:
    """
    Обертка над OpenAI-compatible API.

    В проекте используются переменные:

    LLM_API_KEY
    LLM_BASE_URL
    LLM_MODEL
    LLM_TIMEOUT_SECONDS     optional, default 180
    LLM_MAX_RETRIES         optional, default 3

    Также поддерживаются запасные имена OPENAI_*, DEEPSEEK_*, OPENROUTER_*.
    """

    def __init__(self) -> None:
        project_root = Path(__file__).resolve().parents[3]
        env_path = project_root / ".env"

        load_dotenv(env_path)

        self.model = (
            os.getenv("LLM_MODEL")
            or os.getenv("OPENAI_MODEL")
            or os.getenv("DEEPSEEK_MODEL")
            or os.getenv("OPENROUTER_MODEL")
            or "gpt-4o-mini"
        )

        api_key = (
            os.getenv("LLM_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("DEEPSEEK_API_KEY")
            or os.getenv("OPENROUTER_API_KEY")
        )

        base_url = (
            os.getenv("LLM_BASE_URL")
            or os.getenv("OPENAI_BASE_URL")
            or os.getenv("DEEPSEEK_BASE_URL")
            or os.getenv("OPENROUTER_BASE_URL")
        )

        timeout_seconds = float(os.getenv("LLM_TIMEOUT_SECONDS", "180"))
        max_retries = int(os.getenv("LLM_MAX_RETRIES", "3"))

        if not api_key:
            raise ValueError("LLM API key is not set. Set LLM_API_KEY in .env.")

        if not base_url:
            raise ValueError("LLM base URL is not set. Set LLM_BASE_URL in .env.")

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout_seconds,
            max_retries=max_retries,
        )

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int | None = 4000,
    ) -> str:
        request_kwargs = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            "temperature": 0,
        }

        if max_tokens is not None:
            request_kwargs["max_tokens"] = max_tokens

        response = self.client.chat.completions.create(**request_kwargs)

        content = response.choices[0].message.content

        if content is None:
            raise ValueError("LLM returned empty response")

        return content
