import os
import logging
import getpass
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import chromadb
from chromadb.errors import ChromaError
from sentence_transformers import SentenceTransformer
from sentence_transformers.util import cos_sim

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "collection_name": "agent_exploration_memory",
    "embedding_model": "all-MiniLM-L6-v2",
    "similarity_threshold": 0.8,
    "default_top_k": 5,
    "hnsw_space": "cosine"
}

class VectorMemory:
    """
    ChromaDB-based Vector Memory System (Enhanced Version)
    Features: Parameter validation, batch operations, memory management, model optimization, detailed logging
    """
    
    def __init__(
        self, 
        persist_directory: Optional[str] = None,
        collection_name: str = DEFAULT_CONFIG["collection_name"],
        embedding_model: str = DEFAULT_CONFIG["embedding_model"],
        device: str = "cpu"
    ):
        if persist_directory is None:
            current_user = getpass.getuser()
            persist_directory = str(Path("data") / current_user / "vector_store")
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        logger.info(f"Vector memory storage path: {self.persist_directory}")
        
        try:
            self.client = chromadb.PersistentClient(path=str(self.persist_directory))
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": DEFAULT_CONFIG["hnsw_space"]}
            )
            logger.info(f"ChromaDB collection '{collection_name}' initialized")
        except ChromaError as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            raise RuntimeError(f"VectorMemory init failed: {e}") from e
        
        self.device = device
        self.model_name = embedding_model
        self.model = self._load_embedding_model(retries=3)
        logger.info(f"VectorMemory initialized successfully (model: {embedding_model}, device: {device})")

    def _load_embedding_model(self, retries: int = 3) -> SentenceTransformer:
        """Load embedding model, supports failure retry"""
        for attempt in range(retries):
            try:
                hf_token = os.getenv("HF_TOKEN")
                if hf_token:
                    model = SentenceTransformer(self.model_name, device=self.device, token=hf_token)
                else:
                    model = SentenceTransformer(self.model_name, device=self.device)
                return model
            except Exception as e:
                logger.warning(f"Load model attempt {attempt+1} failed: {e}")
                if attempt == retries - 1:
                    raise RuntimeError(f"Failed to load embedding model after {retries} attempts") from e
                import time
                time.sleep(1)
        raise RuntimeError("Model load retries exhausted")

    def _get_embedding(self, text: str) -> List[float]:
        """Generate text embedding (parameter validation + empty value handling)"""
        if not isinstance(text, str) or text.strip() == "":
            logger.warning("Empty text for embedding, returning zero vector")
            return [0.0] * 384
        return self.model.encode(text.strip()).tolist()

    def add_memory(
        self, 
        doc_id: str, 
        topic: str, 
        content_summary: str, 
        metadata: Dict[str, Any]
    ) -> bool:
        """Add single memory (returns operation result)"""
        if not doc_id or not content_summary:
            logger.error("doc_id and content_summary are required")
            return False
        
        try:
            embedding = self._get_embedding(content_summary)
            metadata["topic"] = topic
            import time
            metadata["create_time"] = metadata.get("create_time", time.time())
            metadata["user_id"] = metadata.get("user_id", getpass.getuser())
            
            self.collection.add(
                ids=[doc_id],
                embeddings=[embedding],
                documents=[content_summary.strip()],
                metadatas=[metadata]
            )
            logger.debug(f"Memory added successfully (ID: {doc_id}, topic: {topic[:20]}...)")
            return True
        except Exception as e:
            logger.error(f"Failed to add memory (ID: {doc_id}): {e}")
            return False

    def add_bulk_memories(
        self, 
        doc_ids: List[str], 
        topics: List[str], 
        content_summaries: List[str], 
        metadatas: List[Dict[str, Any]]
    ) -> Tuple[int, int]:
        """Batch add memories (returns success/failure count)"""
        if len(doc_ids) != len(topics) or len(doc_ids) != len(content_summaries) or len(doc_ids) != len(metadatas):
            logger.error("Bulk add failed: list lengths mismatch")
            return 0, len(doc_ids)
        
        success_count = 0
        fail_count = 0
        for i in range(len(doc_ids)):
            if self.add_memory(doc_ids[i], topics[i], content_summaries[i], metadatas[i]):
                success_count += 1
            else:
                fail_count += 1
        
        logger.info(f"Bulk add completed: {success_count} success, {fail_count} failed")
        return success_count, fail_count

    def find_similar(
        self, 
        query_text: str, 
        n_results: int = DEFAULT_CONFIG["default_top_k"], 
        threshold: float = DEFAULT_CONFIG["similarity_threshold"]
    ) -> List[Dict[str, Any]]:
        """
        Retrieve similar memories (enhanced version: threshold range validation + result sorting)
        :param query_text: Query text
        :param n_results: Maximum return count
        :param threshold: Similarity threshold (0~1)
        :return: Structured similar memory list (sorted by similarity descending)
        """
        if threshold < 0 or threshold > 1:
            logger.warning(f"Invalid threshold ({threshold}), using default {DEFAULT_CONFIG['similarity_threshold']}")
            threshold = DEFAULT_CONFIG["similarity_threshold"]
        if n_results < 1:
            n_results = DEFAULT_CONFIG["default_top_k"]
        
        try:
            query_embedding = self._get_embedding(query_text)
            if sum(query_embedding) == 0:
                logger.warning("Empty query embedding, return empty results")
                return []
            
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                include=["metadatas", "documents", "distances"]
            )
            
            similar_items = []
            if results['ids'] and results['ids'][0]:
                for i, doc_id in enumerate(results['ids'][0]):
                    distance = results['distances'][0][i]
                    similarity = round(1 - distance, 4)
                    
                    if similarity >= threshold:
                        item = {
                            "id": doc_id,
                            "similarity": similarity,
                            "metadata": results['metadatas'][0][i],
                            "content": results['documents'][0][i],
                            "distance": round(distance, 4)
                        }
                        similar_items.append(item)
            
            similar_items.sort(key=lambda x: x["similarity"], reverse=True)
            logger.debug(f"Found {len(similar_items)} similar memories (query: {query_text[:20]}...)")
            return similar_items
        except ChromaError as e:
            logger.error(f"ChromaDB query failed: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to query similar memories: {e}")
            return []

    def delete_memory(self, doc_id: str) -> bool:
        """Delete memory by specified ID"""
        try:
            self.collection.delete(ids=[doc_id])
            logger.debug(f"Memory deleted (ID: {doc_id})")
            return True
        except Exception as e:
            logger.error(f"Failed to delete memory (ID: {doc_id}): {e}")
            return False

    def clear_all_memories(self) -> bool:
        """Clear all memories (use with caution)"""
        try:
            self.collection.delete(ids=self.collection.get()["ids"])
            logger.warning("All memories in collection have been cleared!")
            return True
        except Exception as e:
            logger.error(f"Failed to clear all memories: {e}")
            return False

    def get_total_count(self) -> int:
        """Get total memory count (enhanced exception handling)"""
        try:
            count = self.collection.count()
            logger.debug(f"Total memories in collection: {count}")
            return count
        except Exception as e:
            logger.error(f"Failed to get memory count: {e}")
            return 0

    def close(self) -> None:
        """Clean up resources (optional)"""
        logger.info("VectorMemory resources released")
