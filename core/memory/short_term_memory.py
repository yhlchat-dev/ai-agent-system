#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Short-term Memory Module: Operates short_term.db to store log data, supports multi-user data isolation.
"""

import time
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

from infra.config import MEMORY_SHORT_TERM_LIMIT, get_user_data_dir
from infra.db_manager import get_db_manager


class ShortTermMemory:
    """Short-term Memory Database Operation Class, each user has independent database file"""

    def __init__(self, user_id: str = 'default', db_path: Optional[Path] = None):
        """
        Initialize short-term memory database connection.
        :param user_id: User ID, used to determine data storage directory
        :param db_path: Optional complete database path, if specified, ignores user_id
        """
        self.user_id = user_id
        if db_path is None:
            data_dir = get_user_data_dir(user_id)
            db_path = data_dir / 'short_term.db'
        self.db_path = Path(db_path)
        
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.db_manager = get_db_manager(str(self.db_path))
        self._init_db()
        
    def _init_logs_table(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                user_id TEXT DEFAULT 'default',
                environment TEXT,
                action TEXT,
                result TEXT,
                success_rate REAL,
                trace_id TEXT,
                is_archived INTEGER DEFAULT 0,
                archived_at TEXT
            )
        """)
        conn.commit()

    def _init_db(self) -> None:
        """Initialize database table structure - force rebuild with new table containing user_id"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DROP TABLE IF EXISTS logs")
        conn.commit()
        
        cursor.execute('''
            CREATE TABLE logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                user_id TEXT DEFAULT 'default',
                environment TEXT,
                action TEXT,
                result TEXT,
                success_rate REAL,
                trace_id TEXT,
                is_archived INTEGER DEFAULT 0,
                archived_at TEXT
            )
        ''')
        conn.commit()
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON logs(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_id ON logs(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_is_archived ON logs(is_archived)')
        conn.commit()

    def _ensure_log_schema(self) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(logs)")
        cols = {row[1] for row in cursor.fetchall()}
        if "trace_id" not in cols:
            cursor.execute("ALTER TABLE logs ADD COLUMN trace_id TEXT")
        if "user_id" not in cols:
            cursor.execute("ALTER TABLE logs ADD COLUMN user_id TEXT DEFAULT 'default'")
        if "is_archived" not in cols:
            cursor.execute("ALTER TABLE logs ADD COLUMN is_archived INTEGER DEFAULT 0")
        if "archived_at" not in cols:
            cursor.execute("ALTER TABLE logs ADD COLUMN archived_at TEXT")
        conn.commit()

    def _get_connection(self):
        """Get native sqlite3 connection object for queries"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def insert_log(self, log_dict):
        """Insert single log entry (accepts dictionary form of LogItem)"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO logs (timestamp, user_id, environment, action, result, success_rate, trace_id, is_archived)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                log_dict["timestamp"],
                log_dict.get("user_id", "default"),
                log_dict["environment"],
                log_dict["action"],
                log_dict["result"],
                log_dict["success_rate"],
                log_dict.get("trace_id", ""),
                0
            ))
            conn.commit()

            self._check_auto_archive()
        except Exception as e:
            print(f"[ShortTermMemory] Failed to insert log: {e}")
            raise

    def clean_old_logs(self, hours: int = 24) -> None:
        """
        Delete log records older than specified hours.
        :param hours: Hours to keep, default is 24 hours
        """
        cutoff = time.time() - hours * 3600
        self.db_manager.execute("DELETE FROM logs WHERE timestamp < ?", (cutoff,))

    def query_logs(self, start_time=None, end_time=None, environment=None, limit=None):
        """
        Query raw log data within specified time range
        
        :param start_time: Start time (optional)
        :param end_time: End time (optional)
        :param environment: Environment filter (optional)
        :param limit: Return count limit (optional)
        :return: Log list
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        conditions = []
        params = []
        
        if start_time is not None:
            conditions.append("timestamp >= ?")
            params.append(start_time)
        
        if end_time is not None:
            conditions.append("timestamp <= ?")
            params.append(end_time)
        
        if environment is not None:
            conditions.append("environment = ?")
            params.append(environment)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sql = f"""
            SELECT timestamp, environment, action, result, success_rate, trace_id
            FROM logs
            WHERE {where_clause}
            ORDER BY timestamp DESC
        """
        
        if limit is not None:
            sql += f" LIMIT {limit}"
        
        cursor.execute(sql, params)
        
        columns = ["timestamp", "environment", "action", "result", "success_rate", "trace_id"]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_recent_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get the most recent limit logs"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT timestamp, environment, action, result, success_rate
            FROM logs
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))
        
        result = []
        for row in cursor.fetchall():
            result.append({
                'timestamp': row[0],
                'environment': row[1],
                'action': row[2],
                'result': row[3],
                'success_rate': row[4]
            })
        return result

    def query_logs_by_cutoff(self, cutoff: float) -> List[Dict[str, Any]]:
        """Query all logs with timestamp < cutoff (for transfer)"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, timestamp, environment, action, result, success_rate
            FROM logs
            WHERE timestamp < ?
            ORDER BY timestamp
        ''', (cutoff,))
        
        logs = []
        for row in cursor.fetchall():
            logs.append({
                'id': row[0],
                'timestamp': row[1],
                'environment': row[2],
                'action': row[3],
                'result': row[4],
                'success_rate': row[5],
                'content': row[3],
                'role': 'system',
                'user_id': self.user_id
            })
        return logs

    def save_log(self, log_type: str = None, content: str = None, success: float = 1.0, **kwargs):
        """
        Short-term memory archive log (compatible with multiple calling methods)
        
        :param log_type: Log type
        :param content: Log content
        :param success: Success rate (default 1.0)
        :param kwargs: Supports direct passing of environment, action, result, etc.
        """
        try:
            if kwargs.get("action") and kwargs.get("result"):
                log_dict = {
                    "timestamp": time.time(),
                    "user_id": kwargs.get("user_id", "default"),
                    "environment": kwargs.get("environment", "production"),
                    "action": kwargs["action"],
                    "result": kwargs["result"],
                    "success_rate": kwargs.get("success_rate", 1.0),
                    "trace_id": kwargs.get("trace_id", "")
                }
            else:
                log_dict = {
                    "timestamp": time.time(),
                    "user_id": kwargs.get("user_id", "default"),
                    "environment": kwargs.get("environment", "production"),
                    "action": log_type,
                    "result": content,
                    "success_rate": success,
                    "trace_id": kwargs.get("trace_id", "")
                }
            self.insert_log(log_dict)
            print(f"[ShortTermMemory] Archived log: [{log_dict['action']}] {log_dict['result'][:50]}... (Success rate: {log_dict['success_rate']})")
        except Exception as e:
            print(f"[ShortTermMemory] Failed to archive log: {e}")

    def delete_logs_older_than(self, cutoff: float) -> None:
        """
        Delete all logs with timestamp < cutoff.
        :param cutoff: Cutoff timestamp
        """
        self.db_manager.execute("DELETE FROM logs WHERE timestamp < ?", (cutoff,))

    def _check_auto_archive(self) -> None:
        """Check if short-term memory needs to be auto-archived to long-term memory"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM logs")
            count = cursor.fetchone()[0]

            if count > MEMORY_SHORT_TERM_LIMIT:
                archive_count = count - MEMORY_SHORT_TERM_LIMIT + 5
                self._archive_old_logs(archive_count)
        except Exception as e:
            print(f"[ShortTermMemory] Auto archive check failed: {e}")

    def _archive_old_logs(self, count: int) -> None:
        """Archive the oldest count logs to long-term memory"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, timestamp, environment, action, result, success_rate FROM logs ORDER BY timestamp ASC LIMIT ?",
                (count,)
            )
            old_logs = cursor.fetchall()

            for log in old_logs:
                compressed_content = f"[{log[2]}] {log[3]} -> {log[4]} (Success rate: {log[5]})"
                print(f"[ShortTermMemory] Archiving log: {compressed_content}")

            if old_logs:
                ids = [log[0] for log in old_logs]
                placeholders = ','.join('?' * len(ids))
                self.db_manager.execute(
                    f"DELETE FROM logs WHERE id IN ({placeholders})",
                    ids
                )

        except Exception as e:
            print(f"[ShortTermMemory] Archive failed: {e}")
