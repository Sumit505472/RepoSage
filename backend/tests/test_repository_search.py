import asyncio
import base64

import httpx
import numpy as np

from app.api.routes.repositories import get_github_client
from app.core.config import Settings, get_settings
from app.schemas.repository import IndexedFile, RepositoryIndexResponse
from app.services.repository_index import (
    RepositoryIndexLimitError,
    RepositoryIndexRegistry,
    get_repository_index_registry,
)
from app.main import app

REPOSITORY_URL = "https://github.com/example/search-test"
AUTH_SOURCE = b"def authenticate_user():\n    token = 'ok'\n    return token\n"
RENDER_SOURCE = b"def render_page():\n    return None\n"


def github_response(
    request: httpx.Request,
    body: object,
    status_code: int = 200,
) -> httpx.Response:
    return httpx.Response(status_code, json=body, request=request)


class DeterministicEmbedder:
    def embed(self, texts: list[str]) -> np.ndarray:
        return np.asarray(
            [
                [1.0, 0.0]
                if "authenticate" in text.casefold()
                or "login" in text.casefold()
                else [0.0, 1.0]
                for text in texts
            ],
            dtype=np.float32,
        )


def github_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/repos/example/search-test":
        return github_response(
            request,
            {
                "private": False,
                "owner": {"login": "example"},
                "name": "search-test",
                "default_branch": "main",
            },
        )
    if path == "/repos/example/search-test/commits/main":
        return github_response(
            request,
            {"commit": {"tree": {"sha": "tree"}}},
        )
    if path == "/repos/example/search-test/git/trees/tree":
        return github_response(
            request,
            {
                "truncated": False,
                "tree": [
                    {
                        "path": "src/auth.py",
                        "type": "blob",
                        "sha": "auth",
                        "size": len(AUTH_SOURCE),
                    },
                    {
                        "path": "src/render.py",
                        "type": "blob",
                        "sha": "render",
                        "size": len(RENDER_SOURCE),
                    },
                ],
            },
        )
    if path.endswith("/git/blobs/auth"):
        return github_response(
            request,
            {
                "encoding": "base64",
                "content": base64.b64encode(AUTH_SOURCE).decode("ascii"),
            },
        )
    if path.endswith("/git/blobs/render"):
        return github_response(
            request,
            {
                "encoding": "base64",
                "content": base64.b64encode(RENDER_SOURCE).decode("ascii"),
            },
        )
    return github_response(request, {}, status_code=404)


def test_index_endpoint_builds_real_searchable_in_memory_index() -> None:
    settings = Settings(
        _env_file=None,
        chunk_size_lines=2,
        chunk_overlap_lines=0,
        retrieval_candidate_count=10,
    )
    registry = RepositoryIndexRegistry(
        embedder_factory=lambda _: DeterministicEmbedder()
    )

    async def override_settings() -> Settings:
        return settings

    async def override_github():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(github_handler)
        ) as client:
            yield client

    def override_registry() -> RepositoryIndexRegistry:
        return registry

    async def execute():
        app.dependency_overrides[get_settings] = override_settings
        app.dependency_overrides[get_github_client] = override_github
        app.dependency_overrides[get_repository_index_registry] = override_registry
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                indexed = await client.post(
                    "/api/repositories/index",
                    json={"repository_url": REPOSITORY_URL},
                )
                searched = await client.post(
                    "/api/repositories/search",
                    json={
                        "repository_url": REPOSITORY_URL,
                        "query": "authenticate user login",
                        "top_k": 5,
                    },
                )
                return indexed, searched
        finally:
            app.dependency_overrides.clear()

    indexed, searched = asyncio.run(execute())

    assert indexed.status_code == 200
    assert indexed.json()["owner"] == "example"
    assert searched.status_code == 200
    result = searched.json()["results"][0]
    assert result["file_path"] == "src/auth.py"
    assert result["start_line"] == 1
    assert result["end_line"] == 2
    assert "def authenticate_user" in result["content"]
    assert result["semantic_score"] is not None
    assert result["keyword_score"] is not None
    assert result["hybrid_score"] > 0


def test_search_returns_not_found_before_repository_is_indexed() -> None:
    settings = Settings(_env_file=None)
    registry = RepositoryIndexRegistry(
        embedder_factory=lambda _: DeterministicEmbedder()
    )

    async def override_settings() -> Settings:
        return settings

    def override_registry() -> RepositoryIndexRegistry:
        return registry

    async def execute():
        app.dependency_overrides[get_settings] = override_settings
        app.dependency_overrides[get_repository_index_registry] = override_registry
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                return await client.post(
                    "/api/repositories/search",
                    json={
                        "repository_url": REPOSITORY_URL,
                        "query": "login",
                    },
                )
        finally:
            app.dependency_overrides.pop(get_settings, None)
            app.dependency_overrides.pop(
                get_repository_index_registry, None
            )

    result = asyncio.run(execute())

    assert result.status_code == 404
    assert result.json()["detail"] == (
        "Repository is not indexed in this process; index it first"
    )


def test_search_rejects_invalid_top_k_and_blank_query() -> None:
    async def execute():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            invalid_top_k = await client.post(
                "/api/repositories/search",
                json={
                    "repository_url": REPOSITORY_URL,
                    "query": "login",
                    "top_k": 0,
                },
            )
            blank_query = await client.post(
                "/api/repositories/search",
                json={
                    "repository_url": REPOSITORY_URL,
                    "query": "   ",
                },
            )
            return invalid_top_k, blank_query

    invalid_top_k, blank_query = asyncio.run(execute())

    assert invalid_top_k.status_code == 422
    assert blank_query.status_code == 422


def test_registry_rejects_repository_above_chunk_limit() -> None:
    settings = Settings(
        _env_file=None,
        chunk_size_lines=1,
        chunk_overlap_lines=0,
        max_repository_chunks=1,
    )
    repository = RepositoryIndexResponse(
        owner="example",
        name="oversized",
        branch="main",
        files=[
            IndexedFile(
                path="main.py",
                language="Python",
                source="first\nsecond\n",
            )
        ],
    )
    registry = RepositoryIndexRegistry(
        embedder_factory=lambda _: DeterministicEmbedder()
    )

    try:
        registry.build_and_store(repository, settings)
    except RepositoryIndexLimitError as error:
        assert "chunk limit" in str(error)
    else:
        raise AssertionError("Repository above chunk limit was indexed")
