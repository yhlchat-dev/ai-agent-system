#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Memory Updater
================
Core Features:
- Batch write new facts to long-term memory database (SQLite)
- Optional duplicate checking to avoid storing redundant data
- Complete parameter validation and exception handling
- Structured operation result return
- Secure database connection management

Design Features:
- Configurable constants (database path, deduplication rules)
- Detailed log output for monitoring and debugging
- Compatible with existing interfaces, no breaking changes
- Complete type annotations and documentation
- Support for atomic batch operations (optional)
"""

import sqlite3
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_LONG_TERM_DB = Path("./data/long_term.db")
DB_TIMEOUT = 30

ENABLE_DUPLICATE_CHECK = True
DUPLICATE_CHECK_FIELDS = ("user_id", "habit_type", "content")
DUPLICATE_TIME_WINDOW = 0

BATCH_COMMIT_SIZE = 50
DEFAULT_HABIT_TYPE = "general"

RESULT_SUCCESS = "success"
RESULT_PARTIAL = "partial"
RESULT_FAILED = "failed"


def update_memory(
    new_facts: List[Dict[str, Any]],
    source: str,
    timestamp: Optional[float] = None,
    user_id: str = 'default',
    enable_duplicate_check: bool = ENABLE_DUPLICATE_CHECK,
    long_term_db: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Update long-term memory database (write to habits table), support batch operations and optional deduplication
    
    :param new_facts: List of facts, each fact is a dict, must contain 'value' key, optional 'type' key
    :param source: Information source (e.g. "user_conversation", "patrol_correction", "manual_input")
    :param timestamp: Timestamp (default current time)
    :param user_id: User ID (for data isolation)
    :param enable_duplicate_check: Whether to enable duplicate checking (override global config)
    :param long_term_db: Custom database path (override global config)
    :return: Structured operation result dict:
             - status: success/partial/failed (overall status)
             - success: Whether completely successful (no errors)
             - updated_count: Number of successful inserts
             - skipped_count: Number skipped due to duplicates
             - errors: List of error messages
             - total_facts: Total number of input facts
    :raises TypeError: Input parameter type does not meet requirements
    :raises ValueError: Input parameter value is invalid
    """
    try:
        if not isinstance(new_facts, list):
            raise TypeError(f"new_facts must be list type, got: {type(new_facts)}")
        if not isinstance(source, str) or not source.strip():
            raise ValueError("source must be non-empty string")
        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("user_id must be non-empty string")
        
        if timestamp is None:
            timestamp = float(time.time())
        else:
            timestamp = float(timestamp)
        
        db_path = Path(long_term_db) if long_term_db else DEFAULT_LONG_TERM_DB
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        validated_facts = []
        for idx, fact in enumerate(new_facts):
            if not isinstance(fact, dict):
                logger.warning(f"Ignoring invalid fact[{idx}]: non-dict type - {fact}")
                continue
            
            fact_value = fact.get("value")
            if fact_value is None or not str(fact_value).strip():
                logger.warning(f"Ignoring invalid fact[{idx}]: missing or empty value field - {fact}")
                continue
            
            validated_fact = {
                "type": fact.get("type", DEFAULT_HABIT_TYPE).strip(),
                "value": str(fact_value).strip()
            }
            validated_facts.append(validated_fact)
        
        total_facts = len(new_facts)
        valid_facts_count = len(validated_facts)
        if valid_facts_count == 0:
            logger.warning(f"No valid facts to insert - User: {user_id}, Original count: {total_facts}")
            return {
                "status": RESULT_FAILED,
                "success": False,
                "updated_count": 0,
                "skipped_count": 0,
                "errors": ["No valid fact data"],
                "total_facts": total_facts
            }
        
        conn: Optional[sqlite3.Connection] = None
        cursor: Optional[sqlite3.Cursor] = None
        updated_count = 0
        skipped_count = 0
        errors = []
        
        try:
            conn = sqlite3.connect(str(db_path), timeout=DB_TIMEOUT)
            cursor = conn.cursor()
            logger.debug(f"Successfully connected to database - Path: {db_path}, User: {user_id}")
            
            _init_habits_table(cursor)
            conn.commit()
            
            for idx, fact in enumerate(validated_facts):
                try:
                    habit_type = fact["type"]
                    content = fact["value"]
                    
                    if enable_duplicate_check and _is_duplicate(
                        cursor, user_id, habit_type, content, timestamp
                    ):
                        skipped_count += 1
                        logger.debug(
                            f"Skipping duplicate fact[{idx}] - User: {user_id}, "
                            f"Type: {habit_type}, Content: {content[:50]}..."
                        )
                        continue
                    
                    cursor.execute(
                        """INSERT INTO habits 
                           (user_id, habit_type, content, timestamp, source) 
                           VALUES (?, ?, ?, ?, ?)""",
                        (user_id, habit_type, content, timestamp, source.strip())
                    )
                    updated_count += 1
                    
                    if (updated_count + skipped_count) % BATCH_COMMIT_SIZE == 0:
                        conn.commit()
                        logger.debug(f"Batch commit completed - Processed: {updated_count + skipped_count}/{valid_facts_count}")
                
                except Exception as e:
                    error_msg = f"Failed to insert fact[{idx}] - {fact}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            conn.commit()
            logger.info(
                f"Memory update completed - User: {user_id}, Source: {source}, "
                f"Total valid facts: {valid_facts_count}, Successfully inserted: {updated_count}, "
                f"Skipped duplicates: {skipped_count}, Errors: {len(errors)}"
            )
        
        except sqlite3.Error as e:
            error_msg = f"Database operation failed - Path: {db_path}, Error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            errors.append(error_msg)
            if conn:
                conn.rollback()
        
        except Exception as e:
            error_msg = f"Memory update process exception - Error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            errors.append(error_msg)
        
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
            logger.debug(f"Database connection closed - Path: {db_path}")
        
        if len(errors) == 0:
            status = RESULT_SUCCESS
            success = True
        elif updated_count > 0:
            status = RESULT_PARTIAL
            success = False
        else:
            status = RESULT_FAILED
            success = False
        
        return {
            "status": status,
            "success": success,
            "updated_count": updated_count,
            "skipped_count": skipped_count,
            "errors": errors,
            "total_facts": total_facts,
            "valid_facts_count": valid_facts_count,
            "metadata": {
                "user_id": user_id,
                "source": source,
                "timestamp": timestamp,
                "db_path": str(db_path),
                "duplicate_check_enabled": enable_duplicate_check
            }
        }
    
    except (TypeError, ValueError) as e:
        logger.error(f"Parameter validation failed - {e}")
        return {
            "status": RESULT_FAILED,
            "success": False,
            "updated_count": 0,
            "skipped_count": 0,
            "errors": [str(e)],
            "total_facts": len(new_facts) if isinstance(new_facts, list) else 0,
            "valid_facts_count": 0
        }
    except Exception as e:
        logger.error(f"Memory update overall exception - {e}", exc_info=True)
        return {
            "status": RESULT_FAILED,
            "success": False,
            "updated_count": 0,
            "skipped_count": 0,
            "errors": [f"System exception: {str(e)}"],
            "total_facts": len(new_facts) if isinstance(new_facts, list) else 0,
            "valid_facts_count": 0
        }


