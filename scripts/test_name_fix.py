#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
姓名提取修复验证脚本
测试标准：
1. 用户说：我叫谢霆锋没有做谢谢你啊 → 必须提取：谢霆锋
2. 用户问：我叫什么 → 必须回复：你是谢霆锋
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.utils.intent_recognizer import extract_chinese_name, recognize_save_intent

def test_name_extraction():
    """测试姓名提取功能"""
    print("=" * 60)
    print("🧪 姓名提取功能测试")
    print("=" * 60)
    
    test_cases = [
        ("我叫谢霆锋没有做谢谢你啊", "谢霆锋"),
        ("我叫张三", "张三"),
        ("我是李四", "李四"),
        ("我的名字是王五", "王五"),
        ("名字叫赵六啦", "赵六"),
        ("我叫做陈七哦", "陈七"),
        ("我叫ABC", ""),  # 非中文，应该返回空
        ("我叫一个很长很长的名字", "一个很长"),  # 截断到4个字
        ("我是谢霆锋谢谢你啊", "谢霆锋"),  # 停止词截断
    ]
    
    passed = 0
    failed = 0
    
    for text, expected in test_cases:
        result = extract_chinese_name(text)
        status = "✅" if result == expected else "❌"
        if result == expected:
            passed += 1
        else:
            failed += 1
        print(f"{status} 输入: {text}")
        print(f"   期望: {expected}")
        print(f"   实际: {result}")
        print()
    
    print("=" * 60)
    print(f"测试结果: 通过 {passed}/{len(test_cases)}，失败 {failed}/{len(test_cases)}")
    print("=" * 60)
    
    return failed == 0


def test_save_intent():
    """测试保存意图识别"""
    print("\n" + "=" * 60)
    print("🧪 保存意图识别测试")
    print("=" * 60)
    
    test_cases = [
        ("我叫谢霆锋没有做谢谢你啊", True, "谢霆锋"),
        ("我叫什么", False, None),  # 查询问句，不保存
        ("我是谁", False, None),  # 查询问句，不保存
        ("我喜欢吃苹果", True, "苹果"),
        ("我手机号13800138000", True, "13800138000"),
    ]
    
    passed = 0
    failed = 0
    
    for text, should_save, expected_value in test_cases:
        intents = recognize_save_intent(text)
        
        if should_save:
            if intents and len(intents) > 0:
                actual_value = intents[0].get("info_value", "")
                status = "✅" if expected_value in actual_value else "❌"
                if expected_value in actual_value:
                    passed += 1
                else:
                    failed += 1
                print(f"{status} 输入: {text}")
                print(f"   期望保存: {expected_value}")
                print(f"   实际保存: {actual_value}")
            else:
                failed += 1
                print(f"❌ 输入: {text}")
                print(f"   期望保存: {expected_value}")
                print(f"   实际: 未保存")
        else:
            if not intents or len(intents) == 0:
                passed += 1
                print(f"✅ 输入: {text}")
                print(f"   正确跳过保存（查询问句）")
            else:
                failed += 1
                print(f"❌ 输入: {text}")
                print(f"   期望: 不保存")
                print(f"   实际: 保存了 {intents}")
        print()
    
    print("=" * 60)
    print(f"测试结果: 通过 {passed}/{len(test_cases)}，失败 {failed}/{len(test_cases)}")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    print("\n" + "🚀 " * 20)
    print("姓名提取修复验证")
    print("🚀 " * 20 + "\n")
    
    test1_passed = test_name_extraction()
    test2_passed = test_save_intent()
    
    print("\n" + "=" * 60)
    if test1_passed and test2_passed:
        print("🎉 所有测试通过！姓名提取功能修复成功！")
    else:
        print("⚠️ 部分测试失败，请检查修复")
    print("=" * 60)
