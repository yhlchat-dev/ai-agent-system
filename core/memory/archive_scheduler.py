#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Archive Scheduler: 5-7 day short-term memory to long-term memory automatic archiving

Features:
1. Scheduled scanning of short-term memory data
2. Automatic classification and tagging
3. Full archiving to long-term memory
4. Automatic cleanup of archived data
5. Support for incremental and full archiving
"""
import os
import json
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional


class ArchiveScheduler:
    """Archive Scheduler: 5-7 day short-term memory to long-term memory automatic archiving"""
    
    def __init__(self, short_term_memory, long_term_memory, 
                 archive_days: int = 5, check_interval: int = 86400):
        """
        Initialize archive scheduler
        
        :param short_term_memory: Short-term memory instance
        :param long_term_memory: Long-term memory instance
        :param archive_days: Archive days (default 5 days)
        :param check_interval: Check interval (seconds, default 24 hours)
        """
        self.short_term_memory = short_term_memory
        self.long_term_memory = long_term_memory
        self.archive_days = archive_days
        self.check_interval = check_interval
        self.is_running = False
        self.archive_thread = None
        
    def start(self):
        """Start archive scheduler"""
        if self.is_running:
            return
        
        self.is_running = True
        self.archive_thread = threading.Thread(target=self._archive_loop, daemon=True)
        self.archive_thread.start()
        print(f"Archive scheduler started ({self.archive_days} day auto archive)")
    
    def stop(self):
        """Stop archive scheduler"""
        self.is_running = False
        if self.archive_thread:
            self.archive_thread.join(timeout=5)
        print("Archive scheduler stopped")
    
    def _archive_loop(self):
        """Archive loop"""
        while self.is_running:
            try:
                self.archive_old_memories()
                
                self.cleanup_archived_data()
                
            except Exception as e:
                print(f"Archive loop error: {e}")
            
            time.sleep(self.check_interval)
    
    def archive_old_memories(self) -> Dict:
        """
        Archive old memories to long-term memory
        
        :return: Archive statistics
        """
        print(f"\nStarting archive task (data older than {self.archive_days} days)...")
        
        stats = {
            "total_scanned": 0,
            "total_archived": 0,
            "total_failed": 0,
            "by_category": {}
        }
        
        try:
            cutoff_date = datetime.now() - timedelta(days=self.archive_days)
            
            old_memories = self._get_old_memories(cutoff_date)
            stats["total_scanned"] = len(old_memories)
            
            print(f"Scanned {len(old_memories)} items for archiving")
            
            for memory in old_memories:
                try:
                    category = self._classify_memory(memory)
                    
                    self.long_term_memory.save_memory(
                        user_id=memory.get("user_id", "default"),
                        content=memory.get("content", ""),
                        memory_type=category,
                        metadata={
                            "original_id": memory.get("id"),
                            "created_at": memory.get("created_at"),
                            "archived_at": datetime.now().isoformat(),
                            "category": category
                        }
                    )
                    
                    self._mark_as_archived(memory.get("id"))
                    
                    stats["total_archived"] += 1
                    stats["by_category"][category] = stats["by_category"].get(category, 0) + 1
                    
                except Exception as e:
                    print(f"Archive failed (ID: {memory.get('id')}): {e}")
                    stats["total_failed"] += 1
            
            print(f"Archive completed: {stats['total_archived']}/{stats['total_scanned']} items")
            
        except Exception as e:
            print(f"Archive task failed: {e}")
        
        return stats
    
    def _get_old_memories(self, cutoff_date: datetime) -> List[Dict]:
        """
        Get old memories for archiving
        
        :param cutoff_date: Cutoff date
        :return: List of old memories
        """
        try:
            db_path = getattr(self.short_term_memory, 'db_path', 'data/short_term_memory.db')
            
            if not os.path.exists(db_path):
                return []
            
            import time
            cutoff_timestamp = time.mktime(cutoff_date.timetuple())
            
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT id, user_id, action, result, timestamp
                    FROM logs
                    WHERE timestamp < ?
                    AND (is_archived = 0 OR is_archived IS NULL)
                    ORDER BY timestamp ASC
                ''', (cutoff_timestamp,))
                
                rows = cursor.fetchall()
                
                return [
                    {
                        "id": row[0],
                        "user_id": row[1],
                        "action": row[2],
                        "content": row[3],
                        "created_at": row[4],
                        "timestamp": row[4]
                    }
                    for row in rows
                ]
                
        except Exception as e:
            print(f"Failed to get old memories: {e}")
            return []
    
    def _classify_memory(self, memory: Dict) -> str:
        """
        Automatically classify memory
        
        :param memory: Memory data
        :return: Category label
        """
        content = memory.get("content", "").lower()
        action = memory.get("action", "").lower()
        
        categories = {
            "identity": ["my name is", "i am", "name"],
            "contact": ["phone", "telephone", "email", "contact"],
            "preference": ["like", "prefer", "interest", "favorite"],
            "plan": ["i want", "i will", "plan", "intend"],
            "conversation": ["dialog", "chat", "q&a"],
            "task": ["task", "execute", "complete"],
            "error": ["error", "exception", "failed"]
        }
        
        for category, keywords in categories.items():
            for keyword in keywords:
                if keyword in content or keyword in action:
                    return category
        
        return "general"
    
    def _mark_as_archived(self, memory_id: int):
        """
        Mark memory as archived
        
        :param memory_id: Memory ID
        """
        try:
            db_path = getattr(self.short_term_memory, 'db_path', 'data/short_term_memory.db')
            
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    UPDATE logs
                    SET is_archived = 1, archived_at = ?
                    WHERE id = ?
                ''', (datetime.now().isoformat(), memory_id))
                
                conn.commit()
                
        except Exception as e:
            print(f"Failed to mark as archived: {e}")
    
    def cleanup_archived_data(self, days: int = 30):
        """
        Clean up archived old data
        
        :param days: Days to keep
        """
        try:
            db_path = getattr(self.short_term_memory, 'db_path', 'data/short_term_memory.db')
            
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    DELETE FROM logs
                    WHERE is_archived = 1
                    AND archived_at < datetime('now', ?)
                ''', (f'-{days} days',))
                
                deleted = cursor.rowcount
                conn.commit()
                
                if deleted > 0:
                    print(f"Cleaned up {deleted} archived items")
                    
        except Exception as e:
            print(f"Failed to clean up data: {e}")
    
    def force_archive_all(self) -> Dict:
        """
        Force archive all data (full archive)
        
        :return: Archive statistics
        """
        print("\nStarting full archive...")
        
        stats = {
            "total_archived": 0,
            "total_failed": 0
        }
        
        try:
            all_memories = self._get_all_unarchived()
            
            print(f"Found {len(all_memories)} unarchived items")
            
            for memory in all_memories:
                try:
                    category = self._classify_memory(memory)
                    
                    self.long_term_memory.save_memory(
                        user_id=memory.get("user_id", "default"),
                        content=memory.get("content", ""),
                        memory_type=category,
                        metadata={
                            "original_id": memory.get("id"),
                            "created_at": memory.get("created_at"),
                            "archived_at": datetime.now().isoformat(),
                            "category": category
                        }
                    )
                    
                    self._mark_as_archived(memory.get("id"))
                    stats["total_archived"] += 1
                    
                except Exception as e:
                    print(f"Archive failed: {e}")
                    stats["total_failed"] += 1
            
            print(f"Full archive completed: {stats['total_archived']} items")
            
        except Exception as e:
            print(f"Full archive failed: {e}")
        
        return stats
    
    def _get_all_unarchived(self) -> List[Dict]:
        """
        Get all unarchived data
        
        :return: List of unarchived data
        """
        try:
            db_path = getattr(self.short_term_memory, 'db_path', 'data/short_term_memory.db')
            
            if not os.path.exists(db_path):
                return []
            
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT id, user_id, action, result, timestamp
                    FROM logs
                    WHERE is_archived = 0 OR is_archived IS NULL
                    ORDER BY timestamp ASC
                ''')
                
                rows = cursor.fetchall()
                
                return [
                    {
                        "id": row[0],
                        "user_id": row[1],
                        "action": row[2],
                        "content": row[3],
                        "created_at": row[4],
                        "timestamp": row[4]
                    }
                    for row in rows
                ]
                
        except Exception as e:
            print(f"Failed to get unarchived data: {e}")
            return []
    
    def get_archive_stats(self) -> Dict:
        """
        Get archive statistics
        
        :return: Statistics
        """
        try:
            db_path = getattr(self.short_term_memory, 'db_path', 'data/short_term_memory.db')
            
            if not os.path.exists(db_path):
                return {"error": "Database does not exist"}
            
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('SELECT COUNT(*) FROM logs')
                total = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM logs WHERE is_archived = 1')
                archived = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM logs WHERE is_archived = 0 OR is_archived IS NULL')
                unarchived = cursor.fetchone()[0]
                
                return {
                    "total_records": total,
                    "archived_records": archived,
                    "unarchived_records": unarchived,
                    "archive_rate": f"{(archived/total*100):.1f}%" if total > 0 else "0%"
                }
                
        except Exception as e:
            return {"error": str(e)}


archive_scheduler = None
