import asyncio

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class GeminiError(RuntimeError):
    pass


class GeminiConfigurationError(GeminiError):
    pass


class GeminiRateLimitError(GeminiError):
    pass


class GeminiTimeoutError(GeminiError):
    pass


class GeminiProviderError(GeminiError):
    pass


class GeneratedRAGAnswer(BaseModel):
    answer: str = Field(min_length=1, max_length=12000)
    insufficient_context: bool

    model_config = ConfigDict(extra="forbid")


def _translate_provider_error(error: Exception) -> GeminiError:
    if isinstance(
        error,
        (asyncio.TimeoutError, TimeoutError, httpx.TimeoutException),
    ):
        return GeminiTimeoutError("Gemini request timed out")
    try:
        from google.genai.errors import APIError
    except ImportError:
        return GeminiProviderError("Gemini could not complete the request")
    if isinstance(error, APIError):
        status_code = getattr(error, "code", None)
        if status_code == 429:
            return GeminiRateLimitError(
                "Gemini request quota or rate limit was exceeded"
            )
        if status_code in (401, 403):
            return GeminiConfigurationError(
                "Gemini rejected the configured API key or project"
            )
        if status_code in (408, 504):
            return GeminiTimeoutError("Gemini request timed out")
    return GeminiProviderError("Gemini could not complete the request")


class GeminiAnswerGenerator:
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_output_tokens: int,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._max_output_tokens = max_output_tokens

    async def generate(self, prompt: str) -> GeneratedRAGAnswer:
        try:
            from google import genai
            from google.genai import types
        except ImportError as error:
            raise GeminiConfigurationError(
                "The Google Gen AI SDK is not installed"
            ) from error

        client = None
        response = None
        request_error: GeminiError | None = None
        request_cause: Exception | None = None
        try:
            client = genai.Client(
                api_key=self._api_key,
                http_options=types.HttpOptions(
                    timeout=int(self._timeout_seconds * 1000)
                ),
            )
            response = await client.aio.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                    max_output_tokens=self._max_output_tokens,
                ),
            )
        except Exception as error:
            request_error = _translate_provider_error(error)
            request_cause = error
        finally:
            if client is not None:
                try:
                    await client.aio.aclose()
                except Exception as error:
                    if request_error is None:
                        request_error = GeminiProviderError(
                            "Gemini client could not be closed cleanly"
                        )
                        request_cause = error

        if request_error is not None:
            raise request_error from request_cause

        response_text = getattr(response, "text", None)
        if not isinstance(response_text, str) or not response_text.strip():
            raise GeminiProviderError("Gemini returned an empty response")
        try:
            return GeneratedRAGAnswer.model_validate_json(response_text)
        except (ValidationError, ValueError) as error:
            raise GeminiProviderError(
                "Gemini returned an invalid answer format"
            ) from error
