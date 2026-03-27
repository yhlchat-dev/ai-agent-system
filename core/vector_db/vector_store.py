#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Vector Storage Abstract Interface: 1.0 uses minimal implementation, can be replaced with FAISS/Milvus later"""
from abc import ABC, abstractmethod
from utils.logging import vector_db_logger

class BaseVectorStore(ABC):
    """Vector Storage Abstract Base Class"""
    @abstractmethod
    def add_embedding(self, text, embedding):
        """Add text and corresponding vector"""
        pass
    
    @abstractmethod
    def search_similar(self, query_embedding, top_k=5):
        """Search similar vectors"""
        pass

class SimpleVectorStore(BaseVectorStore):
    """1.0 Minimal Vector Storage (memory version, for demo only)"""
    def __init__(self):
        self.embeddings = []
        vector_db_logger.info("Initialized minimal vector storage (version 1.0)")
    
    def add_embedding(self, text, embedding):
        """Add vector (1.0 only stores, no validation)"""
        self.embeddings.append({
            "text": text,
            "embedding": embedding,
            "add_time": len(self.embeddings)
        })
        vector_db_logger.debug(f"Added vector: {text[:20]}...")
    
    def search_similar(self, query_embedding, top_k=5):
        """Search similar vectors (1.0 only returns last K items, replace with cosine similarity later)"""
        results = self.embeddings[-top_k:] if len(self.embeddings) >= top_k else self.embeddings
        vector_db_logger.debug(f"Found {len(results)} similar vectors (1.0 minimal version)")
        return results

vector_store = SimpleVectorStore()
