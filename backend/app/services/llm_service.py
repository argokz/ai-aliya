from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from app.config import Settings
from app.schemas import ChatMessage


class LLMService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def generate_reply(
        self,
        user_text: str,
        history: list[ChatMessage] | None = None,
    ) -> str:
        messages = [{"role": "system", "content": self.settings.system_prompt}]
        if history:
            messages.extend(m.model_dump() for m in history)
        messages.append({"role": "user", "content": user_text})

        if self.settings.llm_backend == "openai_compat":
            return await self._generate_openai_compat(messages)
        if self.settings.llm_backend == "openai":
            return await self._generate_openai(messages)
        if self.settings.llm_backend == "gemini":
            return await self._generate_gemini(messages)
        return await self._generate_ollama(messages)

    async def _generate_ollama(self, messages: list[dict[str, str]]) -> str:
        payload = {
            "model": self.settings.ollama_model,
            "messages": messages,
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.settings.ollama_base_url}/api/chat",
                json=payload,
            )
        response.raise_for_status()

        data: dict[str, Any] = response.json()
        content = data.get("message", {}).get("content", "").strip()
        if not content:
            raise RuntimeError("LLM returned an empty response")
        return content

    async def _generate_openai_compat(self, messages: list[dict[str, str]]) -> str:
        payload = {
            "model": self.settings.openai_compat_model,
            "messages": messages,
            "temperature": 0.7,
        }
        headers = {
            "Authorization": f"Bearer {self.settings.openai_compat_api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.settings.openai_compat_base_url}/chat/completions",
                headers=headers,
                json=payload,
            )

        response.raise_for_status()
        return self._extract_openai_style_content(response.json())

    async def _generate_openai(self, messages: list[dict[str, str]]) -> str:
        if not self.settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required when LLM_BACKEND=openai")

        payload = {
            "model": self.settings.openai_model,
            "messages": messages,
            "temperature": 0.7,
        }
        headers = {
            "Authorization": f"Bearer {self.settings.openai_api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.settings.openai_base_url}/chat/completions",
                headers=headers,
                json=payload,
            )

        response.raise_for_status()
        return self._extract_openai_style_content(response.json())

    async def _generate_gemini(self, messages: list[dict[str, str]]) -> str:
        if not self.settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is required when LLM_BACKEND=gemini")

        contents: list[dict[str, Any]] = []
        for message in messages:
            role = message.get("role", "user")
            if role == "system":
                continue
            gemini_role = "model" if role == "assistant" else "user"
            contents.append(
                {
                    "role": gemini_role,
                    "parts": [{"text": message.get("content", "")}],
                }
            )

        model_name = self.settings.gemini_model.replace("models/", "")
        model_name = quote(model_name, safe="-._")

        payload: dict[str, Any] = {
            "system_instruction": {
                "parts": [{"text": self.settings.system_prompt}],
            },
            "contents": contents,
            "generationConfig": {"temperature": 0.7},
        }
        headers = {"Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.settings.gemini_base_url}/models/{model_name}:generateContent",
                params={"key": self.settings.gemini_api_key},
                headers=headers,
                json=payload,
            )

        response.raise_for_status()
        data: dict[str, Any] = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise RuntimeError("Gemini returned no candidates")
        parts = candidates[0].get("content", {}).get("parts", [])
        content = "".join(part.get("text", "") for part in parts).strip()
        if not content:
            raise RuntimeError("Gemini returned an empty response")
        return content

    def _extract_openai_style_content(self, data: dict[str, Any]) -> str:
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("LLM backend returned no choices")
        content = choices[0].get("message", {}).get("content", "").strip()
        if not content:
            raise RuntimeError("LLM returned an empty response")
        return content
