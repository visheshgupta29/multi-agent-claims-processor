"""Gemini API client with retry logic and structured output validation."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Optional, Type

from pydantic import BaseModel

from app.config import settings


class GeminiError(Exception):
    """Raised when Gemini API fails after retries."""
    pass


class GeminiClient:
    """Wrapper around Google Gemini API with retry and structured output."""

    def __init__(self):
        self._model = None
        self._vision_model = None

    def _get_client(self):
        """Lazy-initialize the Gemini client."""
        if self._model is None:
            import google.generativeai as genai
            genai.configure(api_key=settings.gemini_api_key)
            self._model = genai.GenerativeModel(settings.gemini_flash_model)
            self._vision_model = genai.GenerativeModel(settings.gemini_flash_model)
        return self._model

    async def generate_structured(
        self,
        prompt: str,
        response_schema: Optional[Type[BaseModel]] = None,
        image_data: Optional[bytes] = None,
        max_retries: int = 3,
    ) -> dict:
        """Generate structured JSON output from Gemini.

        Args:
            prompt: The text prompt
            response_schema: Optional Pydantic model for validation
            image_data: Optional image bytes for vision tasks
            max_retries: Number of retry attempts

        Returns:
            Parsed JSON dict from Gemini response

        Raises:
            GeminiError: If all retries fail
        """
        model = self._get_client()

        for attempt in range(max_retries):
            try:
                # Build content parts
                parts = []
                if image_data:
                    import google.generativeai as genai
                    parts.append({"mime_type": "image/jpeg", "data": image_data})
                parts.append(prompt)

                # Generate with JSON mode
                response = await asyncio.to_thread(
                    model.generate_content,
                    parts,
                    generation_config={
                        "response_mime_type": "application/json",
                        "temperature": 0.1,
                    },
                )

                # Parse response
                text = response.text.strip()
                # Sometimes Gemini wraps in markdown code blocks
                if text.startswith("```json"):
                    text = text[7:]
                if text.startswith("```"):
                    text = text[3:]
                if text.endswith("```"):
                    text = text[:-3]

                data = json.loads(text.strip())

                # Validate against schema if provided
                if response_schema:
                    response_schema(**data)  # Will raise ValidationError if invalid

                return data

            except json.JSONDecodeError as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise GeminiError(f"Failed to parse Gemini JSON response after {max_retries} attempts: {e}")
            except Exception as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise GeminiError(f"Gemini API failed after {max_retries} attempts: {e}")

        raise GeminiError("Exhausted all retries")

    async def generate_text(
        self,
        prompt: str,
        max_retries: int = 3,
    ) -> str:
        """Generate free-text response from Gemini."""
        model = self._get_client()

        for attempt in range(max_retries):
            try:
                response = await asyncio.to_thread(
                    model.generate_content,
                    prompt,
                    generation_config={"temperature": 0.3},
                )
                return response.text.strip()
            except Exception as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise GeminiError(f"Gemini text generation failed: {e}")

        raise GeminiError("Exhausted all retries")


# Singleton instance
gemini_client = GeminiClient()
