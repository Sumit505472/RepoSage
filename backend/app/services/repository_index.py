from collections.abc import Callable
from threading import RLock
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

from app.core.config import Settings
from app.ingestion.chunking import CodeChunker, SourceChunk
from app.ingestion.github import parse_repository_url
from app.retrieval.bm25 import BM25Index
from app.retrieval.embeddings import EmbeddingGenerator
from app.retrieval.faiss_index import FaissVectorIndex
from app.retrieval.hybrid import HybridRetriever
from app.schemas.repository import (
    RepositoryIndexResponse,
    RepositorySearchResponse,
)


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> NDArray[np.float32]: ...


class RepositoryNotIndexedError(LookupError):
    pass


class RepositoryIndexLimitError(ValueError):
    pass


class IndexedRepository:
    def __init__(
        self,
        repository: str,
        chunks: list[SourceChunk],
        embedder: Embedder | None,
        vector_index: FaissVectorIndex,
        keyword_index: BM25Index,
    ) -> None:
        self.repository = repository
        self.chunks = tuple(chunks)
        self.embedder = embedder
        self.vector_index = vector_index
        self.keyword_index = keyword_index


class RepositoryIndexRegistry:
    def __init__(
        self,
        embedder_factory: Callable[[str], Embedder] = EmbeddingGenerator,
    ) -> None:
        self._embedder_factory = embedder_factory
        self._repositories: dict[str, IndexedRepository] = {}
        self._lock = RLock()

    @staticmethod
    def repository_key(owner: str, name: str) -> str:
        return f"{owner.casefold()}/{name.casefold()}"

    def build_and_store(
        self,
        repository: RepositoryIndexResponse,
        settings: Settings,
    ) -> int:
        repository_id = self.repository_key(repository.owner, repository.name)
        chunks = CodeChunker(
            settings.chunk_size_lines,
            settings.chunk_overlap_lines,
        ).chunk_repository(repository)
        if len(chunks) > settings.max_repository_chunks:
            raise RepositoryIndexLimitError(
                "Repository exceeds the configured chunk limit"
            )
        vector_index = FaissVectorIndex()
        embedder: Embedder | None = None
        if chunks:
            embedder = self._embedder_factory(settings.embedding_model_name)
            vectors = embedder.embed([chunk.content for chunk in chunks])
            vector_index.rebuild(chunks, vectors)
        else:
            vector_index.rebuild([], np.empty((0, 0), dtype=np.float32))
        keyword_index = BM25Index(chunks)
        indexed_repository = IndexedRepository(
            repository_id,
            chunks,
            embedder,
            vector_index,
            keyword_index,
        )
        with self._lock:
            self._repositories[repository_id] = indexed_repository
        return len(chunks)

    def search(
        self,
        repository_url: str,
        query: str,
        top_k: int,
        settings: Settings,
    ) -> RepositorySearchResponse:
        reference = parse_repository_url(repository_url)
        repository_id = self.repository_key(reference.owner, reference.name)
        with self._lock:
            indexed_repository = self._repositories.get(repository_id)
        if indexed_repository is None:
            raise RepositoryNotIndexedError(
                "Repository is not indexed in this process; index it first"
            )

        semantic_hits = []
        if indexed_repository.embedder is not None:
            query_embedding = indexed_repository.embedder.embed([query])
            semantic_hits = indexed_repository.vector_index.search(
                query_embedding[0],
                settings.retrieval_candidate_count,
            )
        keyword_hits = indexed_repository.keyword_index.search(
            query, settings.retrieval_candidate_count
        )
        results = HybridRetriever(
            candidate_count=settings.retrieval_candidate_count,
            rrf_k=settings.retrieval_rrf_k,
        ).combine(semantic_hits, keyword_hits, top_k)
        return RepositorySearchResponse(
            repository=indexed_repository.repository,
            query=query,
            results=results,
        )


repository_index_registry = RepositoryIndexRegistry()


def get_repository_index_registry() -> RepositoryIndexRegistry:
    return repository_index_registry
