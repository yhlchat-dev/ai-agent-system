#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Capsule Manager (Core Required: capsule_schema_version field)
Features:
- Manage Agent experience capsules + error experience capsules + user capsules + skill capsules
- Database persistent storage
- Version compatibility (reserved for future structure upgrades)
- Logging (integrated with capsule.log)
"""

import sqlite3
import os
import time
import json
from datetime import datetime
from typing import List, Dict, Optional, Union

class AgentCapsule:
    def __init__(self, agent_id, content, capsule_type="experience"):
        self.schema_version = "1.0"
        self.agent_id = agent_id
        self.content = content
        self.capsule_type = capsule_type
        self.create_time = time.time()
    
    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            "agent_id": self.agent_id,
            "content": self.content,
            "capsule_type": self.capsule_type,
            "create_time": self.create_time
        }

class ErrorCapsule(AgentCapsule):
    def __init__(self, agent_id, error_msg, error_type, traceback=""):
        super().__init__(agent_id, f"[{error_type}] {error_msg}", "error")
        self.error_type = error_type
        self.traceback = traceback
    
    def to_dict(self):
        base = super().to_dict()
        base.update({"error_type": self.error_type, "traceback": self.traceback})
        return base

class UserCapsule(AgentCapsule):
    def __init__(self, agent_id, user_info_type, user_info_value, info_category=None):
        super().__init__(agent_id, f"{user_info_type}: {user_info_value}", "user_info")
        self.user_info_type = user_info_type
        self.user_info_value = user_info_value
        self.info_category = info_category or self._get_info_category(user_info_type)
    
    def _get_info_category(self, user_info_type):
        """Auto-categorize based on information type"""
        category_mapping = {
            "name": "identity",
            "phone": "contact",
            "email": "contact",
            "address": "contact",
            "preference": "preference",
            "like": "preference",
            "hobby": "preference",
            "intent": "plan",
            "plan": "plan",
            "goal": "plan"
        }
        return category_mapping.get(user_info_type, "other")
    
    def to_dict(self):
        base = super().to_dict()
        base.update({
            "user_info_type": self.user_info_type,
            "user_info_value": self.user_info_value,
            "info_category": self.info_category
        })
        return base

class SkillCapsule(AgentCapsule):
    def __init__(self, agent_id, skill_name, skill_description, skill_params=None):
        super().__init__(agent_id, f"Skill: {skill_name}", "skill")
        self.skill_name = skill_name
        self.skill_description = skill_description
        self.skill_params = skill_params or {}
    
    def to_dict(self):
        base = super().to_dict()
        base.update({
            "skill_name": self.skill_name,
            "skill_description": self.skill_description,
            "skill_params": json.dumps(self.skill_params)
        })
        return base

import logging
capsule_logger = logging.getLogger("capsule")
if not capsule_logger.handlers:
    os.makedirs("logs", exist_ok=True)
    file_handler = logging.FileHandler("logs/capsule.log", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ))
    capsule_logger.addHandler(file_handler)
    capsule_logger.setLevel(logging.INFO)

DEFAULT_DATA_DIR = os.path.join("data", "agent_brain")
CAPSULE_DB_PATH = os.path.join(DEFAULT_DATA_DIR, "capsules.db")

class CapsuleManager:
    """
    Capsule Manager (Core Required: capsule_schema_version field)
    """
    def __init__(self, db_path: Optional[str] = None, data_dir: Optional[str] = None):
        self.data_dir = data_dir or DEFAULT_DATA_DIR
        self.db_path = db_path or os.path.join(self.data_dir, "capsules.db")
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self.init_db()
        capsule_logger.info("Capsule manager initialized")

    def init_db(self):
        """
        Initialize capsule database table - force rebuild to clear all old data
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DROP TABLE IF EXISTS capsules")
        capsule_logger.info("Old capsule table dropped, all historical data cleared")
        
        cursor.execute('''
        CREATE TABLE capsules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schema_version TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            content TEXT NOT NULL,
            capsule_type TEXT NOT NULL,
            create_time REAL NOT NULL,
            error_type TEXT,
            traceback TEXT,
            user_info_type TEXT,
            user_info_value TEXT,
            info_category TEXT,
            skill_name TEXT,
            skill_description TEXT,
            skill_params TEXT,
            UNIQUE(agent_id, create_time)
        )
        ''')
        
        cursor.execute('CREATE INDEX idx_agent_id ON capsules(agent_id)')
        cursor.execute('CREATE INDEX idx_capsule_type ON capsules(capsule_type)')
        cursor.execute('CREATE INDEX idx_create_time ON capsules(create_time)')
        cursor.execute('CREATE INDEX idx_user_info_type ON capsules(user_info_type)')
        cursor.execute('CREATE INDEX idx_info_category ON capsules(info_category)')
        conn.commit()
        capsule_logger.info("Capsule table initialized - brand new empty table")
        try:
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_skill_name ON capsules(skill_name)')
        except:
            pass
        
        conn.close()
        capsule_logger.info("Capsule database table initialized (with version field)")

    def save_capsule(self, capsule: Union[AgentCapsule, ErrorCapsule]) -> int:
        """
        Save capsule to database (auto-distinguish experience/error/user/skill capsules, record version)
        :param capsule: AgentCapsule or ErrorCapsule or UserCapsule or SkillCapsule object
        :return: Inserted capsule ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            data = capsule.to_dict()
            
            cursor.execute('''
            INSERT INTO capsules 
            (schema_version, agent_id, content, capsule_type, create_time, error_type, traceback, 
             user_info_type, user_info_value, info_category, skill_name, skill_description, skill_params)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data["schema_version"],
                data["agent_id"],
                data["content"],
                data["capsule_type"],
                data["create_time"],
                data.get("error_type", ""),
                data.get("traceback", ""),
                data.get("user_info_type", ""),
                data.get("user_info_value", ""),
                data.get("info_category", ""),
                data.get("skill_name", ""),
                data.get("skill_description", ""),
                data.get("skill_params", "")
            ))
            
            capsule_id = cursor.lastrowid
            conn.commit()
            capsule_logger.info(
                f"Capsule saved successfully | ID: {capsule_id} | Agent: {data['agent_id']} | "
                f"Type: {data['capsule_type']} | Version: {data['schema_version']}"
            )
            return capsule_id
        
        except sqlite3.IntegrityError:
            capsule_logger.warning(f"Capsule already exists, skip saving | Agent: {capsule.agent_id}")
            return -1
        except Exception as e:
            capsule_logger.error(f"Failed to save capsule: {str(e)}", exc_info=True)
            return -1
        finally:
            conn.close()

    def get_capsules_by_agent(
        self, 
        agent_id: str, 
        limit: int = 10, 
        capsule_type: Optional[str] = None
    ) -> List[Dict]:
        """
        Query capsules for specified Agent
        :param agent_id: Agent ID
        :param limit: Return count limit
        :param capsule_type: Capsule type (None=all, experience/error/user_info/skill=specified type)
        :return: List of capsule dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            if capsule_type:
                cursor.execute('''
                SELECT id, schema_version, agent_id, content, capsule_type, create_time, error_type, traceback,
                       user_info_type, user_info_value, skill_name, skill_description, skill_params
                FROM capsules
                WHERE agent_id = ? AND capsule_type = ?
                ORDER BY create_time DESC
                LIMIT ?
                ''', (agent_id, capsule_type, limit))
            else:
                cursor.execute('''
                SELECT id, schema_version, agent_id, content, capsule_type, create_time, error_type, traceback,
                       user_info_type, user_info_value, skill_name, skill_description, skill_params
                FROM capsules
                WHERE agent_id = ?
                ORDER BY create_time DESC
                LIMIT ?
                ''', (agent_id, limit))
            
            columns = [desc[0] for desc in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            capsule_logger.debug(
                f"Agent capsules queried successfully | Agent: {agent_id} | Count: {len(results)}"
            )
            return results
        
        except Exception as e:
            capsule_logger.error(f"Failed to query agent capsules: {str(e)}", exc_info=True)
            return []
        finally:
            conn.close()

    def get_error_capsules(self, limit: int = 20) -> List[Dict]:
        """
        Query all error capsules (for debugging/review)
        :param limit: Return count limit
        :return: List of error capsule dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            SELECT id, schema_version, agent_id, content, capsule_type, create_time, error_type, traceback
            FROM capsules
            WHERE capsule_type = 'error'
            ORDER BY create_time DESC
            LIMIT ?
            ''', (limit,))
            
            columns = [desc[0] for desc in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            capsule_logger.info(f"Error capsules queried successfully | Count: {len(results)}")
            return results
        
        except Exception as e:
            capsule_logger.error(f"Failed to query error capsules: {str(e)}", exc_info=True)
            return []
        finally:
            conn.close()

    def delete_old_capsules(self, days: int = 30) -> int:
        """
        Clean up expired capsules (keep core experience, clean old errors)
        :param days: Days to keep
        :return: Number of deleted capsules
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cutoff_time = time.time() - (days * 24 * 3600)
            
            cursor.execute('''
            DELETE FROM capsules
            WHERE capsule_type = 'error' AND create_time < ?
            ''', (cutoff_time,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            capsule_logger.info(f"Expired capsules cleaned successfully | Deleted: {deleted_count} | Days kept: {days}")
            return deleted_count
        
        except Exception as e:
            capsule_logger.error(f"Failed to clean expired capsules: {str(e)}", exc_info=True)
            return 0
        finally:
            conn.close()
    
    def save_user_info(self, agent_id: str, info_type: str, info_value: str, info_category: Optional[str] = None) -> int:
        """
        Save user information capsule (name, phone, preferences, plans, etc.)
        :param agent_id: User ID
        :param info_type: Information type (name/phone/preference/intent)
        :param info_value: Information value
        :param info_category: Information category (identity/contact/preference/plan)
        :return: Capsule ID
        """
        capsule = UserCapsule(agent_id, info_type, info_value, info_category)
        return self.save_capsule(capsule)
    
    def get_user_info(self, agent_id: str, info_type: Optional[str] = None, info_category: Optional[str] = None) -> List[Dict]:
        """
        Query user information capsules
        :param agent_id: User ID
        :param info_type: Information type (None=all)
        :param info_category: Information category (None=all)
        :return: List of user information capsules
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            if info_type and info_category:
                cursor.execute('''
                SELECT id, schema_version, agent_id, content, capsule_type, create_time,
                       user_info_type, user_info_value, info_category
                FROM capsules
                WHERE agent_id = ? AND capsule_type = 'user_info' AND user_info_type = ? AND info_category = ?
                ORDER BY create_time DESC
                ''', (agent_id, info_type, info_category))
            elif info_type:
                cursor.execute('''
                SELECT id, schema_version, agent_id, content, capsule_type, create_time,
                       user_info_type, user_info_value, info_category
                FROM capsules
                WHERE agent_id = ? AND capsule_type = 'user_info' AND user_info_type = ?
                ORDER BY create_time DESC
                ''', (agent_id, info_type))
            elif info_category:
                cursor.execute('''
                SELECT id, schema_version, agent_id, content, capsule_type, create_time,
                       user_info_type, user_info_value, info_category
                FROM capsules
                WHERE agent_id = ? AND capsule_type = 'user_info' AND info_category = ?
                ORDER BY create_time DESC
                ''', (agent_id, info_category))
            else:
                cursor.execute('''
                SELECT id, schema_version, agent_id, content, capsule_type, create_time,
                       user_info_type, user_info_value, info_category
                FROM capsules
                WHERE agent_id = ? AND capsule_type = 'user_info'
                ORDER BY create_time DESC
                ''', (agent_id,))
            
            columns = [desc[0] for desc in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            capsule_logger.debug(f"User info queried successfully | Agent: {agent_id} | Count: {len(results)}")
            return results
        
        except Exception as e:
            capsule_logger.error(f"Failed to query user info: {str(e)}", exc_info=True)
            return []
        finally:
            conn.close()
    
    def get_latest(self, user_id: str, category: str) -> Optional[str]:
        """
        Get user's latest valid data
        
        :param user_id: User ID
        :param category: Information category
        :return: Latest data value, returns "Not recorded" if not exists
        """
        capsules = self.get_user_info(user_id, info_category=category)
        if capsules:
            return capsules[0].get("user_info_value", "")
        return "Not recorded"
    
    def save_skill(self, agent_id: str, skill_name: str, skill_description: str, skill_params: Optional[Dict] = None) -> int:
        """
        Save skill capsule (conversation, memory retrieval, sensitive detection, etc.)
        :param agent_id: Agent ID
        :param skill_name: Skill name
        :param skill_description: Skill description
        :param skill_params: Skill parameters
        :return: Capsule ID
        """
        capsule = SkillCapsule(agent_id, skill_name, skill_description, skill_params)
        return self.save_capsule(capsule)
    
    def get_skills(self, agent_id: str, skill_name: Optional[str] = None) -> List[Dict]:
        """
        Query skill capsules
        :param agent_id: Agent ID
        :param skill_name: Skill name (None=all)
        :return: List of skill capsules
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            if skill_name:
                cursor.execute('''
                SELECT id, schema_version, agent_id, content, capsule_type, create_time,
                       skill_name, skill_description, skill_params
                FROM capsules
                WHERE agent_id = ? AND capsule_type = 'skill' AND skill_name = ?
                ORDER BY create_time DESC
                ''', (agent_id, skill_name))
            else:
                cursor.execute('''
                SELECT id, schema_version, agent_id, content, capsule_type, create_time,
                       skill_name, skill_description, skill_params
                FROM capsules
                WHERE agent_id = ? AND capsule_type = 'skill'
                ORDER BY create_time DESC
                ''', (agent_id,))
            
            columns = [desc[0] for desc in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            capsule_logger.debug(f"Skill capsules queried successfully | Agent: {agent_id} | Count: {len(results)}")
            return results
        
        except Exception as e:
            capsule_logger.error(f"Failed to query skill capsules: {str(e)}", exc_info=True)
            return []
        finally:
            conn.close()

    def migrate_capsules(self, target_version: str = "1.0"):
        """
        [Reserved] Capsule version migration (handle future structure changes)
        :param target_version: Target version
        """
        capsule_logger.info(f"Starting capsule version migration | Target version: {target_version}")
        capsule_logger.info(f"Capsule version migration completed | Current version: {target_version}")

capsule_manager = CapsuleManager()

if __name__ == "__main__":
    print("=== Capsule Manager Test ===")
    
    test_agent_capsule = AgentCapsule(
        agent_id="test_agent_001",
        content="Successfully completed task: helped user check weather",
        capsule_type="experience"
    )
    test_error_capsule = ErrorCapsule(
        agent_id="test_agent_001",
        error_msg="Network connection timeout",
        error_type="NetworkError",
        traceback="Traceback (most recent call last):\n  ..."
    )
