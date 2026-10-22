from collections.abc import AsyncIterator

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.core.config import Settings, get_settings
from app.ingestion.github import (
    GitHubRepositoryIndexer,
    RepositoryIngestionError,
)
from app.schemas.repository import (
    RepositoryIndexRequest,
    RepositoryIndexResponse,
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
) -> RepositoryIndexResponse:
    try:
        return await GitHubRepositoryIndexer(settings).index(
            request.repository_url, client
        )
    except RepositoryIngestionError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=error.detail,
        ) from error
