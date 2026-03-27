import os
import sqlite3
import threading
from typing import Optional, Dict, List, Any, Tuple
from contextlib import contextmanager
from typing import Any, List, Tuple

_db_managers: Dict[str, 'DatabaseManager'] = {}
_lock = threading.Lock()


class DBManager:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def execute(self, sql: str, params: Tuple = ()) -> Any:
        cursor = self.conn.cursor()
        cursor.execute(sql, params)
        self.conn.commit()
        return cursor

    def fetchall(self, sql: str, params: Tuple = ()) -> List[sqlite3.Row]:
        cursor = self.conn.cursor()
        cursor.execute(sql, params)
        return cursor.fetchall()

    def fetchone(self, sql: str, params: Tuple = ()) -> sqlite3.Row:
        cursor = self.conn.cursor()
        cursor.execute(sql, params)
        return cursor.fetchone()

    def close(self):
        self.conn.close()

def get_db_manager(db_path: str) -> DBManager:
    return DBManager(db_path)


class DatabaseManager:
    """
    Database Manager (Singleton Pattern)
    Enhanced with shortcut methods for compatibility with legacy code style (direct execute/fetchall calls)
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._local = threading.local()
        os.makedirs(os.path.dirname(db_path), exist_ok=True) if os.path.dirname(db_path) else None
        self._init_db_schema()

    def _init_db_schema(self):
        """Reserved: For unified table creation if needed"""
        pass

    def get_connection(self) -> sqlite3.Connection:
        """Get database connection for current thread"""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30
            )
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection

    def execute(self, sql: str, parameters: Tuple = ()) -> sqlite3.Cursor:
        """
        Execute SQL directly (compatible with legacy interface)
        Automatically gets connection and executes, returns cursor
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, parameters)
        conn.commit()
        return cursor

    def fetchall(self, sql: str, parameters: Tuple = ()) -> List[sqlite3.Row]:
        """
        Execute query and return all results (compatible with legacy interface)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, parameters)
        return cursor.fetchall()

    def fetchone(self, sql: str, parameters: Tuple = ()) -> Optional[sqlite3.Row]:
        """
        Execute query and return single row result (compatible with legacy interface)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, parameters)
        return cursor.fetchone()

    def fetch_one(self, query, params=None):
        """
        Get single record (alias method for compatibility)
        """
        return self.fetchone(query, params if params is not None else ())

    def close(self):
        """Close current thread's connection"""
        if hasattr(self._local, 'connection') and self._local.connection:
            self._local.connection.close()
            self._local.connection = None

    @classmethod
    def get_instance(cls, db_path: str) -> 'DatabaseManager':
        """Get singleton instance"""
        if db_path not in _db_managers:
            with _lock:
                if db_path not in _db_managers:
                    _db_managers[db_path] = cls(db_path)
        return _db_managers[db_path]

    @classmethod
    def clear_instances(cls):
        """Clear all instances (for test reset)"""
        with _lock:
            for manager in _db_managers.values():
                manager.close()
            _db_managers.clear()


def get_db_manager(db_path: str) -> DatabaseManager:
    return DatabaseManager.get_instance(db_path)


@contextmanager
def get_db_context(db_path: str):
    db = get_db_manager(db_path)
    try:
        yield db
    finally:
        pass


import atexit


def _cleanup():
    DatabaseManager.clear_instances()


atexit.register(_cleanup)
