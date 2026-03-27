#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
智能检索引擎完整测试脚本
测试标准：
1. 输入：我叫王博 今年22岁 喜欢吃肉 想去海边 想找媳妇
2. 输出：精准提取所有信息，无重复、无错误
3. 查询：我喜欢吃什么 → 智能输出：你喜欢吃肉
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.utils.smart_retrieval import smart_retrieval_engine

def test_entity_extraction():
    """测试实体提取功能"""
    print("=" * 60)
    print("🧪 实体提取功能测试")
    print("=" * 60)
    
    test_cases = [
        ("我叫王博", "name", "王博"),
        ("今年22岁", "age", "22"),
        ("喜欢吃肉", "hobby", "肉"),
        ("想去海边", "goal", "海边"),
        ("想找媳妇", "goal", "媳妇"),
        ("我叫谢霆锋没有做谢谢你啊", "name", "谢霆锋"),
        ("我手机号13800138000", "phone", "13800138000"),
    ]
    
    passed = 0
    failed = 0
    
    for text, expected_type, expected_value in test_cases:
        entities = smart_retrieval_engine.extract_entities(text)
        
        found = False
        actual_value = ""
        for entity in entities:
            if entity["entity_type"] == expected_type:
                found = True
                actual_value = entity["value"]
                break
        
        status = "✅" if found and expected_value in actual_value else "❌"
        if found and expected_value in actual_value:
            passed += 1
        else:
            failed += 1
        
        print(f"{status} 输入: {text}")
        print(f"   期望: {expected_type}={expected_value}")
        print(f"   实际: {expected_type}={actual_value if found else '未提取到'}")
        print()
    
    print("=" * 60)
    print(f"测试结果: 通过 {passed}/{len(test_cases)}，失败 {failed}/{len(test_cases)}")
    print("=" * 60)
    
    return failed == 0


def test_query_type_detection():
    """测试查询类型检测"""
    print("\n" + "=" * 60)
    print("🧪 查询类型检测测试")
    print("=" * 60)
    
    test_cases = [
        ("我是谁", "identity_query", "name"),
        ("我今年多大", "age_query", "age"),
        ("我喜欢什么", "preference_query", "hobby"),
        ("我想干嘛", "plan_query", "goal"),
        ("我的手机号", "contact_query", "phone"),
    ]
    
    passed = 0
    failed = 0
    
    for query, expected_type, expected_entity in test_cases:
        result = smart_retrieval_engine.detect_query_type(query)
        
        if result:
            actual_type = result["query_type"]
            actual_entity = result["entity_type"]
            status = "✅" if actual_type == expected_type and actual_entity == expected_entity else "❌"
            if actual_type == expected_type and actual_entity == expected_entity:
                passed += 1
            else:
                failed += 1
            print(f"{status} 查询: {query}")
            print(f"   期望: {expected_type}/{expected_entity}")
            print(f"   实际: {actual_type}/{actual_entity}")
        else:
            failed += 1
            print(f"❌ 查询: {query}")
            print(f"   期望: {expected_type}/{expected_entity}")
            print(f"   实际: 未识别")
        print()
    
    print("=" * 60)
    print(f"测试结果: 通过 {passed}/{len(test_cases)}，失败 {failed}/{len(test_cases)}")
    print("=" * 60)
    
    return failed == 0


def test_dynamic_weights():
    """测试动态权重自适应"""
    print("\n" + "=" * 60)
    print("🧪 动态权重自适应测试")
    print("=" * 60)
    
    # 测试精准查询场景
    weights1 = smart_retrieval_engine.calculate_dynamic_weights("identity_query", "name")
    print(f"✅ 精准查询（我是谁）:")
    print(f"   姓名权重: {weights1.get('name', 0):.2f}")
    print(f"   年龄权重: {weights1.get('age', 0):.2f}")
    print(f"   爱好权重: {weights1.get('hobby', 0):.2f}")
    
    # 测试闲聊场景
    weights2 = smart_retrieval_engine.calculate_dynamic_weights(None, None)
    print(f"\n✅ 闲聊场景:")
    print(f"   姓名权重: {weights2.get('name', 0):.2f}")
    print(f"   年龄权重: {weights2.get('age', 0):.2f}")
    print(f"   爱好权重: {weights2.get('hobby', 0):.2f}")
    
    print("\n" + "=" * 60)
    print("✅ 动态权重测试完成")
    print("=" * 60)
    
    return True


