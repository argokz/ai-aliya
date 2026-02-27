from __future__ import annotations

import asyncio
from typing import Any, AsyncGenerator
import google.generativeai as genai
from openai import OpenAI

from app.config import Settings
from app.schemas import ChatMessage


class LLMService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._working_gemini_model: str | None = None
        self._openai_client: OpenAI | None = None
        self._genai_configured = False

    def _get_openai_client(self) -> OpenAI:
        if self._openai_client is None:
            self._openai_client = OpenAI(
                api_key=self.settings.openai_api_key,
                base_url=self.settings.openai_base_url,
            )
        return self._openai_client

    def _configure_genai(self):
        if not self._genai_configured:
            genai.configure(api_key=self.settings.gemini_api_key)
            self._genai_configured = True

    async def generate_reply(
        self,
        user_text: str,
        history: list[ChatMessage] | None = None,
    ) -> str:
        messages = [{"role": "system", "content": self.settings.system_prompt}]
        if history:
            messages.extend(m.model_dump() for m in history)
        messages.append({"role": "user", "content": user_text})

        if self.settings.ai_priority == "gpt":
            try:
                # Try OpenAI first
                return await self._generate_openai(messages)
            except Exception as e:
                print(f"GPT failed: {e}. Falling back to Gemini...")
                return await self._generate_gemini_with_failover(messages)

        return await self._generate_gemini_with_failover(messages)

    async def generate_reply_stream(
        self,
        user_text: str,
        history: list[ChatMessage] | None = None,
    ) -> AsyncGenerator[str, None]:
        messages = [{"role": "system", "content": self.settings.system_prompt}]
        if history:
            messages.extend(m.model_dump() for m in history)
        messages.append({"role": "user", "content": user_text})

        if self.settings.ai_priority == "gpt":
            try:
                async for chunk in self._generate_openai_stream(messages):
                    yield chunk
                return
            except Exception as e:
                print(f"GPT stream failed: {e}. Falling back to Gemini...")
                # Fallback to Gemini stream is complex with model iterations, just yield from failover
                async for chunk in self._generate_gemini_stream_with_failover(messages):
                    yield chunk
                return

        async for chunk in self._generate_gemini_stream_with_failover(messages):
            yield chunk

    async def _generate_gemini_stream_with_failover(self, messages: list[dict[str, str]]) -> AsyncGenerator[str, None]:
        # Simple failover for streaming: try first model, if fails, try others
        models = [m.strip() for m in self.settings.gemini_models.split(",") if m.strip()]
        if self._working_gemini_model and self._working_gemini_model in models:
            models.remove(self._working_gemini_model)
            models.insert(0, self._working_gemini_model)

        for model_name in models:
            try:
                # Test connectivity/first chunk? Just try-except the whole generator
                async for chunk in self._generate_gemini_stream(messages, model_name):
                    yield chunk
                self._working_gemini_model = model_name
                return
            except Exception as e:
                print(f"Gemini stream model {model_name} failed: {e}")
                continue

    async def _generate_openai_stream(self, messages: list[dict[str, str]]) -> AsyncGenerator[str, None]:
        if not self.settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required")

        client = self._get_openai_client()
        model = self.settings.openai_model
        kwargs = {
            "model": model,
            "messages": messages,
            "stream": True
        }
        
        is_reasoning = model.startswith("o1") or model.startswith("o3") or "gpt-5" in model
        if not is_reasoning:
            kwargs["temperature"] = self.settings.openai_temperature
            
        response = await asyncio.to_thread(
            client.chat.completions.create,
            **kwargs
        )
        
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def _generate_gemini_stream(self, messages: list[dict[str, str]], model_name: str | None = None) -> AsyncGenerator[str, None]:
        if not self.settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is required")

        self._configure_genai()
        model_name = model_name or self.settings.gemini_model or "gemini-2.0-flash"
        model_name = model_name.replace("models/", "")
        
        google_messages = []
        system_instruction = self.settings.system_prompt
        
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "system":
                system_instruction = content
                continue
            gemini_role = "model" if role == "assistant" else "user"
            google_messages.append({"role": gemini_role, "parts": [content]})

        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=system_instruction
        )
        
        # generate_content with stream=True returns a response object with an iterator
        response = await asyncio.to_thread(
            model.generate_content,
            google_messages,
            generation_config=genai.types.GenerationConfig(temperature=0.7),
            stream=True
        )
        
        for chunk in response:
            if chunk.text:
                yield chunk.text

    async def _generate_gemini_with_failover(self, messages: list[dict[str, str]]) -> str:
        # 1. Try last working model if exists
        if self._working_gemini_model:
            try:
                return await self._generate_gemini(messages, self._working_gemini_model)
            except Exception:
                self._working_gemini_model = None

        # 2. Iterate through available models
        models = [m.strip() for m in self.settings.gemini_models.split(",") if m.strip()]
        for model in models:
            try:
                response = await self._generate_gemini(messages, model)
                self._working_gemini_model = model
                return response
            except Exception as e:
                print(f"Gemini model {model} failed: {e}")
                continue

        raise RuntimeError("All LLM models failed")

    async def _generate_openai(self, messages: list[dict[str, str]]) -> str:
        if not self.settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required")

        client = self._get_openai_client()
        
        # Reasoning models (o1, o3, etc) and gpt-5 do not support temperature < 1.0 or at all
        model = self.settings.openai_model
        kwargs = {
            "model": model,
            "messages": messages,
        }
        
        # Only add temperature if it's not a reasoning model
        is_reasoning = model.startswith("o1") or model.startswith("o3") or "gpt-5" in model
        if not is_reasoning:
            kwargs["temperature"] = self.settings.openai_temperature
            
        # OpenAI SDK call
        response = await asyncio.to_thread(
            client.chat.completions.create,
            **kwargs
        )
        
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("OpenAI returned an empty response")
        return content.strip()

    async def _generate_gemini(self, messages: list[dict[str, str]], model_name: str | None = None) -> str:
        if not self.settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is required")

        self._configure_genai()
        
        model_name = model_name or self.settings.gemini_model or "gemini-2.0-flash"
        model_name = model_name.replace("models/", "")
        
        # Convert messages to Gemini format
        google_messages = []
        system_instruction = self.settings.system_prompt
        
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "system":
                system_instruction = content
                continue
            
            gemini_role = "model" if role == "assistant" else "user"
            google_messages.append({"role": gemini_role, "parts": [content]})

        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=system_instruction
        )
        
        response = await asyncio.to_thread(
            model.generate_content,
            google_messages,
            generation_config=genai.types.GenerationConfig(temperature=0.7)
        )
        
        if not response.text:
            raise RuntimeError("Gemini returned an empty response")
        return response.text.strip()

    async def _generate_ollama(self, messages: list[dict[str, str]]) -> str:
        # Keep Ollama as HTTP for now since it's local and simple
        import httpx
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
        data = response.json()
        return data.get("message", {}).get("content", "").strip()

    async def _generate_openai_compat(self, messages: list[dict[str, str]]) -> str:
        # Use OpenAI client with custom base URL
        client = OpenAI(
            api_key=self.settings.openai_compat_api_key,
            base_url=self.settings.openai_compat_base_url,
        )
        
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=self.settings.openai_compat_model,
            messages=messages,
            temperature=0.7,
        )
        
        return response.choices[0].message.content or ""
