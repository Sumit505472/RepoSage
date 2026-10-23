import numpy as np
import pytest

from app.ingestion.chunking import SourceChunk
from app.retrieval.bm25 import BM25Index, tokenize
from app.retrieval.embeddings import EmbeddingError, EmbeddingGenerator
from app.retrieval.faiss_index import FaissVectorIndex, RankedChunk
from app.retrieval.hybrid import HybridRetriever


def chunk(
    chunk_id: str,
    content: str,
    file_path: str | None = None,
) -> SourceChunk:
    return SourceChunk(
        chunk_id=chunk_id,
        repository="owner/repo",
        file_path=file_path or f"src/{chunk_id}.py",
        language="Python",
        start_line=1,
        end_line=2,
        content=content,
    )


class StubModel:
    def __init__(self, dimension: int, vectors: list[list[float]]) -> None:
        self.dimension = dimension
        self.vectors = vectors

    def get_sentence_embedding_dimension(self) -> int:
        return self.dimension

    def encode(
        self,
        sentences: list[str],
        *,
        convert_to_numpy: bool,
        normalize_embeddings: bool,
        show_progress_bar: bool,
    ) -> np.ndarray:
        assert len(sentences) == len(self.vectors)
        assert convert_to_numpy
        assert normalize_embeddings
        assert not show_progress_bar
        return np.asarray(self.vectors, dtype=np.float32)


def test_embedding_generator_validates_output_dimensions(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.retrieval.embeddings._load_model",
        lambda _: StubModel(3, [[1.0, 0.0]]),
    )

    with pytest.raises(EmbeddingError, match="invalid vectors"):
        EmbeddingGenerator("test-model").embed(["source"])


def test_embedding_generator_handles_empty_input_without_loading_model(
    monkeypatch,
) -> None:
    def unexpected_load(_: str):
        raise AssertionError("Empty text list must not load the model")

    monkeypatch.setattr("app.retrieval.embeddings._load_model", unexpected_load)

    embeddings = EmbeddingGenerator("test-model").embed([])

    assert embeddings.shape == (0, 0)


def test_faiss_returns_nearest_chunks_and_preserves_position_mapping() -> None:
    chunks = [chunk("east", "east vector"), chunk("north", "north vector")]
    index = FaissVectorIndex()
    index.rebuild(chunks, [[1.0, 0.0], [0.0, 1.0]])

    results = index.search([0.0, 1.0], top_k=2)

    assert [hit.chunk.chunk_id for hit in results] == ["north", "east"]
    assert results[0].score == pytest.approx(1.0)


def test_faiss_empty_index_and_invalid_inputs_are_safe() -> None:
    index = FaissVectorIndex()
    index.rebuild([], np.empty((0, 0), dtype=np.float32))

    assert index.search([1.0, 0.0], top_k=3) == []
    with pytest.raises(ValueError, match="top_k"):
        index.search([1.0, 0.0], top_k=0)
    with pytest.raises(ValueError, match="metadata"):
        index.rebuild([chunk("one", "one")], [[1.0], [0.0]])


def test_bm25_identifier_tokenization_supports_snake_and_camel_case() -> None:
    tokens = tokenize("get_user_by_id userId HTTPClient calculateTotal")

    assert "get_user_by_id" in tokens
    assert "user" in tokens and "id" in tokens
    assert "http" in tokens and "client" in tokens
    assert "calculate" in tokens and "total" in tokens


def test_bm25_exact_identifier_query_returns_original_metadata() -> None:
    relevant = chunk(
        "auth",
        "def get_user_by_id(user_id):\n    return user_id\n",
        "src/auth.py",
    )
    unrelated = chunk("render", "def render_page(): return None", "src/web.py")
    another_unrelated = chunk(
        "docs", "read documentation about project structure", "README.md"
    )
    index = BM25Index([unrelated, relevant, another_unrelated])

    results = index.search("get_user_by_id", top_k=2)

    assert results[0].chunk.chunk_id == "auth"
    assert results[0].chunk.file_path == "src/auth.py"
    assert results[0].score > 0


def test_bm25_empty_query_and_corpus_return_no_hits() -> None:
    assert BM25Index([]).search("search", top_k=5) == []
    assert BM25Index([chunk("only", "some text")]).search("", top_k=5) == []
    assert BM25Index([chunk("only", "single document")]).search(
        "single", top_k=5
    )[0].chunk.chunk_id == "only"


def test_hybrid_rrf_merges_duplicates_and_sorts_deterministically() -> None:
    first = chunk("first", "first content")
    second = chunk("second", "second content")
    retriever = HybridRetriever(candidate_count=10, rrf_k=60)

    results = retriever.combine(
        [RankedChunk(first, 0.9), RankedChunk(second, 0.8)],
        [RankedChunk(first, 4.0)],
        top_k=5,
    )

    assert [result.chunk_id for result in results] == ["first", "second"]
    assert results[0].semantic_score == pytest.approx(0.9)
    assert results[0].keyword_score == pytest.approx(4.0)
    assert results[0].hybrid_score == pytest.approx(1 / 61 + 1 / 61)
    assert results[1].keyword_score is None


def test_hybrid_handles_empty_retriever_results() -> None:
    only_semantic = chunk("semantic", "semantic match")
    only_keyword = chunk("keyword", "keyword match")
    retriever = HybridRetriever(rrf_k=60)

    semantic_results = retriever.combine(
        [RankedChunk(only_semantic, 0.5)], [], top_k=3
    )
    keyword_results = retriever.combine(
        [], [RankedChunk(only_keyword, 1.5)], top_k=3
    )

    assert [result.chunk_id for result in semantic_results] == ["semantic"]
    assert semantic_results[0].keyword_score is None
    assert [result.chunk_id for result in keyword_results] == ["keyword"]
    assert keyword_results[0].semantic_score is None
