#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Temporary Memory Database: New information entry point, periodic sync to short-term memory

Features:
1. Store new information from user input
2. Periodic sync to short-term memory
3. Support incremental data management
4. Auto cleanup of synced data
"""
import os
import json
import sqlite3
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional


class TempDatabase:
    """Temporary Memory Database: New information entry point, periodic sync to short-term memory"""
    
    def __init__(self, db_path: str = "data/temp_memory.db"):
        self.db_path = db_path
        self.lock = threading.Lock()
        self.init_db()
        self.sync_interval = 3600
        self.sync_thread = None
        self.is_running = False
        
    def init_db(self):
        """Initialize temporary database"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS temp_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    info_type TEXT NOT NULL,
                    info_value TEXT NOT NULL,
                    info_category TEXT,
                    is_sensitive INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_synced INTEGER DEFAULT 0,
                    synced_at TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_user_id ON temp_memory(user_id)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_is_synced ON temp_memory(is_synced)
            ''')
            
            conn.commit()
    
    def save_temp(self, user_id: str, info_type: str, info_value: str, 
                  info_category: str = None, is_sensitive: bool = False) -> int:
        """
        Save temporary information
        
        :param user_id: User ID
        :param info_type: Information type (name/phone/preference/intent etc.)
        :param info_value: Information value
        :param info_category: Information category (identity/contact/preference/plan)
        :param is_sensitive: Whether it is sensitive information
        :return: Record ID
        """
        if isinstance(user_id, list):
            user_id = str(user_id[0]) if user_id else "default"
        else:
            user_id = str(user_id)
        
        info_type = str(info_type)
        info_value = str(info_value)
        if info_category is not None:
            info_category = str(info_category)
        
        is_sensitive = bool(is_sensitive)
        
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO temp_memory 
                    (user_id, info_type, info_value, info_category, is_sensitive)
                    VALUES (?, ?, ?, ?, ?)
                ''', (user_id, info_type, info_value, info_category, int(is_sensitive)))
                
                record_id = cursor.lastrowid
                conn.commit()
                
                return record_id
    
    def get_unsynced_data(self, limit: int = 100) -> List[Dict]:
        """
        Get unsynchronized data
        
        :param limit: Maximum return count
        :return: List of unsynchronized data
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, user_id, info_type, info_value, info_category, 
                       is_sensitive, created_at
                FROM temp_memory
                WHERE is_synced = 0
                ORDER BY created_at ASC
                LIMIT ?
            ''', (limit,))
            
            rows = cursor.fetchall()
            
            return [
                {
                    "id": row[0],
                    "user_id": row[1],
                    "info_type": row[2],
                    "info_value": row[3],
                    "info_category": row[4],
                    "is_sensitive": bool(row[5]),
                    "created_at": row[6]
                }
                for row in rows
            ]
    
    def mark_as_synced(self, record_ids: List[int]):
        """
        Mark as synchronized
        
        :param record_ids: List of record IDs
        """
        if not record_ids:
            return
        
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                placeholders = ','.join('?' * len(record_ids))
                cursor.execute(f'''
                    UPDATE temp_memory
                    SET is_synced = 1, synced_at = CURRENT_TIMESTAMP
                    WHERE id IN ({placeholders})
                ''', record_ids)
                
                conn.commit()
    
    def cleanup_synced_data(self, days: int = 7):
        """
        Clean up old synchronized data
        
        :param days: Days to keep
        """
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM temp_memory
                    WHERE is_synced = 1
                    AND synced_at < datetime('now', ?)
                ''', (f'-{days} days',))
                
                conn.commit()
    
    def get_user_temp_data(self, user_id: str) -> List[Dict]:
        """
        Get user temporary data
        
        :param user_id: User ID
        :return: List of user temporary data
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, user_id, info_type, info_value, info_category, 
                       is_sensitive, created_at
                FROM temp_memory
                WHERE user_id = ? AND is_synced = 0
                ORDER BY created_at DESC
            ''', (user_id,))
            
            rows = cursor.fetchall()
            
            return [
                {
                    "id": row[0],
                    "user_id": row[1],
                    "info_type": row[2],
                    "info_value": row[3],
                    "info_category": row[4],
                    "is_sensitive": bool(row[5]),
                    "created_at": row[6]
                }
                for row in rows
            ]
    
    def start_sync_thread(self, callback):
        """Start sync thread"""
        if self.is_running:
            return
        
        self.is_running = True
        
        def sync_worker():
            while self.is_running:
                try:
                    unsynced = self.get_unsynced_data()
                    if unsynced:
                        callback(unsynced)
                        self.mark_as_synced([item['id'] for item in unsynced])
                except Exception as e:
                    pass
                
                time.sleep(self.sync_interval)
        
        self.sync_thread = threading.Thread(target=sync_worker, daemon=True)
        self.sync_thread.start()
    
    def stop_sync_thread(self):
        """Stop sync thread"""
        self.is_running = False
        if self.sync_thread:
            self.sync_thread.join(timeout=5)
