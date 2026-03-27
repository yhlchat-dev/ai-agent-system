#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库字段修复脚本
功能：为所有表添加缺失的 user_id、is_archived 字段
"""

import sqlite3
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

def fix_database_fields():
    """修复数据库缺失字段"""
    print("=" * 60)
    print("🔧 数据库字段修复脚本")
    print("=" * 60)
    
    db_files = [
        "data/default/long_term.db",
        "data/agent_brain/capsules.db",
        "data/temp_memory.db"
    ]
    
    for db_file in db_files:
        db_path = PROJECT_ROOT / db_file
        if not db_path.exists():
            print(f"\n⏭️ 跳过: {db_file} (不存在)")
            continue
        
        print(f"\n📊 处理: {db_file}")
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # 获取所有表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [t[0] for t in cursor.fetchall()]
        
        for table in tables:
            if table == "sqlite_sequence":
                continue
            
            # 获取表结构
            cursor.execute(f"PRAGMA table_info({table})")
            columns = {row[1] for row in cursor.fetchall()}
            
            # 添加 user_id 字段
            if "user_id" not in columns:
                try:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN user_id TEXT DEFAULT 'default'")
                    print(f"   ✅ {table}: 添加 user_id 字段")
                except Exception as e:
                    print(f"   ⚠️ {table}: user_id 字段添加失败 - {e}")
            else:
                print(f"   ✓ {table}: user_id 字段已存在")
            
            # 添加 is_archived 字段
            if "is_archived" not in columns:
                try:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN is_archived INTEGER DEFAULT 0")
                    print(f"   ✅ {table}: 添加 is_archived 字段")
                except Exception as e:
                    print(f"   ⚠️ {table}: is_archived 字段添加失败 - {e}")
            else:
                print(f"   ✓ {table}: is_archived 字段已存在")
        
        conn.commit()
        conn.close()
    
    print("\n" + "=" * 60)
    print("✅ 数据库字段修复完成！")
    print("=" * 60)

if __name__ == "__main__":
    fix_database_fields()