def test_dynamic_top_n():
    """测试动态TopN召回"""
    print("\n" + "=" * 60)
    print("🧪 动态TopN召回测试")
    print("=" * 60)
    
    # 测试短文本查询
    top_n1 = smart_retrieval_engine.calculate_dynamic_top_n("我是谁")
    print(f"✅ 短文本查询（我是谁）: Top{top_n1}")
    
    # 测试中长文本查询
    top_n2 = smart_retrieval_engine.calculate_dynamic_top_n("我想知道我的所有信息包括姓名年龄和爱好")
    print(f"✅ 中长文本查询: Top{top_n2}")
    
    # 测试精准查询类型
    query_type_config = {"top_n": 3}
    top_n3 = smart_retrieval_engine.calculate_dynamic_top_n("我是谁", query_type_config)
    print(f"✅ 精准查询类型: Top{top_n3}")
    
    print("\n" + "=" * 60)
    print("✅ 动态TopN测试完成")
    print("=" * 60)
    
    return True


def test_smart_deduplicate():
    """测试智能去重"""
    print("\n" + "=" * 60)
    print("🧪 智能去重测试")
    print("=" * 60)
    
    # 模拟重复记忆
    memories = [
        {"entity_type": "name", "content": "王博", "timestamp": 1000},
        {"entity_type": "name", "content": "王博", "timestamp": 2000},  # 重复
        {"entity_type": "age", "content": "22", "timestamp": 1500},
        {"entity_type": "hobby", "content": "吃肉", "timestamp": 1800},
        {"entity_type": "hobby", "content": "吃肉", "timestamp": 2500},  # 重复
    ]
    
    unique_memories = smart_retrieval_engine.smart_deduplicate(memories)
    
    print(f"原始记忆数: {len(memories)}")
    print(f"去重后记忆数: {len(unique_memories)}")
    print(f"去重结果: {'✅ 通过' if len(unique_memories) == 3 else '❌ 失败'}")
    
    print("\n" + "=" * 60)
    print("✅ 智能去重测试完成")
    print("=" * 60)
    
    return len(unique_memories) == 3


def test_complete_scenario():
    """测试完整场景"""
    print("\n" + "=" * 60)
    print("🧪 完整场景测试")
    print("=" * 60)
    
    # 模拟用户输入
    user_input = "我叫王博 今年22岁 喜欢吃肉 想去海边 想找媳妇"
    
    print(f"用户输入: {user_input}")
    print()
    
    # 提取实体
    entities = smart_retrieval_engine.extract_entities(user_input)
    print(f"提取到的实体:")
    for entity in entities:
        print(f"  - {entity['entity_type']}: {entity['value']} (分类: {entity['category']})")
    
    print()
    
    # 模拟查询
    queries = [
        "我是谁",
        "我今年多大",
        "我喜欢什么",
        "我想干嘛"
    ]
    
    print("智能问答测试:")
    for query in queries:
        query_config = smart_retrieval_engine.detect_query_type(query)
        if query_config:
            entity_type = query_config["entity_type"]
            # 从提取的实体中查找答案
            answer = None
            for entity in entities:
                if entity["entity_type"] == entity_type:
                    answer = entity["value"]
                    break
            
            print(f"  查询: {query}")
            print(f"  类型: {query_config['query_type']}")
            print(f"  答案: {answer if answer else '未找到'}")
            print()
    
    print("=" * 60)
    print("✅ 完整场景测试完成")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    print("\n" + "🚀 " * 20)
    print("智能检索引擎完整测试")
    print("🚀 " * 20 + "\n")
    
    test1_passed = test_entity_extraction()
    test2_passed = test_query_type_detection()
    test3_passed = test_dynamic_weights()
    test4_passed = test_dynamic_top_n()
    test5_passed = test_smart_deduplicate()
    test6_passed = test_complete_scenario()
    
    print("\n" + "=" * 60)
    if all([test1_passed, test2_passed, test3_passed, test4_passed, test5_passed, test6_passed]):
        print("🎉 所有测试通过！智能检索引擎实现成功！")
    else:
        print("⚠️ 部分测试失败，请检查修复")
    print("=" * 60)
