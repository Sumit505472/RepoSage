from dataclasses import dataclass

import faiss
import numpy as np
from numpy.typing import ArrayLike

from app.ingestion.chunking import SourceChunk


@dataclass(frozen=True)
class RankedChunk:
    chunk: SourceChunk
    score: float


class FaissVectorIndex:
    def __init__(self) -> None:
        self._index: faiss.Index | None = None
        self._chunks: tuple[SourceChunk, ...] = ()
        self._dimension: int | None = None

    @property
    def size(self) -> int:
        return len(self._chunks)

    def rebuild(
        self,
        chunks: list[SourceChunk],
        embeddings: ArrayLike,
    ) -> None:
        vectors = np.asarray(embeddings, dtype=np.float32)
        if not chunks:
            if vectors.size != 0:
                raise ValueError("Cannot map embeddings to an empty chunk set")
            self._index = None
            self._chunks = ()
            self._dimension = None
            return
        if len({chunk.chunk_id for chunk in chunks}) != len(chunks):
            raise ValueError("Chunk IDs must be unique within the vector index")
        if (
            vectors.ndim != 2
            or vectors.shape[0] != len(chunks)
            or vectors.shape[1] == 0
            or not np.isfinite(vectors).all()
        ):
            raise ValueError("Embedding matrix does not match chunk metadata")
        norms = np.linalg.norm(vectors, axis=1)
        if np.any(norms == 0):
            raise ValueError("Cannot index zero-length embeddings")

        normalized = np.ascontiguousarray(vectors.copy())
        faiss.normalize_L2(normalized)
        index = faiss.IndexFlatIP(normalized.shape[1])
        index.add(normalized)

        self._index = index
        self._chunks = tuple(chunks)
        self._dimension = normalized.shape[1]

    def search(
        self,
        query_embedding: ArrayLike,
        top_k: int,
    ) -> list[RankedChunk]:
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        if self._index is None or not self._chunks:
            return []

        query = np.asarray(query_embedding, dtype=np.float32)
        if query.ndim == 1:
            query = query.reshape(1, -1)
        if (
            query.shape != (1, self._dimension)
            or not np.isfinite(query).all()
            or np.linalg.norm(query) == 0
        ):
            raise ValueError("Query embedding has an invalid dimension or value")
        normalized_query = np.ascontiguousarray(query.copy())
        faiss.normalize_L2(normalized_query)
        scores, positions = self._index.search(
            normalized_query, min(top_k, len(self._chunks))
        )
        return [
            RankedChunk(self._chunks[int(position)], float(score))
            for score, position in zip(scores[0], positions[0])
            if 0 <= position < len(self._chunks)
        ]
