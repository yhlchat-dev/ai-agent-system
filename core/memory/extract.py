#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Memory Extraction: Extract relevant content from short-term/long-term memory"""
from .storage import ShortMemory, LongMemory
from utils.logging import memory_logger

class MemoryExtractor:
    """Memory Extractor"""
    @staticmethod
    def extract_recent(count=10):
        """Extract recent N short-term memories"""
        import sqlite3
        conn = sqlite3.connect("agent_memory.db")
        cursor = conn.cursor()
        cursor.execute('''
        SELECT content FROM short_memory 
        ORDER BY create_time DESC LIMIT ?
        ''', (count,))
        records = [row[0] for row in cursor.fetchall()]
        conn.close()
        memory_logger.debug(f"Extracted {len(records)} recent short-term memories")
        return records
    
    @staticmethod
    def extract_long_term(keyword, limit=5):
        """Extract long-term memory by keyword (1.0 minimal version)"""
        import sqlite3
        conn = sqlite3.connect("agent_memory.db")
        cursor = conn.cursor()
        cursor.execute('''
        SELECT content FROM long_memory 
        WHERE content LIKE ? ORDER BY create_time DESC LIMIT ?
        ''', (f"%{keyword}%", limit))
        records = [row[0] for row in cursor.fetchall()]
        conn.close()
        memory_logger.debug(f"Extracted {len(records)} long-term memories with keyword [{keyword}]")
        return records
