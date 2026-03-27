#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Memory Handler: Integrates short-term text memory (SQLite) + long-term vector memory (ChromaDB)
Provides unified memory add/delete/query/recall interfaces
"""
import os
import uuid
import logging
import sqlite3
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from core.capsules.capsule_manager import CapsuleManager
from sentence_transformers import SentenceTransformer

from core.memory.vector_memory import VectorMemory

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "short_term_db_name": "short_term_memory.db",
    "vector_collection_name": "agent_exploration_memory",
    "similarity_threshold": 0.8,
    "default_top_k": 5,
    "short_term_expire_days": 7
}

class ShortTermMemory:
    """Short-term text memory: Based on SQLite, stores recent interactions/operation logs/temporary memories"""
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = self._init_db()
        self._init_tables()

    def _init_db(self) -> sqlite3.Connection:
        """Initialize database connection (supports auto-reconnect)"""
        try:
            conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=10
            )
            conn.execute("PRAGMA journal_mode=WAL")
            return conn
        except sqlite3.Error as e:
            logger.error(f"Failed to connect to short-term DB: {e}")
            raise RuntimeError(f"ShortTermMemory init failed: {e}") from e

    def _init_tables(self):
        """Initialize short-term memory tables (interaction records + logs)"""
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                content TEXT NOT NULL,
                role TEXT NOT NULL,
                create_time REAL NOT NULL,
                tags TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                timestamp REAL,
                environment TEXT,
                action TEXT,
                result TEXT,
                success_rate REAL,
                trace_id TEXT
            )
        """)
        self.conn.commit()

    def add_interaction(
        self,
        user_id: str,
        content: str,
        role: str,
        tags: Optional[List[str]] = None
    ) -> str:
        """Add an interaction memory (returns unique ID)"""
        mem_id = f"inter_{user_id}_{uuid.uuid4().hex[:8]}"
        tags_str = ",".join(tags) if tags else ""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO interactions 
                (id, user_id, content, role, create_time, tags)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (mem_id, user_id, content, role, time.time(), tags_str))
            self.conn.commit()
            logger.debug(f"Short-term interaction added (ID: {mem_id}, user: {user_id})")
            return mem_id
        except sqlite3.Error as e:
            logger.error(f"Failed to add interaction: {e}")
            return ""

    def query_interactions(
        self,
        user_id: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Query user's short-term interaction memories"""
        cursor = self.conn.cursor()
        query = "SELECT * FROM interactions WHERE user_id = ?"
        params = [user_id]
        
        if start_time:
            query += " AND create_time >= ?"
            params.append(start_time)
        if end_time:
            query += " AND create_time <= ?"
            params.append(end_time)
        
        query += " ORDER BY create_time DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        columns = [desc[0] for desc in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        for res in results:
            res["tags"] = res["tags"].split(",") if res["tags"] else []
        return results

    def insert_log(self, log_dict: Dict[str, Any]):
        """Insert log (compatible with Logger class)"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO logs 
                (timestamp, environment, action, result, success_rate, trace_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                log_dict["timestamp"],
                log_dict["environment"],
                log_dict["action"],
                log_dict["result"],
                log_dict["success_rate"],
                log_dict.get("trace_id", "")
            ))
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to insert log: {e}")

    def query_logs(self, start_time: float, end_time: float) -> List[Dict[str, Any]]:
        """Query logs within specified time range (compatible with Logger class)"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT timestamp, environment, action, result, success_rate 
            FROM logs WHERE timestamp >= ? AND timestamp <= ?
        """, (start_time, end_time))
        columns = ["timestamp", "environment", "action", "result", "success_rate"]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def clean_expired(self, expire_days: int = DEFAULT_CONFIG["short_term_expire_days"]):
        """Clean up expired short-term memories"""
        cutoff = time.time() - expire_days * 24 * 3600
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM interactions WHERE create_time < ?", (cutoff,))
            del_inter = cursor.rowcount
            cursor.execute("DELETE FROM logs WHERE timestamp < ?", (cutoff,))
            del_logs = cursor.rowcount
            self.conn.commit()
            logger.info(f"Cleaned expired short-term memory: {del_inter} interactions, {del_logs} logs")
        except sqlite3.Error as e:
            logger.error(f"Failed to clean expired memory: {e}")

class MemoryHandler:
    def __init__(self, data_dir: str = "./data"):
        self.data_dir = Path(data_dir)
        self.short_term = ShortTermMemory(str(self.data_dir / "short_term.db"))
        self.long_term = VectorMemory(persist_directory=str(self.data_dir / "vector_store"))
        
        self.embed_model = SentenceTransformer("all-MiniLM-L6-v2")
        self.capsule_manager = CapsuleManager(
            user_id="default",
            data_dir=self.data_dir / "capsules",
            embed_model=self.embed_model
        )
    
    def close(self):
        pass

    def save_experience_capsule(self, problem: str, solution: str, capsule_type: str = "experience", tags: List[str] = None) -> int:
        """Save agent experience capsule"""
        return self.capsule_manager.add_capsule(problem, solution, capsule_type, tags)

    def save_error_capsule(self, error_msg: str, error_trace: str, module: str) -> int:
        """Save error capsule"""
        return self.capsule_manager.add_error_log_capsule(error_msg, error_trace, module)

    def recall_similar_capsules(self, query: str, capsule_type: str = None, top_k: int = 5) -> List[Dict]:
        """Recall similar capsules"""
        return self.capsule_manager.semantic_search_capsules(query, top_k, capsule_type)

    def save_short_term_memory(
        self,
        user_id: str,
        content: str,
        role: str = "system",
        tags: Optional[List[str]] = None
    ) -> str:
        """Save short-term memory (shortcut interface)"""
        return self.short_term.add_interaction(user_id, content, role, tags)

    def get_short_term_memory(
        self,
        user_id: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get user's recent short-term memories"""
        start_time = time.time() - DEFAULT_CONFIG["short_term_expire_days"] * 24 * 3600
        return self.short_term.query_interactions(user_id, start_time=start_time, limit=limit)

    def save_long_term_memory(
        self,
        user_id: str,
        content: str,
        topic: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Save long-term vector memory (auto-generate ID + supplement metadata)"""
        mem_id = f"long_{user_id}_{uuid.uuid4().hex[:8]}"
        metadata = metadata or {}
        metadata["user_id"] = user_id
        metadata["create_time"] = time.time()
        metadata["topic"] = topic
        
        content_summary = content[:200] + "..." if len(content) > 200 else content
        
        success = self.long_term.add_memory(
            doc_id=mem_id,
            topic=topic,
            content_summary=content_summary,
            metadata=metadata
        )
        
        if success:
            logger.info(f"Long-term memory saved (ID: {mem_id}, user: {user_id})")
            return mem_id
        else:
            logger.error(f"Failed to save long-term memory (user: {user_id})")
            return ""

    def recall_similar_memories(
        self,
        user_id: str,
        query_text: str,
        n_results: int = DEFAULT_CONFIG["default_top_k"],
        threshold: float = DEFAULT_CONFIG["similarity_threshold"]
    ) -> List[Dict[str, Any]]:
        """Recall user's similar long-term memories"""
        similar_items = self.long_term.find_similar(query_text, n_results, threshold)
        user_memories = [
            item for item in similar_items 
            if item["metadata"].get("user_id") == user_id
        ]
        logger.debug(f"Recalled {len(user_memories)} similar memories for user {user_id}")
        return user_memories

    def clean_expired_memory(self):
        """Clean up expired memories (short-term + optional long-term cleanup)"""
        self.short_term.clean_expired()

    def get_memory_stats(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Get memory statistics"""
        if user_id:
            cursor = self.short_term.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM interactions WHERE user_id = ?", (user_id,))
            short_term_count = cursor.fetchone()[0]
        else:
            cursor = self.short_term.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM interactions")
            short_term_count = cursor.fetchone()[0]
        
        long_term_count = self.long_term.get_total_count()
        
        return {
            "short_term_count": short_term_count,
            "long_term_count": long_term_count,
            "update_time": time.time()
        }

    def close(self):
        """Close database connections, release resources"""
        self.short_term.conn.close()
        self.long_term.close()
        logger.info("MemoryHandler resources released")

if __name__ == "__main__":
    mem_handler = MemoryHandler(data_dir="./test_data")
    
    user_id = "test_user_001"
    mem_handler.save_short_term_memory(
        user_id=user_id,
        content="User asked about Beijing weather",
        role="user",
        tags=["weather_query", "short_term"]
    )
    
    long_mem_id = mem_handler.save_long_term_memory(
        user_id=user_id,
        content="Beijing's climate belongs to warm temperate semi-humid continental monsoon climate, with hot and rainy summers, cold and dry winters",
        topic="Beijing climate characteristics",
        metadata={"type": "knowledge", "source": "encyclopedia"}
    )
    
    similar_mems = mem_handler.recall_similar_memories(
        user_id=user_id,
        query_text="Beijing weather characteristics",
        n_results=3
    )
    print("Similar memory recall results:")
    for mem in similar_mems:
        print(f"- Similarity: {mem['similarity']:.2f} | Content: {mem['content']}")
    
    stats = mem_handler.get_memory_stats(user_id=user_id)
    print("\nMemory statistics:", stats)
    
    mem_handler.close()
