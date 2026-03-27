# -*- coding: utf-8 -*-
"""
Patrol Tools: Conversation/Memory/Knowledge patrol + Capsule system calls
"""
import sqlite3
import time
from pathlib import Path

def patrol_recent(days=7, user_id='default', data_dir=None):
    """Patrol recent conversation records"""
    from infra.config import DATA_DIR
    data_dir = Path(data_dir or DATA_DIR)
    db_path = data_dir / 'short_term.db'
    if not db_path.exists():
        return {"success": True, "data": [], "error": None}
        
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        threshold = time.time() - days * 24 * 3600
        cursor.execute("""
            SELECT session_id, user_msg, agent_reply, timestamp 
            FROM conversations 
            WHERE user_id=? AND timestamp > ? 
            ORDER BY timestamp DESC LIMIT ?
        """, (user_id, threshold, max_results))
        rows = cursor.fetchall()
        conn.close()
        
        results = [{
            "source": "short_term", 
            "content": f"User: {row[1]}\nAgent: {row[2]}",
            "timestamp": row[3], 
            "metadata": {"session_id": row[0], "type": "conversation"}
        } for row in rows]
        
        return {"success": True, "data": results, "error": None}
    except Exception as e:
        return {"success": False, "data": [], "error": str(e)}

def patrol_facts(keywords, user_id='default', max_results=10, data_dir=None):
    """Patrol long-term memory"""
    from infra.config import DATA_DIR
    data_dir = Path(data_dir or DATA_DIR)
    db_path = data_dir / 'long_term.db'
    if not db_path.exists():
        return {"success": True, "data": [], "error": None}
        
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT habit_type, content, timestamp 
            FROM habits 
            WHERE user_id=? AND content LIKE ? 
            ORDER BY timestamp DESC LIMIT ?
        """, (user_id, f"%{keywords}%", max_results))
        rows = cursor.fetchall()
        conn.close()
        
        results = [{
            "source": "long_term_habits", 
            "content": f"{row[0]}: {row[1]}",
            "timestamp": row[2], 
            "metadata": {"type": row[0]}
        } for row in rows]
        
        return {"success": True, "data": results, "error": None}
    except Exception as e:
        return {"success": False, "data": [], "error": str(e)}

def patrol_knowledge(query, user_id='default', max_results=10):
    """Patrol knowledge base (reserved)"""
    return {"success": True, "data": [], "error": None}

def capsule_search(query, user_id=None, top_k=5, capsule_manager=None):
    """Search experience capsules"""
    if not capsule_manager:
        return {"success": False, "result": None, "error": "Capsule manager not initialized"}
        
    results = capsule_manager.search_capsules(query, user_id=user_id, top_k=top_k)
    return {"success": True, "data": results, "error": None}

def capsule_add(problem, solution, tags, creator='default', capsule_manager=None):
    """Add experience capsule"""
    if not capsule_manager:
        return {"success": False, "result": None, "error": "Capsule manager not initialized"}
        
    tag_list = [t.strip() for t in tags.split(',')] if tags else []
    cap_id = capsule_manager.add_capsule(problem, solution, tag_list, creator=creator)
    return {"success": True, "capsule_id": cap_id, "error": None}

def capsule_update(capsule_id, success, capsule_manager=None):
    """Update capsule usage result"""
    if not capsule_manager:
        return {"success": False, "result": None, "error": "Capsule manager not initialized"}
        
    capsule_manager.update_capsule(capsule_id, success)
    return {"success": True, "error": None}