def _init_habits_table(cursor: sqlite3.Cursor) -> None:
    """Initialize habits table structure (idempotent operation)"""
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS habits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            habit_type TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp REAL NOT NULL,
            source TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_habits_user_type ON habits (user_id, habit_type)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_habits_timestamp ON habits (timestamp)
    ''')
    logger.debug("habits table structure initialized/verified")


def _is_duplicate(
    cursor: sqlite3.Cursor,
    user_id: str,
    habit_type: str,
    content: str,
    current_timestamp: float
) -> bool:
    """
    Check if memory is duplicate
    
    :param cursor: Database cursor
    :param user_id: User ID
    :param habit_type: Memory type
    :param content: Memory content
    :param current_timestamp: Current timestamp
    :return: Whether duplicate
    """
    try:
        query_parts = [
            "user_id = ?",
            "habit_type = ?",
            "content = ?"
        ]
        query_params = [user_id, habit_type, content]
        
        if DUPLICATE_TIME_WINDOW > 0:
            time_threshold = current_timestamp - DUPLICATE_TIME_WINDOW
            query_parts.append("timestamp >= ?")
            query_params.append(time_threshold)
        
        query_sql = f"""
            SELECT 1 FROM habits 
            WHERE {" AND ".join(query_parts)} 
            LIMIT 1
        """
        cursor.execute(query_sql, query_params)
        
        return cursor.fetchone() is not None
    
    except Exception as e:
        logger.warning(f"Duplicate check failed, treating as non-duplicate - {e}")
        return False


def get_memory_count(
    user_id: str = 'default',
    habit_type: Optional[str] = None,
    long_term_db: Optional[Path] = None
) -> int:
    """
    Get memory count for specified user (extended feature)
    
    :param user_id: User ID
    :param habit_type: Optional memory type filter
    :param long_term_db: Database path
    :return: Memory count
    """
    db_path = Path(long_term_db) if long_term_db else DEFAULT_LONG_TERM_DB
    try:
        with sqlite3.connect(str(db_path), timeout=DB_TIMEOUT) as conn:
            cursor = conn.cursor()
            if habit_type:
                cursor.execute(
                    "SELECT COUNT(*) FROM habits WHERE user_id = ? AND habit_type = ?",
                    (user_id, habit_type)
                )
            else:
                cursor.execute(
                    "SELECT COUNT(*) FROM habits WHERE user_id = ?",
                    (user_id,)
                )
            return cursor.fetchone()[0]
    except Exception as e:
        logger.error(f"Failed to get memory count - {e}")
        return 0


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    print("\n=== Test Case 1: Normal Batch Insert ===")
    test_facts = [
        {"type": "fact", "value": "Stored in 1Password"},
        {"type": "preference", "value": "Python programming"},
        {"type": "preference", "value": "Machine learning"},
        None,
        {"key": "No value field"},
        {"type": "empty", "value": ""}
    ]
    result1 = update_memory(
        new_facts=test_facts,
        source="test_script",
        user_id="hailong",
        enable_duplicate_check=True
    )
    print(f"Operation result: {result1}")
    
    print("\n=== Test Case 2: Duplicate Insert (Verify Deduplication) ===")
    result2 = update_memory(
        new_facts=[{"type": "fact", "value": "Stored in 1Password"}],
        source="test_script",
        user_id="hailong",
        enable_duplicate_check=True
    )
    print(f"Operation result: {result2}")
    
    print("\n=== Test Case 3: Parameter Error (Verify Validation) ===")
    result3 = update_memory(
        new_facts="Not a list",
        source="",
        user_id="hailong"
    )
    print(f"Operation result: {result3}")
    
    print("\n=== Extended Feature: Get Memory Count ===")
    count = get_memory_count(user_id="hailong")
    print(f"Total memory count for user hailong: {count}")
    count_fact = get_memory_count(user_id="hailong", habit_type="fact")
    print(f"Fact type memory count for user hailong: {count_fact}")
