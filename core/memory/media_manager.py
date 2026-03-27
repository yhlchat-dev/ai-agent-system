#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Multimedia File Custom Storage Manager

Features:
1. User-defined path
2. Tag marking
3. Path persistent storage
4. Image/video/audio management
"""
import os
import shutil
import json
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict


class MediaStorageManager:
    """Multimedia File Custom Storage Manager
    
    Features: User-defined path + Tag marking + Path persistent storage + Image/video/audio management
    """
    
    def __init__(self, user_id: str, default_path: str = "./media_storage"):
        """
        Initialize multimedia storage manager
        
        :param user_id: User ID
        :param default_path: Default storage path
        """
        self.user_id = user_id
        self.default_path = default_path
        self.custom_path: Optional[str] = None
        self.db_path = os.path.join(default_path, "media_index.db")
        self.init_storage_dir()
        self.init_database()
    
    def init_storage_dir(self):
        """Initialize default storage directory"""
        if not os.path.exists(self.default_path):
            os.makedirs(self.default_path, exist_ok=True)
    
    def init_database(self):
        """Initialize media index database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS media_index (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    save_path TEXT NOT NULL,
                    tags TEXT,
                    file_type TEXT,
                    file_size INTEGER,
                    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    custom_path TEXT
                )
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_user_id ON media_index(user_id)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_file_type ON media_index(file_type)
            ''')
            
            conn.commit()
    
    def set_custom_save_path(self, custom_path: str):
        """
        User-defined storage path (core feature)
        
        :param custom_path: Custom storage path
        """
        if not os.path.exists(custom_path):
            os.makedirs(custom_path, exist_ok=True)
        self.custom_path = custom_path
    
    def get_current_save_path(self) -> str:
        """
        Get current storage path (prioritize user-defined)
        
        :return: Current storage path
        """
        return self.custom_path if self.custom_path else self.default_path
    
    def save_media_file(self, file_path: str, tags: List[str] = None) -> dict:
        """
        Save multimedia file (image/video/audio)
        
        :param file_path: Original file path
        :param tags: Tag list (e.g.: avatar, travel, recording)
        :return: Storage info (path + tags + time)
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError("Source file does not exist")
        
        save_dir = self.get_current_save_path()
        file_name = os.path.basename(file_path)
        target_path = os.path.join(save_dir, file_name)
        
        shutil.copy2(file_path, target_path)
        
        file_size = os.path.getsize(target_path)
        
        file_type = self._get_media_type(file_name)
        
        media_info = {
            "user_id": self.user_id,
            "file_name": file_name,
            "save_path": target_path,
            "tags": tags or [],
            "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "file_type": file_type,
            "file_size": file_size,
            "custom_path": self.custom_path
        }
        
        self._save_to_index(media_info)
        
        return media_info
    
    def _get_media_type(self, file_name: str) -> str:
        """
        Auto-identify media type
        
        :param file_name: File name
        :return: Media type
        """
        img_exts = [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg"]
        video_exts = [".mp4", ".mov", ".avi", ".mkv", ".flv", ".wmv"]
        audio_exts = [".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg"]
        
        ext = os.path.splitext(file_name)[-1].lower()
        
        if ext in img_exts:
            return "image"
        if ext in video_exts:
            return "video"
        if ext in audio_exts:
            return "audio"
        
        return "unknown"
    
    def _save_to_index(self, media_info: dict):
        """
        Save media info to index database
        
        :param media_info: Media info dictionary
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO media_index
                (user_id, file_name, save_path, tags, file_type, file_size, custom_path)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                media_info["user_id"],
                media_info["file_name"],
                media_info["save_path"],
                json.dumps(media_info["tags"], ensure_ascii=False),
                media_info["file_type"],
                media_info["file_size"],
                media_info.get("custom_path")
            ))
            
            conn.commit()
    
    def get_media_by_tags(self, tags: List[str]) -> List[Dict]:
        """
        Query media files by tags
        
        :param tags: Tag list
        :return: Media info list
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            conditions = []
            params = [self.user_id]
            
            for tag in tags:
                conditions.append("tags LIKE ?")
                params.append(f"%{tag}%")
            
            where_clause = " OR ".join(conditions)
            
            cursor.execute(f'''
                SELECT id, user_id, file_name, save_path, tags, file_type, 
                       file_size, create_time, custom_path
                FROM media_index
                WHERE user_id = ? AND ({where_clause})
                ORDER BY create_time DESC
            ''', params)
            
            rows = cursor.fetchall()
            
            return [
                {
                    "id": row[0],
                    "user_id": row[1],
                    "file_name": row[2],
                    "save_path": row[3],
                    "tags": json.loads(row[4]) if row[4] else [],
                    "file_type": row[5],
                    "file_size": row[6],
                    "create_time": row[7],
                    "custom_path": row[8]
                }
                for row in rows
            ]
    
    def get_media_by_type(self, file_type: str) -> List[Dict]:
        """
        Query media files by file type
        
        :param file_type: File type (image/video/audio)
        :return: Media info list
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, user_id, file_name, save_path, tags, file_type, 
                       file_size, create_time, custom_path
                FROM media_index
                WHERE user_id = ? AND file_type = ?
                ORDER BY create_time DESC
            ''', (self.user_id, file_type))
            
            rows = cursor.fetchall()
            
            return [
                {
                    "id": row[0],
                    "user_id": row[1],
                    "file_name": row[2],
                    "save_path": row[3],
                    "tags": json.loads(row[4]) if row[4] else [],
                    "file_type": row[5],
                    "file_size": row[6],
                    "create_time": row[7],
                    "custom_path": row[8]
                }
                for row in rows
            ]
    
    def get_all_media(self) -> List[Dict]:
        """
        Get all user media files
        
        :return: Media info list
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, user_id, file_name, save_path, tags, file_type, 
                       file_size, create_time, custom_path
                FROM media_index
                WHERE user_id = ?
                ORDER BY create_time DESC
            ''', (self.user_id,))
            
            rows = cursor.fetchall()
            
            return [
                {
                    "id": row[0],
                    "user_id": row[1],
                    "file_name": row[2],
                    "save_path": row[3],
                    "tags": json.loads(row[4]) if row[4] else [],
                    "file_type": row[5],
                    "file_size": row[6],
                    "create_time": row[7],
                    "custom_path": row[8]
                }
                for row in rows
            ]
    
    def delete_media(self, media_id: int) -> bool:
        """
        Delete media file (delete both file and index record)
        
        :param media_id: Media ID
        :return: Success or not
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT save_path FROM media_index
                WHERE id = ? AND user_id = ?
            ''', (media_id, self.user_id))
            
            row = cursor.fetchone()
            if not row:
                return False
            
            file_path = row[0]
            
            if os.path.exists(file_path):
                os.remove(file_path)
            
            cursor.execute('''
                DELETE FROM media_index
                WHERE id = ? AND user_id = ?
            ''', (media_id, self.user_id))
            
            conn.commit()
            
            return True
    
    def get_stats(self) -> Dict:
        """
        Get media statistics
        
        :return: Statistics info
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT COUNT(*), SUM(file_size)
                FROM media_index
                WHERE user_id = ?
            ''', (self.user_id,))
            
            total_count, total_size = cursor.fetchone()
            
            cursor.execute('''
                SELECT file_type, COUNT(*)
                FROM media_index
                WHERE user_id = ?
                GROUP BY file_type
            ''', (self.user_id,))
            
            by_type = {row[0]: row[1] for row in cursor.fetchall()}
            
            return {
                "total_count": total_count or 0,
                "total_size": total_size or 0,
                "total_size_mb": round((total_size or 0) / (1024 * 1024), 2),
                "by_type": by_type
            }
