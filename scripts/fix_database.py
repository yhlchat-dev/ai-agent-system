#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库自动修复脚本
功能：
1. 删除旧数据库文件
2. 重新初始化表结构
3. 添加缺失字段（user_id, is_archived）
"""

import os
import sqlite3
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent  # 修复：指向项目根目录

DB_FILES = [
    "data/default/long_term.db",
    "data/agent_brain/capsules.db",
    "data/encrypted_memory.db",
    "data/temp_memory.db",
    "media_storage/media_index.db"
]

def backup_and_delete_databases():
    """备份并删除旧数据库"""
    print("=" * 60)
    print("🔧 数据库自动修复脚本")
    print("=" * 60)
    
    for db_file in DB_FILES:
        db_path = PROJECT_ROOT / db_file
        if db_path.exists():
            # 备份
            backup_path = db_path.with_suffix(".db.backup")
            try:
                shutil.copy2(db_path, backup_path)
                print(f"✅ 备份: {db_file} -> {backup_path.name}")
            except Exception as e:
                print(f"⚠️ 备份失败: {db_file} - {e}")
            
            # 删除
            try:
                os.remove(db_path)
                print(f"🗑️ 删除: {db_file}")
            except Exception as e:
                print(f"❌ 删除失败: {db_file} - {e}")
        else:
            print(f"⏭️ 跳过: {db_file} (不存在)")
    
    print("\n✅ 数据库清理完成！")

def init_long_term_db():
    """初始化长期记忆数据库（包含缺失字段）"""
    print("\n" + "=" * 60)
    print("📊 初始化长期记忆数据库")
    print("=" * 60)
    
    db_path = PROJECT_ROOT / "data/default/long_term.db"
    os.makedirs(db_path.parent, exist_ok=True)
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # 创建完整的表结构
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS habits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL DEFAULT 'default',
            habit_type TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp REAL NOT NULL,
            access_count INTEGER DEFAULT 0,
            is_archived INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL DEFAULT 'default',
            timestamp REAL NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            file_path TEXT,
            tags TEXT,
            is_archived INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL DEFAULT 'default',
            content TEXT NOT NULL,
            type TEXT,
            timestamp DATETIME,
            is_archived INTEGER DEFAULT 0
        )
    ''')
    
    # 创建索引
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_habits_user ON habits(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_habits_type ON habits(habit_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_memories_user ON memories(user_id)')
    
    conn.commit()
    conn.close()
    
    print(f"✅ 长期记忆数据库初始化完成: {db_path}")

def init_temp_db():
    """初始化临时记忆数据库"""
    print("\n" + "=" * 60)
    print("📊 初始化临时记忆数据库")
    print("=" * 60)
    
    db_path = PROJECT_ROOT / "data/temp_memory.db"
    os.makedirs(db_path.parent, exist_ok=True)
    
    conn = sqlite3.connect(str(db_path))
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
    
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_temp_user ON temp_memory(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_temp_synced ON temp_memory(is_synced)')
    
    conn.commit()
    conn.close()
    
    print(f"✅ 临时记忆数据库初始化完成: {db_path}")

def init_capsules_db():
    """初始化胶囊数据库"""
    print("\n" + "=" * 60)
    print("📊 初始化胶囊数据库")
    print("=" * 60)
    
    db_path = PROJECT_ROOT / "data/agent_brain/capsules.db"
    os.makedirs(db_path.parent, exist_ok=True)
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_capsules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            info_type TEXT NOT NULL,
            info_value TEXT NOT NULL,
            info_category TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS error_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT,
            error_type TEXT,
            error_message TEXT,
            timestamp REAL,
            level TEXT DEFAULT 'error'
        )
    ''')
    
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_capsules_user ON user_capsules(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_capsules_category ON user_capsules(info_category)')
    
    conn.commit()
    conn.close()
    
    print(f"✅ 胶囊数据库初始化完成: {db_path}")

def main():
    """主函数"""
    print("\n" + "🚀" * 30)
    print("数据库自动修复脚本启动")
    print("🚀" * 30 + "\n")
    
    # 1. 备份并删除旧数据库
    backup_and_delete_databases()
    
    # 2. 初始化所有数据库
    init_long_term_db()
    init_temp_db()
    init_capsules_db()
    
    print("\n" + "=" * 60)
    print("✅ 所有数据库修复完成！")
    print("=" * 60)
    print("\n📝 修复内容：")
    print("  ✅ 删除旧数据库文件（已备份）")
    print("  ✅ 重新初始化表结构")
    print("  ✅ 添加缺失字段（user_id, is_archived）")
    print("  ✅ 创建必要索引")
    print("\n🎉 系统已就绪，可以启动服务！")

if __name__ == "__main__":
    main()
