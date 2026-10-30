from threading import RLock
from typing import Any, Protocol

import numpy as np
import httpx
from numpy.typing import NDArray


class EmbeddingError(RuntimeError):
    pass


_MODEL_LOCK = RLock()
_MODEL_CACHE: dict[str, "SentenceTransformerModel"] = {}


class SentenceTransformerModel(Protocol):
    def get_sentence_embedding_dimension(self) -> int | None: ...

    def encode(
        self,
        sentences: list[str],
        *,
        convert_to_numpy: bool,
        normalize_embeddings: bool,
        show_progress_bar: bool,
    ) -> Any: ...


def _load_model(model_name: str) -> SentenceTransformerModel:
    with _MODEL_LOCK:
        if model_name in _MODEL_CACHE:
            return _MODEL_CACHE[model_name]
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as error:
            raise EmbeddingError(
                "Sentence Transformers is not installed; install backend requirements"
            ) from error
        try:
            model = SentenceTransformer(model_name)
        except (httpx.HTTPError, OSError, RuntimeError, ValueError) as error:
            raise EmbeddingError(
                "Unable to load the configured embedding model"
            ) from error
        _MODEL_CACHE[model_name] = model
        return model


class EmbeddingGenerator:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    def embed(self, texts: list[str]) -> NDArray[np.float32]:
        if not texts:
            return np.empty((0, 0), dtype=np.float32)

        model = _load_model(self.model_name)
        try:
            dimension_getter = getattr(model, "get_embedding_dimension", None)
            if dimension_getter is None:
                dimension = model.get_sentence_embedding_dimension()
            else:
                dimension = dimension_getter()
            with _MODEL_LOCK:
                embeddings = np.asarray(
                    model.encode(
                        texts,
                        convert_to_numpy=True,
                        normalize_embeddings=True,
                        show_progress_bar=False,
                    ),
                    dtype=np.float32,
                )
        except (httpx.HTTPError, OSError, RuntimeError, ValueError) as error:
            raise EmbeddingError("Unable to generate embeddings") from error

        if (
            dimension is None
            or dimension <= 0
            or embeddings.shape != (len(texts), dimension)
            or not np.isfinite(embeddings).all()
        ):
            raise EmbeddingError("Embedding model returned invalid vectors")
        return embeddings
