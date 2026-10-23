from collections.abc import AsyncIterator

import httpx
from fastapi import APIRouter, Depends, HTTPException
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings, get_settings
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
from app.schemas.repository import (
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
