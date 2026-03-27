#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Memory Manager
================
Core Features:
- Short-term Memory (STM) and Long-term Memory (LTM) layered storage
- Automatic sensitive information detection and masking
- Automatic archiving based on time threshold (7-day rule)
- Keyword-based short-term memory retrieval
- Secure database resource management

Design Features:
- Complete parameter validation and exception handling
- Structured log output for monitoring and debugging
- Context manager support for automatic resource release
- Auto-commit database operations to prevent data loss
- Configurable threshold constants for strategy adjustment
- Comprehensive type annotations and documentation
"""

import time
import logging
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any
from infra.db_manager import get_db_manager
from utils.sensitive_detector import scan_text

logger = logging.getLogger(__name__)

ARCHIVE_THRESHOLD_DAYS = 7
ARCHIVE_BATCH_SIZE = 100

DEFAULT_DATA_DIR = Path("./data")
DEFAULT_MEMORY_TYPE = "default"
DEFAULT_SOURCE = "user"

DEFAULT_QUERY_LIMIT = 10
MAX_QUERY_LIMIT = 100

FALLBACK_SAFE_CONTENT = ""


class MemoryManager:
    """
    Memory Manager: Short-term + Long-term memory layered storage, auto-masking and archiving
    
    Core Flow:
    1. Auto-detect and mask sensitive information when saving memories
    2. New memories are prioritized for storage in short-term memory (STM)
    3. Periodically check and archive short-term memories exceeding threshold to long-term memory (LTM)
    4. Support keyword-based short-term memory retrieval
    """
    
    def __init__(self, user_id: str = 'default', data_dir: Optional[Path] = None):
        """
        Initialize Memory Manager
        
        :param user_id: User unique identifier for data isolation
        :param data_dir: Data storage directory (None uses default path: ./data/{user_id})
        :raises Exception: Throws exception when database initialization fails
        """
        try:
            self.user_id = user_id.strip()
            if not self.user_id:
                raise ValueError("user_id cannot be empty")
            
            self.data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR / self.user_id
            self.data_dir.mkdir(exist_ok=True, parents=True)
            logger.info(f"Initializing Memory Manager - User: {self.user_id}, Data Directory: {self.data_dir}")
            
            self.stm_path = self.data_dir / 'stm.db'
            self.ltm_path = self.data_dir / 'ltm.db'
            
            self.stm_db = get_db_manager(str(self.stm_path))
            self.ltm_db = get_db_manager(str(self.ltm_path))
            
            self._init_tables()
            
            self._check_archive_trigger()
            
        except Exception as e:
            logger.error(f"Memory Manager initialization failed - User: {self.user_id}, Error: {e}", exc_info=True)
            self.close()
            raise
    
    def _init_tables(self) -> None:
        """Initialize database table structure (idempotent operation, compatible with existing tables)"""
        try:
            self.stm_db.execute('''
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    memory_type TEXT NOT NULL DEFAULT 'default',
                    source TEXT NOT NULL DEFAULT 'user',
                    created_at REAL NOT NULL,
                    access_count INTEGER NOT NULL DEFAULT 0
                )
            ''')

            self.ltm_db.execute('''
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    memory_type TEXT NOT NULL DEFAULT 'default',
                    source TEXT NOT NULL DEFAULT 'user',
                    created_at REAL NOT NULL,
                    archived_at REAL NOT NULL
                )
            ''')

            logger.debug("Database table structure initialization completed")
            
        except Exception as e:
            logger.error(f"Table structure initialization failed - Error: {e}", exc_info=True)
            raise
    
    def save_memory(
        self, 
        content: str, 
        memory_type: str = DEFAULT_MEMORY_TYPE, 
        source: str = DEFAULT_SOURCE
    ) -> int:
        """
        Save memory to short-term storage (auto-masking, check archive after saving)
        
        :param content: Memory content (will be auto-masked)
        :param memory_type: Memory type (e.g., user_input, system_generated, preference, etc.)
        :param source: Memory source (e.g., user, api, manual, etc.)
        :return: ID of the newly added memory
        :raises Exception: Throws exception when save fails
        """
        try:
            content = str(content).strip() if content is not None else ""
            memory_type = str(memory_type).strip() if memory_type is not None else DEFAULT_MEMORY_TYPE
            source = str(source).strip() if source is not None else DEFAULT_SOURCE
            
            try:
                scan_result = scan_text(content)
                safe_content = scan_result.masked_text if scan_result else FALLBACK_SAFE_CONTENT
                if scan_result and scan_result.is_sensitive:
                    logger.warning(
                        f"Sensitive information detected and masked - User: {self.user_id}, "
                        f"Original length: {len(content)}, Masked length: {len(safe_content)}"
                    )
            except Exception as e:
                logger.error(f"Sensitive detection failed, using original content - Error: {e}")
                safe_content = content
            
            created_at = float(time.time())
            cursor = self.stm_db.execute(
                '''INSERT INTO memories 
                   (content, memory_type, source, created_at) 
                   VALUES (?, ?, ?, ?)''',
                (safe_content, memory_type, source, created_at)
            )

            mem_id = cursor.lastrowid
            
            self._check_archive_trigger()
            
            logger.debug(
                f"Memory saved successfully - User: {self.user_id}, ID: {mem_id}, "
                f"Type: {memory_type}, Source: {source}, Content length: {len(safe_content)}"
            )
            return mem_id
            
        except Exception as e:
            logger.error(
                f"Memory save failed - User: {self.user_id}, Content length: {len(str(content))}, Error: {e}",
                exc_info=True
            )
            raise
    
    def query_memory(
        self, 
        keyword: str, 
        limit: int = DEFAULT_QUERY_LIMIT, 
        update_access_count: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Keyword-based short-term memory retrieval (supports fuzzy matching)
        
        :param keyword: Search keyword (empty string returns latest limit records)
        :param limit: Number of results to return (max MAX_QUERY_LIMIT)
        :param update_access_count: Whether to update memory access count
        :return: Structured memory list, each containing id/content/memory_type/source/created_at
        """
        try:
            keyword = str(keyword).strip() if keyword is not None else ""
            limit = min(int(limit), MAX_QUERY_LIMIT)
            limit = max(limit, 1)
            
            if keyword:
                query_sql = '''
                    SELECT id, content, memory_type, source, created_at 
                    FROM memories 
                    WHERE content LIKE ? 
                    ORDER BY created_at DESC 
                    LIMIT ?
                '''
                params = (f'%{keyword}%', limit)
                logger.debug(f"Executing keyword search - User: {self.user_id}, Keyword: {keyword}, Limit: {limit}")
            else:
                query_sql = '''
                    SELECT id, content, memory_type, source, created_at 
                    FROM memories 
                    ORDER BY created_at DESC 
                    LIMIT ?
                '''
                params = (limit,)
                logger.debug(f"Executing latest records search - User: {self.user_id}, Limit: {limit}")
            
            rows = self.stm_db.fetchall(query_sql, params)
            
            results = []
            for row in rows:
                result = {
                    'id': row[0],
                    'content': row[1],
                    'memory_type': row[2],
                    'source': row[3],
                    'created_at': row[4]
                }
                results.append(result)
                
                if update_access_count:
                    self.stm_db.execute(
                        'UPDATE memories SET access_count = access_count + 1 WHERE id = ?',
                        (row[0],)
                    )
            
            logger.info(
                f"Memory search completed - User: {self.user_id}, Keyword: {keyword}, "
                f"Matches: {len(results)}, Limit: {limit}"
            )
            return results
            
        except Exception as e:
            logger.error(
                f"Memory search failed - User: {self.user_id}, Keyword: {keyword}, Error: {e}",
                exc_info=True
            )
            return []
    
    def query_long_term_memory(self, keyword: str, limit: int = DEFAULT_QUERY_LIMIT) -> List[Dict[str, Any]]:
        """
        Extended feature: Keyword-based long-term memory retrieval
        
        :param keyword: Search keyword
        :param limit: Number of results to return
        :return: Structured long-term memory list
        """
        try:
            keyword = str(keyword).strip() if keyword is not None else ""
            limit = min(int(limit), MAX_QUERY_LIMIT)
            
            if keyword:
                rows = self.ltm_db.fetchall(
                    '''SELECT id, content, memory_type, source, created_at, archived_at 
                       FROM memories 
                       WHERE content LIKE ? 
                       ORDER BY archived_at DESC 
                       LIMIT ?''',
                    (f'%{keyword}%', limit)
                )
            else:
                rows = self.ltm_db.fetchall(
                    '''SELECT id, content, memory_type, source, created_at, archived_at 
                       FROM memories 
                       ORDER BY archived_at DESC 
                       LIMIT ?''',
                    (limit,)
                )
            
            results = []
            for row in rows:
                results.append({
                    'id': row[0],
                    'content': row[1],
                    'memory_type': row[2],
                    'source': row[3],
                    'created_at': row[4],
                    'archived_at': row[5]
                })
            
            logger.info(
                f"Long-term memory search completed - User: {self.user_id}, Keyword: {keyword}, "
                f"Matches: {len(results)}, Limit: {limit}"
            )
            return results
            
        except Exception as e:
            logger.error(f"Long-term memory search failed - Error: {e}", exc_info=True)
            return []
    
    def _check_archive_trigger(self) -> None:
        """Check and trigger archiving: migrate short-term memories exceeding threshold to long-term storage"""
        try:
            threshold = time.time() - (ARCHIVE_THRESHOLD_DAYS * 24 * 3600)
            
            rows = self.stm_db.fetchall(
                '''SELECT id, content, memory_type, source, created_at 
                   FROM memories 
                   WHERE created_at < ? 
                   LIMIT ?''',
                (threshold, ARCHIVE_BATCH_SIZE)
            )
            
            if not rows:
                logger.debug(f"No memories to archive - User: {self.user_id}, Threshold: {threshold}")
                return
            
            archived_count = self._archive_memories(rows)
            
            logger.info(
                f"Archiving completed - User: {self.user_id}, Archived: {archived_count}, "
                f"Remaining to archive: {len(rows) - archived_count}"
            )
            
        except Exception as e:
            logger.error(f"Archive check failed - Error: {e}", exc_info=True)
    
    def _archive_memories(self, rows: List[Tuple]) -> int:
        """
        Batch archive memories (from short-term to long-term)
        
        :param rows: List of memory records to archive
        :return: Number of successfully archived records
        """
        archived_count = 0
        archived_at = float(time.time())
        
        try:
            for row in rows:
                try:
                    mem_id, content, mem_type, source, created_at = row
                    
                    self.ltm_db.execute(
                        '''INSERT INTO memories 
                           (content, memory_type, source, created_at, archived_at) 
                           VALUES (?, ?, ?, ?, ?)''',
                        (str(content), str(mem_type), str(source), float(created_at), archived_at)
                    )
                    
                    self.stm_db.execute('DELETE FROM memories WHERE id = ?', (mem_id,))
                    
                    archived_count += 1
                    
                except Exception as e:
                    logger.error(f"Single memory archive failed - ID: {row[0] if row else 'unknown'}, Error: {e}")
                    continue

            return archived_count
            
        except Exception as e:
            logger.error(f"Batch archive failed - Error: {e}", exc_info=True)
            self.ltm_db.rollback()
            self.stm_db.rollback()
            return archived_count
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """
        Extended feature: Get memory statistics
        
        :return: Statistics including short-term/long-term memory counts, archive threshold, etc.
        """
        try:
            stm_count = self.stm_db.fetchone('SELECT COUNT(*) FROM memories')[0]
            ltm_count = self.ltm_db.fetchone('SELECT COUNT(*) FROM memories')[0]
            threshold = time.time() - (ARCHIVE_THRESHOLD_DAYS * 24 * 3600)
            pending_archive = self.stm_db.fetchone(
                'SELECT COUNT(*) FROM memories WHERE created_at < ?',
                (threshold,)
            )[0]
            
            return {
                'user_id': self.user_id,
                'short_term_count': stm_count,
                'long_term_count': ltm_count,
                'pending_archive_count': pending_archive,
                'archive_threshold_days': ARCHIVE_THRESHOLD_DAYS,
                'data_dir': str(self.data_dir)
            }
            
        except Exception as e:
            logger.error(f"Failed to get statistics - Error: {e}", exc_info=True)
            return {'error': str(e)}
    
    def close(self) -> None:
        """Safely close database connections"""
        try:
            if hasattr(self, 'stm_db') and hasattr(self.stm_db, 'close'):
                self.stm_db.close()
                logger.debug(f"Short-term memory database connection closed - User: {self.user_id}")
            
            if hasattr(self, 'ltm_db') and hasattr(self.ltm_db, 'close'):
                self.ltm_db.close()
                logger.debug(f"Long-term memory database connection closed - User: {self.user_id}")
                
        except Exception as e:
            logger.error(f"Failed to close database connections - Error: {e}", exc_info=True)
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit (auto-close connections)"""
        self.close()
        if exc_type:
            logger.error(
                f"Memory Manager abnormal exit - User: {self.user_id}, "
                f"Exception type: {exc_type.__name__}, Message: {exc_val}"
            )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    class MockDBManager:
        """Mock Database Manager (for testing)"""
        def __init__(self, path):
            self.path = path
            self.conn = None
            self.cursor = None
        def execute(self, sql, params=()):
            class MockCursor:
                lastrowid = 1
            return MockCursor()
        def fetchall(self, sql, params=()):
            return [(1, "Test content", "default", "user", time.time())]
        def fetchone(self, sql, params=()):
            return (0,)
        def commit(self): pass
        def rollback(self): pass
        def close(self): pass
    
    class MockScanResult:
        """Mock Sensitive Detection Result (for testing)"""
        def __init__(self):
            self.is_sensitive = False
            self.masked_text = ""
    
    def get_db_manager(path):
        return MockDBManager(path)
    
    def scan_text(content):
        result = MockScanResult()
        result.masked_text = content
        return result
    
    with MemoryManager("test_user_001") as mm:
        mem_id = mm.save_memory("My email password is 123456", "user_input", "test")
        print(f"Saved memory ID: {mem_id}")
        
        results = mm.query_memory("password", limit=5)
        print(f"Query results: {results}")
        
        stats = mm.get_memory_stats()
        print(f"Statistics: {stats}")
        
        ltm_results = mm.query_long_term_memory("password")
        print(f"Long-term memory query results: {ltm_results}")
