#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Memory Storage: Underlying storage implementation for short-term/long-term memory"""
import sqlite3
import os
from datetime import datetime
from utils.logging import memory_logger

DB_PATH = "agent_memory.db"

class ShortMemory:
    """Short-term memory: Stores daily chat/interaction records"""
    @classmethod
    def init_table(cls):
        """Initialize short-term memory table"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS short_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            create_time DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        conn.commit()
        conn.close()
        memory_logger.info("Short-term memory table initialized")
    
    @classmethod
    def add(cls, content):
        """Add short-term memory"""
        if not content:
            return
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO short_memory (content, create_time)
        VALUES (?, ?)
        ''', (content, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
        memory_logger.debug(f"Added short-term memory: {content[:20]}...")
    
    @classmethod
    def get_count(cls):
        """Get short-term memory count"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM short_memory WHERE DATE(create_time) = DATE("now")')
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    @classmethod
    def archive_to_long(cls, long_memory):
        """Archive short-term memory older than 1 day to long-term memory"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
        SELECT content, create_time FROM short_memory 
        WHERE DATE(create_time) < DATE("now")
        ''')
        records = cursor.fetchall()
        for content, create_time in records:
            long_memory.add(content, create_time)
        cursor.execute('''
        DELETE FROM short_memory WHERE DATE(create_time) < DATE("now")
        ''')
        conn.commit()
        conn.close()
        memory_logger.info(f"Archived {len(records)} short-term memories to long-term memory")

class LongMemory:
    """Long-term memory: Stores archived historical records"""
    @classmethod
    def init_table(cls):
        """Initialize long-term memory table"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS long_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            create_time DATETIME NOT NULL
        )
        ''')
        conn.commit()
        conn.close()
        memory_logger.info("Long-term memory table initialized")
    
    @classmethod
    def add(cls, content, create_time):
        """Add long-term memory"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO long_memory (content, create_time)
        VALUES (?, ?)
        ''', (content, create_time))
        conn.commit()
        conn.close()
    
    @classmethod
    def get_count(cls):
        """Get long-term memory count"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM long_memory')
        count = cursor.fetchone()[0]
        conn.close()
        return count

ShortMemory.init_table()
LongMemory.init_table()
