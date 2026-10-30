import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from google.genai.errors import APIError

from app.generation.gemini import (
    GeminiAnswerGenerator,
    GeminiConfigurationError,
    GeminiProviderError,
    GeminiRateLimitError,
    GeminiTimeoutError,
)


def build_generator() -> GeminiAnswerGenerator:
    return GeminiAnswerGenerator(
        api_key="test-key",
        model="gemini-test",
        timeout_seconds=30,
        max_output_tokens=100,
    )


def install_fake_client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    response: object | None = None,
    error: Exception | None = None,
) -> tuple[SimpleNamespace, SimpleNamespace, SimpleNamespace]:
    models = SimpleNamespace(
        generate_content=AsyncMock(
            return_value=response,
            side_effect=error,
        )
    )
    async_client = SimpleNamespace(models=models, aclose=AsyncMock())
    client = SimpleNamespace(aio=async_client)
    def factory(**kwargs: object) -> SimpleNamespace:
        return client

    from google import genai

    monkeypatch.setattr(genai, "Client", factory)
    return models, async_client, client


def test_gemini_generator_uses_sdk_and_parses_structured_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = SimpleNamespace(
        text='{"answer":"Grounded [S1].","insufficient_context":false}'
    )
    models, async_client, _ = install_fake_client(
        monkeypatch, response=response
    )

    answer = asyncio.run(build_generator().generate("bounded prompt"))

    assert answer.answer == "Grounded [S1]."
    assert answer.insufficient_context is False
    models.generate_content.assert_awaited_once()
    assert models.generate_content.await_args.kwargs["model"] == "gemini-test"
    assert models.generate_content.await_args.kwargs["contents"] == (
        "bounded prompt"
    )
    assert async_client.aclose.await_count == 1


@pytest.mark.parametrize(
    "error, expected_error",
    [
        (APIError(429, {"message": "quota"}), GeminiRateLimitError),
        (APIError(403, {"message": "denied"}), GeminiConfigurationError),
        (APIError(504, {"message": "timeout"}), GeminiTimeoutError),
        (RuntimeError("provider unavailable"), GeminiProviderError),
        (TimeoutError("request timeout"), GeminiTimeoutError),
    ],
)
def test_gemini_generator_maps_provider_errors(
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    expected_error: type[Exception],
) -> None:
    install_fake_client(monkeypatch, error=error)

    with pytest.raises(expected_error):
        asyncio.run(build_generator().generate("bounded prompt"))


def test_gemini_generator_does_not_mask_request_error_on_close_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    models, async_client, _ = install_fake_client(
        monkeypatch,
        error=APIError(429, {"message": "quota"}),
    )
    async_client.aclose.side_effect = RuntimeError("close failed")

    with pytest.raises(GeminiRateLimitError):
        asyncio.run(build_generator().generate("bounded prompt"))

    models.generate_content.assert_awaited_once()
