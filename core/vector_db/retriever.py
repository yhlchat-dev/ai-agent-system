#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Vector Retrieval Interface: Encapsulate retrieval logic, extensible later"""
from .vector_store import vector_store
from utils.logging import vector_db_logger

class VectorRetriever:
    """Vector Retriever"""
    def __init__(self, vector_store=vector_store):
        self.vector_store = vector_store
    
    def retrieve(self, query_embedding, top_k=5):
        """Retrieve similar vectors"""
        try:
            results = self.vector_store.search_similar(query_embedding, top_k)
            return [item["text"] for item in results]
        except Exception as e:
            vector_db_logger.error(f"Vector retrieval failed: {e}", exc_info=True)
            return []
    
    def add_text(self, text, embedding):
        """Add text to vector store"""
        self.vector_store.add_embedding(text, embedding)

vector_retriever = VectorRetriever()
