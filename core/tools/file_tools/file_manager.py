# -*- coding: utf-8 -*-
"""
File Management Tools: Register, search, read/write files
"""
import os
import shutil
import sqlite3
import time
from pathlib import Path
from datetime import datetime

def register_file(src_path, tags="", description="", user_id='default', data_dir=None):
    """Register file to index database"""
    from infra.config import DATA_DIR
    data_dir = Path(data_dir or DATA_DIR)
    src = Path(src_path)
    if not src.exists():
        return {"success": False, "result": None, "error": f"Source file does not exist"}
        
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_filename = f"{src.stem}_{timestamp}{src.suffix}"
    user_files_dir = data_dir / 'files' / user_id
    user_files_dir.mkdir(parents=True, exist_ok=True)
    dest_path = user_files_dir / dest_filename

    try:
        shutil.copy2(src, dest_path)
    except Exception as e:
        return {"success": False, "result": None, "error": f"Copy failed: {e}"}

    try:
        conn = sqlite3.connect(data_dir / "file_index.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO files (path, filename, tags, description, created_at, user_id) VALUES (?, ?, ?, ?, ?, ?)",
            (str(dest_path), dest_filename, tags, description, time.time(), user_id)
        )
        conn.commit()
        conn.close()
        
        return {"success": True, "result": f"File saved", "error": None}
    except Exception as e:
        return {"success": False, "result": None, "error": f"Database write failed: {e}"}

def search_files(query, tag_only=False, data_dir=None):
    """Search files"""
    from infra.config import DATA_DIR
    data_dir = Path(data_dir or DATA_DIR)
    try:
        conn = sqlite3.connect(data_dir / "file_index.db")
        cursor = conn.cursor()
        
        if tag_only:
            cursor.execute("""
                SELECT path, filename, tags, description, created_at 
                FROM files WHERE tags LIKE ?
            """, (f"%{query}%",))
        else:
            cursor.execute("""
                SELECT path, filename, tags, description, created_at 
                FROM files WHERE tags LIKE ? OR description LIKE ?
            """, (f"%{query}%", f"%{query}%"))
            
        rows = cursor.fetchall()
        conn.close()
        
        results = [{
            "path": r[0], "filename": r[1], "tags": r[2], 
            "description": r[3], "created_at": r[4]
        } for r in rows]
        
        return {"success": True, "result": results, "error": None}
    except Exception as e:
        return {"success": False, "result": None, "error": str(e)}

def list_files(data_dir=None):
    """List all files"""
    from infra.config import DATA_DIR
    data_dir = Path(data_dir or DATA_DIR)
    try:
        conn = sqlite3.connect(data_dir / "file_index.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT path, filename, tags, description, created_at 
            FROM files ORDER BY created_at DESC
        """)
        rows = cursor.fetchall()
        conn.close()
        
        results = [{
            "path": r[0], "filename": r[1], "tags": r[2], 
            "description": r[3], "created_at": r[4]
        } for r in rows]
        
        return {"success": True, "result": results, "error": None}
    except Exception as e:
        return {"success": False, "result": None, "error": str(e)}

def read_file(file_path):
    """Read file content"""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File does not exist")
        
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def write_file(file_path, content):
    """Write file content"""
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
        
    return f"File saved"
