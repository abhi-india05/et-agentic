import os
import pickle
from typing import Any, Dict, List, Optional
from datetime import datetime

import numpy as np

from backend.config.settings import settings
from backend.utils.logger import get_logger

logger = get_logger("vector_store")

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False

try:
    from openai import OpenAI as _OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class VectorMemoryStore:
    def __init__(self, dimension: int = 1536, index_path: Optional[str] = None):
        self.dimension = dimension
        self.index_path = index_path or settings.faiss_index_path
        self.documents: List[Dict[str, Any]] = []
        self.index = None
        self._openai_client = None
        self._initialize()

    def _initialize(self) -> None:
        if not FAISS_AVAILABLE:
            logger.warning("faiss_unavailable", reason="faiss-cpu not installed, using in-memory fallback")
        else:
            self.index = faiss.IndexFlatL2(self.dimension)
            logger.info("faiss_index_initialized", dimension=self.dimension)

        if OPENAI_AVAILABLE and settings.has_openai_key:
            try:
                self._openai_client = _OpenAI(api_key=settings.openai_api_key)
                logger.info("embedding_client_ready")
            except Exception as e:
                logger.warning("embedding_client_failed", error=str(e))
                self._openai_client = None

    def _get_embedding(self, text: str) -> np.ndarray:
        if self._openai_client:
            try:
                response = self._openai_client.embeddings.create(
                    model="text-embedding-3-small",
                    input=text[:8000],   
                )
                return np.array(response.data[0].embedding, dtype=np.float32)
            except Exception as e:
                logger.warning("embedding_fallback", error=str(e))

        rng = np.random.default_rng(abs(hash(text)) % (2**32))
        return rng.standard_normal(self.dimension).astype(np.float32)

    def add_document(
        self,
        doc_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        try:
            embedding = self._get_embedding(content)
            doc = {
                "doc_id": doc_id,
                "content": content,
                "metadata": metadata or {},
                "timestamp": datetime.utcnow().isoformat(),
                "embedding_index": len(self.documents),
            }
            self.documents.append(doc)

            if self.index is not None and FAISS_AVAILABLE:
                self.index.add(embedding.reshape(1, -1))

            return True
        except Exception as e:
            logger.error("add_document_failed", doc_id=doc_id, error=str(e))
            return False

    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        if not self.documents:
            return []

        try:
            query_embedding = self._get_embedding(query)

            if self.index is not None and FAISS_AVAILABLE and self.index.ntotal > 0:
                k = min(top_k, len(self.documents))
                distances, indices = self.index.search(query_embedding.reshape(1, -1), k)
                results = []
                for dist, idx in zip(distances[0], indices[0]):
                    if 0 <= idx < len(self.documents):
                        doc = dict(self.documents[idx])
                        doc["similarity_score"] = float(1.0 / (1.0 + dist))
                        results.append(doc)
            else:
                results = [dict(d) for d in self.documents[-top_k:]]
                for r in results:
                    r["similarity_score"] = 0.5

            if filter_metadata:
                results = [
                    r for r in results
                    if all(r["metadata"].get(k) == v for k, v in filter_metadata.items())
                ]

            return results

        except Exception as e:
            logger.error("search_failed", error=str(e))
            return []

    def get_context_for_company(self, company: str) -> str:
        results = self.search(company, top_k=3, filter_metadata={"company": company})
        if not results:
            results = self.search(company, top_k=3)

        if not results:
            return "No prior context available."

        return "\n".join(
            f"[{r['timestamp'][:10]}] {r['content']}" for r in results
        )

    def save(self) -> None:
        try:
            index_dir = os.path.dirname(self.index_path)
            if index_dir:
                os.makedirs(index_dir, exist_ok=True)

            with open(f"{self.index_path}_docs.pkl", "wb") as f:
                pickle.dump(self.documents, f)

            if self.index is not None and FAISS_AVAILABLE:
                faiss.write_index(self.index, f"{self.index_path}.faiss")

            logger.info("vector_store_saved", doc_count=len(self.documents))
        except Exception as e:
            logger.error("vector_store_save_failed", error=str(e))

    def load(self) -> None:
        try:
            docs_path = f"{self.index_path}_docs.pkl"
            if os.path.exists(docs_path):
                with open(docs_path, "rb") as f:
                    self.documents = pickle.load(f)
                logger.info("vector_store_loaded", doc_count=len(self.documents))
            else:
                logger.info("vector_store_fresh", reason="no persisted index found")

            faiss_path = f"{self.index_path}.faiss"
            if FAISS_AVAILABLE and os.path.exists(faiss_path):
                self.index = faiss.read_index(faiss_path)
                logger.info("faiss_index_loaded")

        except Exception as e:
            logger.error("vector_store_load_failed", error=str(e))
            self.documents = []
            if FAISS_AVAILABLE:
                self.index = faiss.IndexFlatL2(self.dimension)

    def clear(self) -> None:
        self.documents = []
        if FAISS_AVAILABLE:
            self.index = faiss.IndexFlatL2(self.dimension)
        logger.info("vector_store_cleared")

    def stats(self) -> Dict[str, Any]:
        return {
            "total_documents": len(self.documents),
            "faiss_available": FAISS_AVAILABLE,
            "dimension": self.dimension,
            "index_active": self.index is not None,
            "embedding_client": self._openai_client is not None,
        }


_store_instance: Optional[VectorMemoryStore] = None


def get_vector_store() -> VectorMemoryStore:
    global _store_instance
    if _store_instance is None:
        _store_instance = VectorMemoryStore()
    return _store_instance