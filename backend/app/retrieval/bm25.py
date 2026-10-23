import re

from rank_bm25 import BM25Okapi

from app.ingestion.chunking import SourceChunk
from app.retrieval.faiss_index import RankedChunk

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*")
CAMEL_BOUNDARY_PATTERN = re.compile(
    r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])"
)


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for match in TOKEN_PATTERN.findall(text):
        tokens.append(match.casefold())
        separated = CAMEL_BOUNDARY_PATTERN.sub(" ", match)
        tokens.extend(
            part.casefold()
            for part in re.split(r"[_\W]+", separated)
            if part
        )
    return tokens


class BM25Index:
    def __init__(self, chunks: list[SourceChunk]) -> None:
        tokenized = [
            (chunk, tokenize(chunk.content))
            for chunk in chunks
        ]
        searchable = [(chunk, tokens) for chunk, tokens in tokenized if tokens]
        self._chunks = tuple(chunk for chunk, _ in searchable)
        self._documents = tuple(tokens for _, tokens in searchable)
        self._index = BM25Okapi(list(self._documents)) if searchable else None

    def search(self, query: str, top_k: int) -> list[RankedChunk]:
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        query_tokens = tokenize(query)
        if self._index is None or not query_tokens:
            return []

        scores = self._index.get_scores(query_tokens)
        query_terms = set(query_tokens)
        ranked_positions = sorted(
            (
                position
                for position in range(len(self._chunks))
                if query_terms.intersection(self._documents[position])
            ),
            key=lambda position: (
                -float(scores[position]),
                -len(query_terms.intersection(self._documents[position])),
                self._chunks[position].chunk_id,
            ),
        )
        return [
            RankedChunk(self._chunks[position], float(scores[position]))
            for position in ranked_positions[:top_k]
        ]
