import asyncio

import httpx
import pytest

from app.api.routes.repositories import (
    get_rag_answer_service,
)
from app.core.config import Settings, get_settings
from app.generation.gemini import (
    GeminiConfigurationError,
    GeminiProviderError,
    GeminiRateLimitError,
    GeminiTimeoutError,
    GeneratedRAGAnswer,
)
from app.schemas.repository import (
    RepositoryAskResponse,
    RepositoryCitation,
    RepositorySearchResponse,
    RepositorySearchResult,
)
from app.retrieval.embeddings import EmbeddingError
from app.services.rag_service import RAGAnswerService
from app.services.repository_index import (
    RepositoryIndexRegistry,
    RepositoryNotIndexedError,
    get_repository_index_registry,
)
from app.main import app

REPOSITORY_URL = "https://github.com/example/project"


class FakeRegistry:
    def __init__(
        self,
        search_response: RepositorySearchResponse | None = None,
        error: Exception | None = None,
    ) -> None:
        self.search_response = search_response or RepositorySearchResponse(
            repository="example/project",
            query="How does login work?",
            results=[
                RepositorySearchResult(
                    chunk_id="real-chunk",
                    repository="example/project",
                    file_path="src/login.py",
                    language="Python",
                    start_line=4,
                    end_line=9,
                    content="def login(): return True\n",
                    semantic_score=0.7,
                    keyword_score=1.2,
                    hybrid_score=0.03,
                )
            ],
        )
        self.error = error
        self.calls: list[tuple[str, str, int]] = []

    def search(
        self,
        repository_url: str,
        query: str,
        top_k: int,
        settings: Settings,
    ) -> RepositorySearchResponse:
        self.calls.append((repository_url, query, top_k))
        if self.error is not None:
            raise self.error
        return self.search_response


class FakeGenerator:
    def __init__(
        self,
        answer: GeneratedRAGAnswer | None = None,
        error: Exception | None = None,
    ) -> None:
        self.answer_value = answer or GeneratedRAGAnswer(
            answer="Login is implemented by `login` [S1].",
            insufficient_context=False,
        )
        self.error = error
        self.prompt: str | None = None

    async def generate(self, prompt: str) -> GeneratedRAGAnswer:
        self.prompt = prompt
        if self.error:
            raise self.error
        return self.answer_value


def service(
    generator: FakeGenerator | None,
) -> RAGAnswerService:
    return RAGAnswerService(
        generator,
        context_chunks=4,
        max_context_characters=5000,
    )


def make_client_overrides(
    registry: FakeRegistry,
    rag_service: RAGAnswerService,
    settings: Settings | None = None,
) -> None:
    async def override_settings() -> Settings:
        return settings or Settings(_env_file=None)

    def override_registry() -> FakeRegistry:
        return registry

    def override_rag_service() -> RAGAnswerService:
        return rag_service

    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_repository_index_registry] = override_registry
    app.dependency_overrides[get_rag_answer_service] = override_rag_service


async def post_ask(
    body: dict[str, object],
) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        return await client.post("/api/repositories/ask", json=body)


def call_ask(
    body: dict[str, object],
    registry: FakeRegistry,
    rag_service: RAGAnswerService,
    settings: Settings | None = None,
) -> httpx.Response:
    make_client_overrides(registry, rag_service, settings)
    try:
        return asyncio.run(post_ask(body))
    finally:
        app.dependency_overrides.pop(get_settings, None)
        app.dependency_overrides.pop(
            get_repository_index_registry, None
        )
        app.dependency_overrides.pop(get_rag_answer_service, None)


def test_ask_endpoint_uses_existing_hybrid_results_and_returns_grounded_citation() -> None:
    registry = FakeRegistry()
    generator = FakeGenerator()
    response = call_ask(
        {
            "repository_url": REPOSITORY_URL,
            "question": "How does login work?",
        },
        registry,
        service(generator),
        Settings(_env_file=None, rag_context_chunks=4),
    )

    assert response.status_code == 200
    payload = response.json()
    assert registry.calls == [
        (REPOSITORY_URL, "How does login work?", 4)
    ]
    assert payload["repository"] == "example/project"
    assert payload["citations"] == [
        {
            "source_id": "S1",
            "chunk_id": "real-chunk",
            "file_path": "src/login.py",
            "start_line": 4,
            "end_line": 9,
            "relevant_content": "def login(): return True\n",
        }
    ]
    assert payload["answer"].endswith("[src/login.py:4-9].")


@pytest.mark.parametrize(
    "question",
    ["", "  \t  "],
)
def test_ask_endpoint_rejects_empty_or_whitespace_question(
    question: str,
) -> None:
    response = call_ask(
        {"repository_url": REPOSITORY_URL, "question": question},
        FakeRegistry(),
        service(FakeGenerator()),
    )

    assert response.status_code == 422


def test_ask_endpoint_reports_unindexed_repository() -> None:
    response = call_ask(
        {
            "repository_url": REPOSITORY_URL,
            "question": "How does login work?",
        },
        FakeRegistry(error=RepositoryNotIndexedError("index it first")),
        service(FakeGenerator()),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "index it first"


def test_ask_endpoint_maps_embedding_error_to_safe_service_unavailable() -> None:
    internal_detail = "synthetic model path and internal failure"
    response = call_ask(
        {
            "repository_url": REPOSITORY_URL,
            "question": "How does login work?",
        },
        FakeRegistry(error=EmbeddingError(internal_detail)),
        service(FakeGenerator()),
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Unable to generate embeddings for repository search"
    )
    assert internal_detail not in response.text


def test_ask_endpoint_returns_503_when_key_is_missing_and_context_exists() -> None:
    settings = Settings(_env_file=None, gemini_api_key=None)
    response = call_ask(
        {
            "repository_url": REPOSITORY_URL,
            "question": "How does login work?",
        },
        FakeRegistry(),
        service(None),
        settings,
    )

    assert response.status_code == 503
    assert "GEMINI_API_KEY" in response.json()["detail"]


@pytest.mark.parametrize(
    "error, status_code",
    [
        (GeminiRateLimitError("quota exceeded"), 429),
        (GeminiTimeoutError("timed out"), 504),
        (GeminiProviderError("provider failed"), 502),
        (GeminiConfigurationError("invalid key"), 503),
    ],
)
def test_ask_endpoint_maps_gemini_errors_to_http_status(
    error: Exception,
    status_code: int,
) -> None:
    response = call_ask(
        {
            "repository_url": REPOSITORY_URL,
            "question": "How does login work?",
        },
        FakeRegistry(),
        service(FakeGenerator(error=error)),
    )

    assert response.status_code == status_code
    assert "Traceback" not in response.text


def test_empty_retrieval_does_not_require_api_key_or_call_generator() -> None:
    registry = FakeRegistry(
        search_response=RepositorySearchResponse(
            repository="example/project",
            query="Question?",
            results=[],
        )
    )
    generator = FakeGenerator()
    response = call_ask(
        {
            "repository_url": REPOSITORY_URL,
            "question": "Question?",
        },
        registry,
        service(generator),
        Settings(_env_file=None, gemini_api_key=None),
    )

    assert response.status_code == 200
    assert response.json()["insufficient_context"] is True
    assert response.json()["citations"] == []
    assert generator.prompt is None


def test_settings_load_gemini_environment_variables(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "not-a-real-key")
    monkeypatch.setenv("GEMINI_MODEL", "test-model")

    settings = Settings(_env_file=None)

    assert settings.gemini_api_key is not None
    assert settings.gemini_api_key.get_secret_value() == "not-a-real-key"
    assert settings.gemini_model == "test-model"
