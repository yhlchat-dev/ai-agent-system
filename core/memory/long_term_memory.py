#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Long-term Memory Module - Industrial-grade Three-layer RAG Retrieval Architecture
================
Core Features:
- SQLite stores structured data (habits, task logs, conversation archives, pending items, preference temp data)
- ChromaDB vector retrieval (semantic search), supports auto-degradation
- BM25 full-text retrieval (keyword recall)
- Three-layer RAG architecture: Recall Layer -> Fusion Layer -> Re-ranking Layer
- Sensitive information detection and processing (configurable BLOCK/MASK strategy)
- Preference learning and auto-promotion mechanism
- Multi-user data isolation, each user has independent storage files

Three-layer RAG Architecture:
1. Recall Layer: Vector recall + BM25 keyword recall + metadata filtering
2. Fusion Layer: RRF weighted fusion ranking (vector 0.7 + BM25 0.3)
3. Re-ranking Layer: Keep top 10% high-quality memories, deduplication and cleaning

Fault Tolerance Features:
- Auto-degradation to SQLite-only retrieval when vector model loading fails
- Auto-degradation to basic retrieval when database operations fail
- Graceful degradation when dependencies are missing
"""

import hashlib
import time
import json
import logging
import os
import re
import math
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Set

logger = logging.getLogger(__name__)

DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
DEFAULT_TOP_K = 5
DEFAULT_CONVERSATION_LIMIT = 20
DEFAULT_PREFERENCE_MIN_MENTIONS = 4
DEFAULT_PREFERENCE_MIN_INTERVAL_DAYS = 2
DEFAULT_CUTOFF_DAYS = 30
MEMORY_ARCHIVE_THRESHOLD_DEFAULT = 0.8

RAG_VECTOR_WEIGHT = 0.7
RAG_BM25_WEIGHT = 0.3
RAG_TOP_PERCENTAGE = 0.1
RAG_CANDIDATE_MULTIPLIER = 3

try:
    os.environ["CHROMA_TELEMETRY_DISABLED"] = "true"
    os.environ["ANONYMIZED_TELEMETRY"] = "False"
    
    import chromadb
    from chromadb.api.models.Collection import Collection
    from chromadb import PersistentClient
    
    import logging
    logging.getLogger("chromadb.telemetry").setLevel(logging.ERROR)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    
    CHROMADB_AVAILABLE = True
except ImportError:
    logger.warning("ChromaDB not installed, vector retrieval will be disabled")
    CHROMADB_AVAILABLE = False
    class Collection:
        pass
    class PersistentClient:
        def __init__(self, path: str): pass
        def get_or_create_collection(self, name: str) -> Collection: return Collection()

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    logger.warning("sentence-transformers not installed, vector model loading failed")
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    class SentenceTransformer:
        def __init__(self, model_name: str):
            raise ImportError("sentence-transformers not installed")
        def encode(self, text: str) -> List[float]:
            return []

try:
    from infra.config import (
        get_user_data_dir,
        ENABLE_SENSITIVE_CHECK,
        SENSITIVE_ACTION,
        MEMORY_ARCHIVE_THRESHOLD
    )
except ImportError:
    logger.warning("Config module import failed, using default config")
    def get_user_data_dir(user_id: str) -> Path:
        return Path(f"data/{user_id}")
    ENABLE_SENSITIVE_CHECK = False
    SENSITIVE_ACTION = "MASK"
    MEMORY_ARCHIVE_THRESHOLD = MEMORY_ARCHIVE_THRESHOLD_DEFAULT

try:
    from core.utils.sensitive_check import scan_text
except ImportError:
    logger.warning("Sensitive detection module import failed, sensitive check disabled")
    class MockDetection:
        is_sensitive = False
        sensitive_types = []
        masked_text = ""
    def scan_text(content: str) -> MockDetection:
        detection = MockDetection()
        detection.masked_text = content
        return detection

try:
    from infra.db_manager import get_db_manager, DatabaseManager
except ImportError:
    logger.error("Database manager import failed, cannot continue")
    raise


class LongTermMemory:
    """
    Long-term Memory: SQLite + ChromaDB Hybrid Storage
    
    Features:
    - Multi-user data isolation (each user has independent files)
    - Vector retrieval auto-degradation (SQLite-only when model loading fails)
    - Sensitive information detection and processing (configurable strategy)
    - Preference learning and auto-promotion
    - Complete exception handling and logging
    """

    def __init__(self, user_id: str = 'default', data_dir: Optional[Path] = None) -> None:
        """
        Initialize long-term memory manager
        
        :param user_id: User unique identifier
        :param data_dir: Data storage directory (None uses default path)
        """
        self.user_id = user_id.strip()
        if not self.user_id:
            raise ValueError("user_id cannot be empty")
        
        if data_dir is None:
            self.data_dir = Path(f"data/{user_id}")
        else:
            self.data_dir = Path(data_dir)
        os.makedirs(str(self.data_dir), exist_ok=True)
        
        self.sqlite_path = self.data_dir / 'long_term.db'
        self.db_manager: DatabaseManager = get_db_manager(str(self.sqlite_path))
        
        try:
            self.conn = self.db_manager.get_connection()
            self.cursor = self.conn.cursor()
        except Exception as e:
            logger.error(f"Failed to get database connection: {e}")
            raise
        
        self._init_sqlite()
        
        self.chroma_client: Optional[PersistentClient] = None
        self.collection: Optional[Collection] = None
        if CHROMADB_AVAILABLE:
            try:
                os.environ['ANONYMIZED_TELEMETRY'] = 'False'
                os.environ['CHROMA_TELEMETRY'] = 'False'
                
                import chromadb.config as chroma_config
                
                self.chroma_path = self.data_dir / 'chromadb'
                self.chroma_client = PersistentClient(
                    path=str(self.chroma_path),
                    settings=chroma_config.Settings(
                        anonymized_telemetry=False,
                        allow_reset=True
                    )
                )
                self.collection = self.chroma_client.get_or_create_collection(name="long_term_memory")
            except Exception as e:
                pass
        
        self.embedder: Optional[SentenceTransformer] = None
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self.embedder = SentenceTransformer(DEFAULT_EMBEDDING_MODEL)
            except Exception as e:
                pass
        
        logger.info(f"Long-term memory manager initialized - User: {self.user_id}")

    def _init_sqlite(self) -> None:
        """Initialize SQLite table structure - force rebuild to clear all old data"""
        try:
            self.cursor.execute("DROP TABLE IF EXISTS habits")
            self.cursor.execute("DROP TABLE IF EXISTS task_logs")
            self.cursor.execute("DROP TABLE IF EXISTS conversations_archive")
            self.cursor.execute("DROP TABLE IF EXISTS pending_confirm")
            self.cursor.execute("DROP TABLE IF EXISTS preference_temp")
            self.conn.commit()
            logger.info("Old tables deleted, all historical data cleared")
        except Exception as e:
            logger.warning(f"Warning deleting old tables: {e}")
        
        table_ddls = [
            '''
            CREATE TABLE habits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                habit_type TEXT,
                content TEXT,
                timestamp REAL,
                access_count INTEGER DEFAULT 0
            )
            ''',
            '''
            CREATE TABLE task_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                task_name TEXT,
                result TEXT,
                timestamp REAL
            )
            ''',
            '''
            CREATE TABLE conversations_archive (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                timestamp REAL,
                role TEXT,
                content TEXT,
                file_path TEXT,
                tags TEXT
            )
            ''',
            '''
            CREATE TABLE pending_confirm (
                user_id TEXT PRIMARY KEY,
                item_type TEXT,
                item_value TEXT,
                item_masked TEXT,
                level TEXT,
                created_at REAL
            )
            ''',
            '''
            CREATE TABLE preference_temp (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                content TEXT,
                expressions TEXT,
                mention_dates TEXT,
                created_at REAL,
                updated_at REAL
            )
            '''
        ]
        
        try:
            for ddl in table_ddls:
                self.db_manager.execute(ddl)
            self.conn.commit()
            logger.info("SQLite table structure initialized - brand new empty tables")
        
        except Exception as e:
            logger.error(f"SQLite initialization failed: {e}")
            raise

    def _process_sensitive_content(self, content: str) -> str:
        """
        Sensitive information processing (unified logic)
        
        :param content: Original content
        :return: Processed content
        :raises ValueError: Sensitive information blocked by BLOCK strategy
        """
        if not ENABLE_SENSITIVE_CHECK:
            return content
        
        detection = scan_text(content)
        if not detection.is_sensitive:
            return content
        
        sensitive_types = ", ".join(detection.sensitive_types)
        if SENSITIVE_ACTION == "BLOCK":
            raise ValueError(f"Sensitive information detected ({sensitive_types}), save blocked")
        elif SENSITIVE_ACTION == "MASK":
            logger.warning(f"Sensitive information detected, auto-masking: {sensitive_types}")
            return detection.masked_text
        
        return content

    def save_habit(self, user_id: str, habit_type: str, content: str) -> None:
        """
        Store user habit (SQLite + optional vector storage)
        
        :param user_id: User ID
        :param habit_type: Habit type
        :param content: Habit content
        :raises ValueError: Sensitive information blocked or invalid parameters
        :raises Exception: Database operation failed
        """
        try:
            if not all([user_id, habit_type, content]):
                raise ValueError("user_id, habit_type, content cannot be empty")
            
            if self._is_duplicate_memory(user_id, content):
                logger.debug(f"Skipping duplicate memory: {content[:50]}...")
                return
            
            processed_content = self._process_sensitive_content(content)
            
            timestamp = datetime.now().timestamp()
            self.db_manager.execute(
                "INSERT INTO habits (user_id, habit_type, content, timestamp, access_count) VALUES (?, ?, ?, ?, 0)",
                (user_id, habit_type, processed_content, timestamp)
            )
            self.conn.commit()
            
            self._check_auto_archive(user_id)
            
            if self.embedder and self.collection:
                try:
                    doc_id = hashlib.md5(f"{user_id}_{habit_type}_{processed_content}".encode()).hexdigest()
                    embedding = self.embedder.encode(processed_content).tolist()
                    metadata = {"user_id": user_id, "type": "habit", "habit_type": habit_type}
                    
                    self.collection.upsert(
                        ids=[doc_id],
                        embeddings=[embedding],
                        metadatas=[metadata],
                        documents=[processed_content]
                    )
                    logger.debug(f"Vector storage successful - ID: {doc_id[:8]}")
                except Exception as e:
                    logger.error(f"Vector storage failed: {e}")
            
            logger.info(f"Habit saved successfully - User: {user_id}, Type: {habit_type}, Content length: {len(processed_content)}")
        
        except ValueError as e:
            logger.error(f"Habit save failed (parameter/sensitive info): {e}")
            raise
        except Exception as e:
            logger.error(f"Habit save failed: {e}", exc_info=True)
            raise

    def get_habit(self, user_id: str, habit_type: str = "preference") -> Optional[str]:
        """
        Query user habit/preference (fixed memory read error)
        
        :param user_id: User ID
        :param habit_type: Habit type (name/phone/preference/plan etc.)
        :return: Habit content or None
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT content FROM habits WHERE user_id=? AND habit_type=? ORDER BY timestamp DESC LIMIT 1",
                (user_id, habit_type)
            )
            result = cursor.fetchone()
            if result:
                content = result[0]
                if "：" in content:
                    return content.split("：", 1)[1]
                return content
            return None
        except Exception as e:
            logger.error(f"Failed to query habit: {e}")
            return None

    def search_memory(
        self, 
        user_id: str, 
        query: str, 
        top_k: int = DEFAULT_TOP_K,
        use_rag: bool = True,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Intelligent hybrid retrieval (supports three-layer RAG architecture)
        
        Three-layer RAG Architecture:
        1. Recall Layer: Vector recall + BM25 keyword recall + metadata filtering
        2. Fusion Layer: RRF weighted fusion ranking (vector 0.7 + BM25 0.3)
        3. Re-ranking Layer: Keep top 10% high-quality memories
        
        :param user_id: User ID
        :param query: Search keyword/statement
        :param top_k: Number of results to return
        :param use_rag: Whether to use three-layer RAG architecture (default True)
        :param metadata_filter: Metadata filter conditions
        :return: Deduplicated result list sorted by comprehensive score
        """
        try:
            if not all([user_id, query]):
                logger.warning("Search parameters empty, returning empty results")
                return []
            
            if use_rag:
                return self._three_layer_rag_search(user_id, query, top_k, metadata_filter)
            
            current_time = time.time()
            sql_results = self._sql_keyword_search(user_id, query, top_k * 2, current_time)
            vector_results = self._vector_semantic_search(user_id, query, top_k, current_time)
            
            all_results = sql_results + vector_results
            all_results.sort(key=lambda x: x.get('score', 0), reverse=True)
            
            unique_results = self._deduplicate_results(all_results, top_k)
            
            logger.info(f"Hybrid search completed - User: {user_id}, Query: {query[:30]}, Results: {len(unique_results)}")
            return unique_results
        
        except Exception as e:
            logger.error(f"Hybrid search failed, degrading to basic search: {e}")
            return self._fallback_search(user_id, query, top_k)

    def _sql_keyword_search(
        self, 
        user_id: str, 
        query: str, 
        limit: int, 
        current_time: float
    ) -> List[Dict[str, Any]]:
        """SQLite keyword search (with scoring)"""
        try:
            rows = self.db_manager.fetchall(
                "SELECT id, habit_type, content, timestamp, access_count FROM habits WHERE user_id=? AND content LIKE ? ORDER BY timestamp DESC LIMIT ?",
                (user_id, f'%{query}%', limit)
            )
            
            results = []
            for row in rows:
                memory_id, habit_type, content, timestamp, access_count = row
                
                keyword_score = 0.8
                time_score = max(0, 1.0 - (current_time - timestamp) / (30 * 24 * 3600))
                frequency_score = min(1.0, access_count / 10.0)
                total_score = keyword_score * 0.4 + time_score * 0.3 + frequency_score * 0.3
                
                results.append({
                    "id": memory_id,
                    "source": "sqlite",
                    "type": habit_type,
                    "content": content,
                    "score": total_score,
                    "timestamp": timestamp,
                    "access_count": access_count
                })
                
                self.update_access_count(user_id, content[:50])
            
            return results
        except Exception as e:
            logger.error(f"SQL keyword search failed: {e}")
            return []

    def _vector_semantic_search(
        self, 
        user_id: str, 
        query: str, 
        top_k: int, 
        current_time: float
    ) -> List[Dict[str, Any]]:
        """ChromaDB vector semantic search (with scoring)"""
        if not (self.embedder and self.collection):
            return []
        
        try:
            query_emb = self.embedder.encode(query).tolist()
            chroma_results = self.collection.query(
                query_embeddings=[query_emb],
                n_results=top_k,
                where={"user_id": user_id}
            )
            
            results = []
            if chroma_results.get('ids') and chroma_results['ids'][0]:
                for i in range(len(chroma_results['ids'][0])):
                    doc_id = chroma_results['ids'][0][i]
                    content = chroma_results['documents'][0][i]
                    metadata = chroma_results['metadatas'][0][i]
                    distance = chroma_results['distances'][0][i]
                    
                    vector_score = 1.0 - distance
                    
                    row = self.db_manager.fetchone(
                        "SELECT timestamp, access_count FROM habits WHERE user_id=? AND content=?",
                        (user_id, content)
                    )
                    
                    if row:
                        timestamp, access_count = row
                        time_score = max(0, 1.0 - (current_time - timestamp) / (30 * 24 * 3600))
                        frequency_score = min(1.0, access_count / 10.0)
                        total_score = vector_score * 0.5 + time_score * 0.3 + frequency_score * 0.2
                    else:
                        total_score = vector_score
                    
                    results.append({
                        "source": "chromadb",
                        "content": content,
                        "metadata": metadata,
                        "score": total_score
                    })
            
            return results
        except Exception as e:
            logger.error(f"Vector semantic search failed: {e}")
            return []

    def _deduplicate_results(self, results: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
        """Deduplicate results and limit count"""
        seen_contents: Set[str] = set()
        unique_results: List[Dict[str, Any]] = []
        
        for r in results:
            content = r.get('content', '')
            if content not in seen_contents:
                seen_contents.add(content)
                unique_results.append(r)
            if len(unique_results) >= top_k:
                break
        
        return unique_results

    def _fallback_search(self, user_id: str, query: str, top_k: int) -> List[Dict[str, Any]]:
        """Fallback search (basic keyword matching only)"""
        try:
            rows = self.db_manager.fetchall(
                "SELECT habit_type, content FROM habits WHERE user_id=? AND content LIKE ? ORDER BY timestamp DESC LIMIT ?",
                (user_id, f'%{query}%', top_k)
            )
            return [{"source": "sqlite", "type": row[0], "content": row[1], "score": 0.5} for row in rows]
        except Exception as e:
            logger.error(f"Fallback search also failed: {e}")
            return []
    
    def _tokenize(self, text: str) -> List[str]:
        """Text tokenization (supports Chinese and English)"""
        text = text.lower()
        chinese_chars = re.findall(r'[\u4e00-\u9fff]+', text)
        english_words = re.findall(r'[a-z0-9]+', text)
        tokens = []
        for chars in chinese_chars:
            tokens.extend(list(chars))
        tokens.extend(english_words)
        return [t for t in tokens if len(t) > 0]
    
    def _calculate_bm25_score(
        self, 
        query_tokens: List[str], 
        doc_tokens: List[str], 
        doc_length: int, 
        avg_doc_length: float,
        doc_count: int,
        df_dict: Dict[str, int],
        k1: float = 1.5,
        b: float = 0.75
    ) -> float:
        """
        Calculate BM25 score
        
        :param query_tokens: Query term list
        :param doc_tokens: Document term list
        :param doc_length: Document length
        :param avg_doc_length: Average document length
        :param doc_count: Total document count
        :param df_dict: Term frequency dictionary
        :param k1: BM25 parameter
        :param b: BM25 parameter
        :return: BM25 score
        """
        score = 0.0
        tf_dict = Counter(doc_tokens)
        
        for term in query_tokens:
            if term not in tf_dict:
                continue
            
            tf = tf_dict[term]
            df = df_dict.get(term, 0)
            
            if df == 0:
                continue
            
            idf = math.log((doc_count - df + 0.5) / (df + 0.5) + 1)
            numerator = tf * (k1 + 1)
            denominator = tf + k1 * (1 - b + b * (doc_length / avg_doc_length))
            score += idf * (numerator / denominator)
        
        return score
    
    def _bm25_search(
        self, 
        user_id: str, 
        query: str, 
        top_k: int,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        BM25 full-text retrieval
        
        :param user_id: User ID
        :param query: Query text
        :param top_k: Number of results to return
        :param metadata_filter: Metadata filter conditions
        :return: BM25 search result list
        """
        try:
            query_tokens = self._tokenize(query)
            if not query_tokens:
                return []
            
            where_clause = "WHERE user_id = ?"
            params = [user_id]
            
            if metadata_filter:
                if 'habit_type' in metadata_filter:
                    where_clause += " AND habit_type = ?"
                    params.append(metadata_filter['habit_type'])
                if 'start_time' in metadata_filter:
                    where_clause += " AND timestamp >= ?"
                    params.append(metadata_filter['start_time'])
                if 'end_time' in metadata_filter:
                    where_clause += " AND timestamp <= ?"
                    params.append(metadata_filter['end_time'])
            
            rows = self.db_manager.fetchall(
                f"SELECT id, habit_type, content, timestamp, access_count FROM habits {where_clause}",
                tuple(params)
            )
            
            if not rows:
                return []
            
            doc_count = len(rows)
            all_tokens = []
            doc_lengths = []
            df_dict = Counter()
            
            for row in rows:
                content = row[2]
                tokens = self._tokenize(content)
                all_tokens.append(tokens)
                doc_lengths.append(len(tokens))
                for token in set(tokens):
                    df_dict[token] += 1
            
            avg_doc_length = sum(doc_lengths) / doc_count if doc_count > 0 else 1
            
            results = []
            for i, row in enumerate(rows):
                memory_id, habit_type, content, timestamp, access_count = row
                bm25_score = self._calculate_bm25_score(
                    query_tokens, 
                    all_tokens[i], 
                    doc_lengths[i], 
                    avg_doc_length,
                    doc_count,
                    df_dict
                )
                
                if bm25_score > 0:
                    results.append({
                        "id": memory_id,
                        "source": "bm25",
                        "type": habit_type,
                        "content": content,
                        "score": bm25_score,
                        "timestamp": timestamp,
                        "access_count": access_count
                    })
            
            results.sort(key=lambda x: x['score'], reverse=True)
            return results[:top_k]
        
        except Exception as e:
            logger.error(f"BM25 search failed: {e}")
            return []
    
    def _metadata_filter(
        self, 
        user_id: str,
        memory_type: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Metadata filter search
        
        :param user_id: User ID
        :param memory_type: Memory type
        :param start_time: Start timestamp
        :param end_time: End timestamp
        :param limit: Number of results to return
        :return: Filtered memory list
        """
        try:
            where_clause = "WHERE user_id = ?"
            params = [user_id]
            
            if memory_type:
                where_clause += " AND habit_type = ?"
                params.append(memory_type)
            
            if start_time:
                where_clause += " AND timestamp >= ?"
                params.append(start_time)
            
            if end_time:
                where_clause += " AND timestamp <= ?"
                params.append(end_time)
            
            rows = self.db_manager.fetchall(
                f"SELECT id, habit_type, content, timestamp, access_count FROM habits {where_clause} ORDER BY timestamp DESC LIMIT ?",
                tuple(params + [limit])
            )
            
            results = []
            for row in rows:
                memory_id, habit_type, content, timestamp, access_count = row
                results.append({
                    "id": memory_id,
                    "source": "metadata_filter",
                    "type": habit_type,
                    "content": content,
                    "score": 1.0,
                    "timestamp": timestamp,
                    "access_count": access_count
                })
            
            return results
        
        except Exception as e:
            logger.error(f"Metadata filter failed: {e}")
            return []
    
    def _rrf_fusion(
        self, 
        vector_results: List[Dict[str, Any]], 
        bm25_results: List[Dict[str, Any]],
        k: int = 60
    ) -> List[Dict[str, Any]]:
        """
        RRF (Reciprocal Rank Fusion) fusion ranking
        
        :param vector_results: Vector search results
        :param bm25_results: BM25 search results
        :param k: RRF parameter
        :return: Fused result list
        """
        rrf_scores: Dict[str, float] = {}
        content_to_result: Dict[str, Dict[str, Any]] = {}
        
        for rank, result in enumerate(vector_results, 1):
            content = result.get('content', '')
            if content not in content_to_result:
                content_to_result[content] = result
            rrf_scores[content] = rrf_scores.get(content, 0) + RAG_VECTOR_WEIGHT / (k + rank)
        
        for rank, result in enumerate(bm25_results, 1):
            content = result.get('content', '')
            if content not in content_to_result:
                content_to_result[content] = result
            rrf_scores[content] = rrf_scores.get(content, 0) + RAG_BM25_WEIGHT / (k + rank)
        
        sorted_contents = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        
        fused_results = []
        for content, score in sorted_contents:
            result = content_to_result[content].copy()
            result['rrf_score'] = score
            fused_results.append(result)
        
        return fused_results
    
    def _rerank_results(
        self, 
        results: List[Dict[str, Any]], 
        top_percentage: float = RAG_TOP_PERCENTAGE
    ) -> List[Dict[str, Any]]:
        """
        Re-ranking Layer: Keep top percentage high-quality memories
        
        :param results: Fused result list
        :param top_percentage: Percentage to keep
        :return: Re-ranked result list
        """
        if not results:
            return []
        
        keep_count = max(1, int(len(results) * top_percentage))
        
        seen_contents: Set[str] = set()
        unique_results: List[Dict[str, Any]] = []
        
        for r in results:
            content = r.get('content', '')
            if content and content not in seen_contents:
                seen_contents.add(content)
                unique_results.append(r)
        
        return unique_results[:keep_count]
    
    def _three_layer_rag_search(
        self, 
        user_id: str, 
        query: str, 
        top_k: int = DEFAULT_TOP_K,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Three-layer RAG search architecture
        
        First Layer: Recall Layer - Three-way multi-path recall
        Second Layer: Fusion Layer - RRF weighted fusion ranking
        Third Layer: Re-ranking Layer - Keep top 10% high-quality memories
        
        :param user_id: User ID
        :param query: Query text
        :param top_k: Final number of results to return
        :param metadata_filter: Metadata filter conditions
        :return: Re-ranked result list
        """
        try:
            candidate_count = top_k * RAG_CANDIDATE_MULTIPLIER
            
            vector_results = self._vector_semantic_search(user_id, query, candidate_count, time.time())
            
            bm25_results = self._bm25_search(user_id, query, candidate_count, metadata_filter)
            
            metadata_results = self._metadata_filter(user_id, limit=candidate_count)
            
            all_candidates = {}
            for result in vector_results + bm25_results + metadata_results:
                content = result.get('content', '')
                if content and content not in all_candidates:
                    all_candidates[content] = result
            
            fused_results = self._rrf_fusion(vector_results, bm25_results)
            
            for result in metadata_results:
                content = result.get('content', '')
                if content not in [r.get('content', '') for r in fused_results]:
                    fused_results.append(result)
            
            reranked_results = self._rerank_results(fused_results)
            
            final_results = reranked_results[:top_k]
            
            logger.info(
                f"Three-layer RAG search completed - User: {user_id}, Query: {query[:30]}, "
                f"Vector recall: {len(vector_results)}, BM25 recall: {len(bm25_results)}, "
                f"Metadata filter: {len(metadata_results)}, Final results: {len(final_results)}"
            )
            
            return final_results
        
        except Exception as e:
            logger.error(f"Three-layer RAG search failed, degrading to basic search: {e}")
            return self._fallback_search(user_id, query, top_k)

    def save_conversation(
        self, 
        user_id: str, 
        role: str, 
        content: str, 
        file_path: Optional[str] = None, 
        tags: Optional[str] = None
    ) -> None:
        """
        Save conversation to long-term memory archive
        
        :param user_id: User ID
        :param role: Role (user/agent/system)
        :param content: Conversation content
        :param file_path: Associated file path (optional)
        :param tags: Tags (comma separated, optional)
        """
        try:
            processed_content = self._process_sensitive_content(content)
            
            timestamp = time.time()
            self.db_manager.execute(
                "INSERT INTO conversations_archive (user_id, timestamp, role, content, file_path, tags) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, timestamp, role, processed_content, file_path, tags)
            )
            self.conn.commit()
            
            logger.info(f"Conversation archived successfully - User: {user_id}, Role: {role}, Content length: {len(processed_content)}")
        
        except Exception as e:
            logger.error(f"Conversation archive failed: {e}", exc_info=True)
            raise

    def search_conversations(
        self, 
        user_id: str, 
        query: str, 
        limit: int = DEFAULT_CONVERSATION_LIMIT
    ) -> List[Dict[str, Any]]:
        """
        Search historical conversations
        
        :param user_id: User ID
        :param query: Search keyword
        :param limit: Number of results to return
        :return: Conversation list
        """
        try:
            like_pattern = f"%{query}%"
            rows = self.db_manager.fetchall(
                "SELECT timestamp, role, content, file_path, tags FROM conversations_archive "
                "WHERE user_id=? AND (content LIKE ? OR tags LIKE ?) "
                "ORDER BY timestamp DESC LIMIT ?",
                (user_id, like_pattern, like_pattern, limit)
            )
            
            results = []
            for row in rows:
                results.append({
                    "timestamp": row[0],
                    "role": row[1],
                    "content": row[2],
                    "file_path": row[3],
                    "tags": row[4]
                })
            
            logger.info(f"Conversation search completed - User: {user_id}, Query: {query[:30]}, Results: {len(results)}")
            return results
        except Exception as e:
            logger.error(f"Conversation search failed: {e}", exc_info=True)
            return []

    def archive_short_term(self, stm, hours_threshold: int = 23) -> int:
        """
        Archive short-term memory to long-term memory
        
        :param stm: Short-term memory instance
        :param hours_threshold: Records older than this number of hours will be archived
        :return: Number of archived records
        """
        try:
            cutoff = time.time() - hours_threshold * 3600
            logs = stm.query_logs_by_cutoff(cutoff)
            if not logs:
                logger.info("No short-term memory records need archiving")
                return 0
            
            try:
                import jieba.analyse
                JIEBA_AVAILABLE = True
            except ImportError:
                JIEBA_AVAILABLE = False
                logger.warning("jieba not installed, skipping keyword extraction")
            
            count = 0
            for log in logs:
                content = log.get('content', '')
                tags = ''
                
                if JIEBA_AVAILABLE and content:
                    try:
                        keywords = jieba.analyse.extract_tags(content, topK=3)
                        tags = ','.join(keywords)
                    except Exception as e:
                        logger.warning(f"Keyword extraction failed: {e}")
                
                self.save_conversation(
                    user_id=log.get('user_id', 'default'),
                    role=log.get('role', 'system'),
                    content=content,
                    file_path=None,
                    tags=tags
                )
                count += 1
            
            stm.delete_logs_older_than(cutoff)
            logger.info(f"Short-term memory archiving completed - Total archived: {count} records")
            return count
        
        except Exception as e:
            logger.error(f"Short-term memory archiving failed: {e}", exc_info=True)
            return 0

    def save_pending(self, user_id: str, item: Dict[str, Any]) -> None:
        """Save pending confirmation item"""
        try:
            required_fields = ['type', 'value', 'masked', 'level']
            for field in required_fields:
                if field not in item:
                    raise ValueError(f"Pending item missing required field: {field}")
            
            self.db_manager.execute(
                "INSERT OR REPLACE INTO pending_confirm (user_id, item_type, item_value, item_masked, level, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, item['type'], item['value'], item['masked'], item['level'], time.time())
            )
            self.conn.commit()
            logger.info(f"Pending item saved successfully - User: {user_id}, Type: {item['type']}")
        
        except Exception as e:
            logger.error(f"Pending item save failed: {e}", exc_info=True)
            raise

    def get_pending(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user pending confirmation item"""
        try:
            row = self.db_manager.fetchone(
                "SELECT item_type, item_value, item_masked, level FROM pending_confirm WHERE user_id=?",
                (user_id,)
            )
            if row:
                return {
                    'type': row[0],
                    'value': row[1],
                    'masked': row[2],
                    'level': row[3]
                }
            return None
        except Exception as e:
            logger.error(f"Failed to get pending item: {e}")
            return None

    def clear_pending(self, user_id: str) -> None:
        """Clear user pending confirmation item"""
        try:
            self.db_manager.execute("DELETE FROM pending_confirm WHERE user_id=?", (user_id,))
            self.conn.commit()
            logger.info(f"Pending item cleared - User: {user_id}")
        except Exception as e:
            logger.error(f"Failed to clear pending item: {e}", exc_info=True)
            raise

    def _is_duplicate_memory(self, user_id: str, content: str) -> bool:
        """Check if memory is duplicate"""
        try:
            if self.embedder and self.collection:
                query_emb = self.embedder.encode(content).tolist()
                results = self.collection.query(
                    query_embeddings=[query_emb],
                    n_results=5,
                    where={"user_id": user_id}
                )
                if results.get('distances') and results['distances'][0]:
                    min_distance = min(results['distances'][0])
                    similarity = 1.0 - min_distance
                    return similarity > MEMORY_ARCHIVE_THRESHOLD
            
            rows = self.db_manager.fetchall(
                "SELECT content FROM habits WHERE user_id=? ORDER BY timestamp DESC LIMIT 10",
                (user_id,)
            )
            recent_memories = [row[0] for row in rows]
            for memory in recent_memories:
                if self._keyword_similarity(content, memory) > MEMORY_ARCHIVE_THRESHOLD:
                    return True
            
            return False
        except Exception as e:
            logger.warning(f"Duplicate check failed, skipping deduplication: {e}")
            return False

    def _keyword_similarity(self, text1: str, text2: str) -> float:
        """Calculate keyword similarity"""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        if not words1 or not words2:
            return 0.0
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        return len(intersection) / len(union)

    def add_preference_mention(self, user_id: str, content: str, expression: str) -> None:
        """Record preference mention"""
        try:
            now = time.time()
            date_str = datetime.fromtimestamp(now).strftime('%Y%m%d')
            
            row = self.db_manager.fetchone(
                "SELECT id, mention_dates, expressions FROM preference_temp WHERE user_id=? AND content=?",
                (user_id, content)
            )
            
            if row:
                pid, dates_json, exp_json = row
                try:
                    dates = json.loads(dates_json) if dates_json else []
                    exps = json.loads(exp_json) if exp_json else []
                except Exception:
                    dates, exps = [], []
                
                if date_str not in dates:
                    dates.append(date_str)
                if expression not in exps:
                    exps.append(expression)
                
                self.db_manager.execute(
                    "UPDATE preference_temp SET mention_dates=?, expressions=?, updated_at=? WHERE id=?",
                    (json.dumps(dates), json.dumps(exps), now, pid)
                )
            else:
                self.db_manager.execute(
                    "INSERT INTO preference_temp (user_id, content, expressions, mention_dates, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (user_id, content, json.dumps([expression]), json.dumps([date_str]), now, now)
                )
            
            self.conn.commit()
            logger.debug(f"Preference mention recorded successfully - User: {user_id}, Content: {content[:30]}")
        
        except Exception as e:
            logger.error(f"Failed to record preference mention: {e}", exc_info=True)
            raise

    def check_and_promote_preferences(
        self, 
        user_id: str, 
        user_data: Optional[Any] = None
    ) -> List[str]:
        """
        Check and promote temporary preferences to permanent habits
        
        :param user_id: User ID
        :param user_data: User data object (contains preference config)
        :return: List of promoted preferences
        """
        try:
            if user_data and hasattr(user_data, 'get_preference_learning_config'):
                config = user_data.get_preference_learning_config()
                min_mentions = config.get('min_mentions', DEFAULT_PREFERENCE_MIN_MENTIONS)
                min_interval_days = config.get('min_interval_days', DEFAULT_PREFERENCE_MIN_INTERVAL_DAYS)
            else:
                min_mentions = DEFAULT_PREFERENCE_MIN_MENTIONS
                min_interval_days = DEFAULT_PREFERENCE_MIN_INTERVAL_DAYS
            
            promoted = []
            cutoff_date = (datetime.now() - timedelta(days=DEFAULT_CUTOFF_DAYS)).strftime('%Y%m%d')
            
            rows = self.db_manager.fetchall(
                "SELECT id, content, mention_dates FROM preference_temp WHERE user_id=?",
                (user_id,)
            )
            
            for row in rows:
                pid, content, dates_json = row
                try:
                    dates = json.loads(dates_json) if dates_json else []
                except Exception:
                    continue
                
                recent_dates = [d for d in dates if d >= cutoff_date]
                if len(recent_dates) < min_mentions:
                    continue
                
                unique_dates = set(recent_dates)
                if len(unique_dates) < 2:
                    continue
                
                date_objs = [datetime.strptime(d, '%Y%m%d') for d in recent_dates]
                date_span = (max(date_objs) - min(date_objs)).days
                if date_span < min_interval_days:
                    continue
                
                self.save_habit(user_id, "preference", content)
                promoted.append(content)
                
                self.db_manager.execute("DELETE FROM preference_temp WHERE id=?", (pid,))
            
            self.conn.commit()
            logger.info(f"Preference promotion completed - User: {user_id}, Promoted count: {len(promoted)}")
            return promoted
        
        except Exception as e:
            logger.error(f"Preference promotion failed: {e}", exc_info=True)
            return []

    def _check_auto_archive(self, user_id: str) -> None:
        """Auto archive check (reserved interface)"""
        pass

    def update_access_count(self, user_id: str, content_prefix: str) -> None:
        """Update memory access count"""
        try:
            self.db_manager.execute(
                "UPDATE habits SET access_count = access_count + 1 WHERE user_id=? AND content LIKE ?",
                (user_id, f"{content_prefix}%")
            )
            self.conn.commit()
        except Exception as e:
            logger.warning(f"Failed to update access count: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Get current status (for monitoring/debugging)"""
        try:
            table_counts = {}
            for table in ['habits', 'task_logs', 'conversations_archive', 'pending_confirm', 'preference_temp']:
                row = self.db_manager.fetchone(f"SELECT COUNT(*) FROM {table} WHERE user_id=?", (self.user_id,))
                table_counts[table] = row[0] if row else 0
            
            return {
                "user_id": self.user_id,
                "data_dir": str(self.data_dir),
                "sqlite_path": str(self.sqlite_path),
                "chromadb_available": CHROMADB_AVAILABLE and self.chroma_client is not None,
                "embedder_available": self.embedder is not None,
                "table_counts": table_counts,
                "sensitive_check_enabled": ENABLE_SENSITIVE_CHECK,
                "sensitive_action": SENSITIVE_ACTION
            }
        except Exception as e:
            logger.error(f"Failed to get status: {e}")
            return {"error": str(e)}

    def close(self) -> None:
        """Safely close resources"""
        try:
            if hasattr(self, 'conn') and self.conn:
                self.conn.commit()
                self.conn.close()
            logger.info(f"Resources closed - User: {self.user_id}")
        except Exception as e:
            logger.error(f"Failed to close resources: {e}")

    def __del__(self):
        """Destructor"""
        self.close()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
        if exc_type:
            logger.error(f"Long-term memory manager exited with exception: {exc_type.__name__}: {exc_val}")


def create_long_term_memory(user_id: str = 'default', data_dir: Optional[Path] = None) -> LongTermMemory:
    """Quickly create long-term memory instance"""
    return LongTermMemory(user_id=user_id, data_dir=data_dir)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    with LongTermMemory("test_user_001") as ltm:
        ltm.save_habit("test_user_001", "test", "Principles and applications of quantum entanglement")
        
        results = ltm.search_memory("test_user_001", "quantum entanglement")
        print(f"\nSearch results: {results}")
        
        ltm.save_conversation("test_user_001", "user", "Hello, I want to learn about quantum mechanics", tags="quantum mechanics,learning")
        
        conv_results = ltm.search_conversations("test_user_001", "quantum mechanics")
        print(f"\nConversation search results: {conv_results}")
        
        ltm.add_preference_mention("test_user_001", "Likes quantum physics", "interested")
        
        status = ltm.get_status()
        print(f"\nManager status: {status}")
