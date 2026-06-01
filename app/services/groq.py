"""Groq API client with retry logic and structured output validation."""

from __future__ import annotations

import asyncio
import base64
import json
from typing import Optional, Type

from pydantic import BaseModel

from app.config import settings


class GroqError(Exception):
    """Raised when Groq API fails after retries."""


class GroqClient:
    """Wrapper around Groq API with retry and structured output."""

    def __init__(self):
        self._client = None

    def _get_client(self):
        """Lazy-initialize the Groq client."""
        if self._client is None:
            from groq import Groq

            self._client = Groq(api_key=settings.groq_api_key)
        return self._client

    async def generate_structured(
        self,
        prompt: str,
        response_schema: Optional[Type[BaseModel]] = None,
        image_data: Optional[bytes] = None,
        max_retries: int = 3,
    ) -> dict:
        """Generate structured JSON output from Groq."""
        client = self._get_client()

        for attempt in range(max_retries):
            try:
                content = [{"type": "text", "text": prompt}]
                model_id = settings.groq_text_model

                if image_data:
                    # Groq accepts multimodal input via OpenAI-compatible image_url parts.
                    encoded = base64.b64encode(image_data).decode("utf-8")
                    content.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
                        }
                    )
                    model_id = settings.groq_vision_model

                response = await asyncio.to_thread(
                    client.chat.completions.create,
                    model=model_id,
                    service_tier=settings.groq_service_tier,
                    messages=[{"role": "user", "content": content}],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                    max_completion_tokens=1024,
                )

                text = (response.choices[0].message.content or "").strip()
                if text.startswith("```json"):
                    text = text[7:]
                if text.startswith("```"):
                    text = text[3:]
                if text.endswith("```"):
                    text = text[:-3]

                data = json.loads(text.strip())

                if response_schema:
                    response_schema(**data)

                return data

            except json.JSONDecodeError as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt)
                    continue
                raise GroqError(f"Failed to parse Groq JSON response after {max_retries} attempts: {e}")
            except Exception as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt)
                    continue
                raise GroqError(f"Groq API failed after {max_retries} attempts: {e}")

        raise GroqError("Exhausted all retries")

    async def generate_text(
        self,
        prompt: str,
        max_retries: int = 3,
    ) -> str:
        """Generate free-text response from Groq."""
        client = self._get_client()

        for attempt in range(max_retries):
            try:
                response = await asyncio.to_thread(
                    client.chat.completions.create,
                    model=settings.groq_text_model,
                    service_tier=settings.groq_service_tier,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_completion_tokens=512,
                )
                return (response.choices[0].message.content or "").strip()
            except Exception as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt)
                    continue
                raise GroqError(f"Groq text generation failed: {e}")

        raise GroqError("Exhausted all retries")


# Singleton instance
groq_client = GroqClient()