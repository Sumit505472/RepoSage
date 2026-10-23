from app.ingestion.chunking import SourceChunk
from app.retrieval.faiss_index import RankedChunk
from app.schemas.repository import RepositorySearchResult


class HybridRetriever:
    def __init__(self, candidate_count: int = 50, rrf_k: int = 60) -> None:
        if candidate_count <= 0 or rrf_k <= 0:
            raise ValueError("candidate_count and rrf_k must be positive")
        self.candidate_count = candidate_count
        self.rrf_k = rrf_k

    def combine(
        self,
        semantic_hits: list[RankedChunk],
        keyword_hits: list[RankedChunk],
        top_k: int,
    ) -> list[RepositorySearchResult]:
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        chunks: dict[str, SourceChunk] = {}
        semantic_scores: dict[str, float] = {}
        keyword_scores: dict[str, float] = {}
        hybrid_scores: dict[str, float] = {}

        for hits, score_map in (
            (semantic_hits[: self.candidate_count], semantic_scores),
            (keyword_hits[: self.candidate_count], keyword_scores),
        ):
            for rank, hit in enumerate(hits, start=1):
                chunk_id = hit.chunk.chunk_id
                chunks.setdefault(chunk_id, hit.chunk)
                score_map[chunk_id] = hit.score
                hybrid_scores[chunk_id] = hybrid_scores.get(chunk_id, 0.0) + (
                    1.0 / (self.rrf_k + rank)
                )

        ordered_ids = sorted(
            hybrid_scores,
            key=lambda chunk_id: (-hybrid_scores[chunk_id], chunk_id),
        )
        return [
            RepositorySearchResult(
                chunk_id=chunk_id,
                repository=chunks[chunk_id].repository,
                file_path=chunks[chunk_id].file_path,
                language=chunks[chunk_id].language,
                start_line=chunks[chunk_id].start_line,
                end_line=chunks[chunk_id].end_line,
                content=chunks[chunk_id].content,
                semantic_score=semantic_scores.get(chunk_id),
                keyword_score=keyword_scores.get(chunk_id),
                hybrid_score=hybrid_scores[chunk_id],
            )
            for chunk_id in ordered_ids[:top_k]
        ]
