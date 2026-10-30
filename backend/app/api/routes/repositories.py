from collections.abc import AsyncIterator

import httpx
from fastapi import APIRouter, Depends, HTTPException
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings, get_settings
from app.generation.gemini import (
    GeminiAnswerGenerator,
    GeminiConfigurationError,
    GeminiError,
    GeminiProviderError,
    GeminiRateLimitError,
    GeminiTimeoutError,
)
from app.ingestion.github import (
    GitHubRepositoryIndexer,
    RepositoryIngestionError,
)
from app.retrieval.embeddings import EmbeddingError
from app.services.repository_index import (
    RepositoryIndexLimitError,
    RepositoryIndexRegistry,
    RepositoryNotIndexedError,
    get_repository_index_registry,
)
from app.services.rag_service import RAGAnswerService
from app.schemas.repository import (
    RepositoryAskRequest,
    RepositoryAskResponse,
    RepositoryIndexRequest,
    RepositoryIndexResponse,
    RepositorySearchRequest,
    RepositorySearchResponse,
)

router = APIRouter()


async def get_github_client(
    settings: Settings = Depends(get_settings),
) -> AsyncIterator[httpx.AsyncClient]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if settings.github_token is not None:
        headers["Authorization"] = (
            f"Bearer {settings.github_token.get_secret_value()}"
        )
    async with httpx.AsyncClient(
        timeout=settings.github_api_timeout_seconds,
        headers=headers,
        follow_redirects=False,
    ) as client:
        yield client


def get_rag_answer_service(
    settings: Settings = Depends(get_settings),
) -> RAGAnswerService:
    generator = None
    if settings.gemini_api_key is not None:
        generator = GeminiAnswerGenerator(
            api_key=settings.gemini_api_key.get_secret_value(),
            model=settings.gemini_model,
            timeout_seconds=settings.gemini_timeout_seconds,
            max_output_tokens=settings.rag_max_output_tokens,
        )
    return RAGAnswerService(
        generator,
        context_chunks=settings.rag_context_chunks,
        max_context_characters=settings.rag_context_max_characters,
    )


@router.post(
    "/index",
    response_model=RepositoryIndexResponse,
)
async def index_repository(
    request: RepositoryIndexRequest,
    settings: Settings = Depends(get_settings),
    client: httpx.AsyncClient = Depends(get_github_client),
    registry: RepositoryIndexRegistry = Depends(get_repository_index_registry),
) -> RepositoryIndexResponse:
    try:
        repository = await GitHubRepositoryIndexer(settings).index(
            request.repository_url, client
        )
        await run_in_threadpool(registry.build_and_store, repository, settings)
        return repository
    except RepositoryIngestionError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=error.detail,
        ) from error
    except EmbeddingError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error
    except RepositoryIndexLimitError as error:
        raise HTTPException(status_code=413, detail=str(error)) from error


@router.post(
    "/ask",
    response_model=RepositoryAskResponse,
)
async def ask_repository(
    request: RepositoryAskRequest,
    settings: Settings = Depends(get_settings),
    registry: RepositoryIndexRegistry = Depends(get_repository_index_registry),
    service: RAGAnswerService = Depends(get_rag_answer_service),
) -> RepositoryAskResponse:
    try:
        retrieval = await run_in_threadpool(
            registry.search,
            request.repository_url,
            request.question,
            settings.rag_context_chunks,
            settings,
        )
        return await service.answer(
            retrieval.repository,
            request.question,
            retrieval.results,
        )
    except RepositoryNotIndexedError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RepositoryIngestionError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=error.detail,
        ) from error
    except EmbeddingError as error:
        raise HTTPException(
            status_code=503,
            detail="Unable to generate embeddings for repository search",
        ) from error
    except GeminiConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except GeminiRateLimitError as error:
        raise HTTPException(status_code=429, detail=str(error)) from error
    except GeminiTimeoutError as error:
        raise HTTPException(status_code=504, detail=str(error)) from error
    except GeminiProviderError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except GeminiError as error:
        raise HTTPException(
            status_code=502,
            detail="Gemini could not complete the request",
        ) from error


@router.post(
    "/search",
    response_model=RepositorySearchResponse,
)
async def search_repository(
    request: RepositorySearchRequest,
    settings: Settings = Depends(get_settings),
    registry: RepositoryIndexRegistry = Depends(get_repository_index_registry),
) -> RepositorySearchResponse:
    try:
        return await run_in_threadpool(
            registry.search,
            request.repository_url,
            request.query,
            request.top_k,
            settings,
        )
    except RepositoryNotIndexedError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RepositoryIngestionError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=error.detail,
        ) from error
    except EmbeddingError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error
