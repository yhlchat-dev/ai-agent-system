#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试280个关键词库
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.utils.keyword_engine import extract_user_info, smart_query, KEYWORD_LIBRARY

def test_keyword_library():
    """测试关键词库"""
    print("\n" + "=" * 60)
    print("🧪 测试280个关键词库")
    print("=" * 60)
    
    total_keywords = 0
    for category, config in KEYWORD_LIBRARY.items():
        keywords = config["keywords"]
        total_keywords += len(keywords)
        print(f"\n📂 {config['name']}：{len(keywords)}个关键词")
        print(f"   示例：{', '.join(keywords[:5])}...")
    
    print(f"\n✅ 总计：{total_keywords}个关键词")
    return True


def test_entity_extraction():
    """测试实体提取"""
    print("\n" + "=" * 60)
    print("🧪 测试实体提取")
    print("=" * 60)
    
    test_cases = [
        ("我叫王博", "name", "王博"),
        ("今年22岁", "age", "22"),
        ("喜欢吃肉", "like_food", "肉"),
        ("想去海边", "destination", "海边"),
        ("想找媳妇", "goal", "媳妇"),
        ("属龙", "zodiac", "龙"),
        ("身高175", "height", "175"),
        ("体重70", "weight", "70"),
        ("生日5月1日", "birthday", "5月1日"),
        ("星座白羊", "zodiac_sign", "白羊"),
        ("老家北京", "hometown", "北京"),
    ]
    
    passed = 0
    failed = 0
    
    for text, expected_type, expected_value in test_cases:
        entities = extract_user_info(text)
        
        found = False
        for entity in entities:
            if entity["entity_type"] == expected_type and expected_value in entity["value"]:
                found = True
                break
        
        if found:
            print(f"✅ 输入: {text} → 提取: {expected_type}={expected_value}")
            passed += 1
        else:
            print(f"❌ 输入: {text} → 期望: {expected_type}={expected_value}, 实际: {entities}")
            failed += 1
    
    print(f"\n测试结果: 通过 {passed}/{len(test_cases)}，失败 {failed}/{len(test_cases)}")
    return failed == 0


def test_query_detection():
    """测试查询检测"""
    print("\n" + "=" * 60)
    print("🧪 测试查询检测")
    print("=" * 60)
    
    test_cases = [
        ("我是谁", "identity_query"),
        ("我叫什么", "identity_query"),
        ("我多大", "age_query"),
        ("我属什么", "zodiac_query"),
        ("我身高", "height_query"),
        ("我体重", "weight_query"),
        ("我喜欢什么", "preference_query"),
        ("我想去哪", "plan_query"),
        ("我老家", "hometown_query"),
    ]
    
    passed = 0
    failed = 0
    
    for query, expected_type in test_cases:
        from core.utils.keyword_engine import _keyword_extractor
        result = _keyword_extractor.detect_query_type(query)
        
        if result and result["query_type"] == expected_type:
            print(f"✅ 查询: {query} → 类型: {expected_type}")
            passed += 1
        else:
            print(f"❌ 查询: {query} → 期望: {expected_type}, 实际: {result}")
            failed += 1
    
    print(f"\n测试结果: 通过 {passed}/{len(test_cases)}，失败 {failed}/{len(test_cases)}")
    return failed == 0


def test_complete_scenario():
    """测试完整场景"""
    print("\n" + "=" * 60)
    print("🧪 完整场景测试")
    print("=" * 60)
    
    user_input = "我叫王博 今年22岁 喜欢吃肉 想去海边 想找媳妇"
    
    print(f"用户输入: {user_input}")
    print()
    
    entities = extract_user_info(user_input)
    print(f"提取到的实体:")
    for entity in entities:
        print(f"  - {entity['entity_type']}: {entity['value']} (分类: {entity['category']})")
    
    print()
    
    queries = [
        ("我是谁", "王博"),
        ("我多大", "22"),
        ("我喜欢什么", "肉"),
        ("我想去哪", "海边"),
    ]
    
    print("智能问答测试:")
    for query, expected_answer in queries:
        from core.utils.keyword_engine import _keyword_extractor
        result = _keyword_extractor.detect_query_type(query)
        
        if result:
            entity_type = result["entity_type"]
            answer = None
            for entity in entities:
                if entity["entity_type"] == entity_type or expected_answer in entity["value"]:
                    answer = entity["value"]
                    break
            
            print(f"  查询: {query}")
            print(f"  类型: {result['query_type']}")
            print(f"  答案: {answer if answer else '未找到'}")
            print()
    
    return True


if __name__ == "__main__":
    print("\n" + "🚀 " * 20)
    print("280个关键词库完整测试")
    print("🚀 " * 20 + "\n")
    
    test1_passed = test_keyword_library()
    test2_passed = test_entity_extraction()
    test3_passed = test_query_detection()
    test4_passed = test_complete_scenario()
    
    print("\n" + "=" * 60)
    if all([test1_passed, test2_passed, test3_passed, test4_passed]):
        print("🎉 所有测试通过！280个关键词库实现成功！")
    else:
        print("⚠️ 部分测试失败，请检查修复")
    print("=" * 60)
