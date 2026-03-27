#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""简单功能验证"""

import sys
sys.path.insert(0, "D:\\Agent")

print("=" * 60)
print("🧪 简单功能验证")
print("=" * 60)

# 1. 测试数据库
print("\n1. 测试数据库连接...")
try:
    import sqlite3
    conn = sqlite3.connect("data/default/long_term.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print(f"   ✅ 数据库表: {[t[0] for t in tables]}")
    conn.close()
except Exception as e:
    print(f"   ❌ 数据库错误: {e}")

# 2. 测试意图识别
print("\n2. 测试意图识别...")
try:
    from core.utils.intent_recognizer import recognize_save_intent
    result = recognize_save_intent("我叫张三")
    print(f"   ✅ 保存意图: {result}")
except Exception as e:
    print(f"   ❌ 意图识别错误: {e}")

# 3. 测试敏感检测
print("\n3. 测试敏感检测...")
try:
    from core.utils.sensitive_check import detect_sensitive
    result = detect_sensitive("13800138000")
    print(f"   ✅ 敏感检测: {result}")
except Exception as e:
    print(f"   ❌ 敏感检测错误: {e}")

# 4. 测试长期记忆
print("\n4. 测试长期记忆...")
try:
    from core.memory.long_term_memory import LongTermMemory
    ltm = LongTermMemory(user_id='test', data_dir='data')
    ltm.save_habit('test', 'name', '测试用户')
    result = ltm.get_habit('test', 'name')
    print(f"   ✅ 长期记忆: {result}")
except Exception as e:
    print(f"   ❌ 长期记忆错误: {e}")

# 5. 测试胶囊系统
print("\n5. 测试胶囊系统...")
try:
    from core.capsules.capsule_manager import CapsuleManager
    cm = CapsuleManager()
    cm.save_user_info('test', 'name', '测试用户', 'identity')
    result = cm.get_latest('test', 'identity')
    print(f"   ✅ 胶囊系统: {result}")
except Exception as e:
    print(f"   ❌ 胶囊系统错误: {e}")

print("\n" + "=" * 60)
print("✅ 验证完成！")
print("=" * 60)
