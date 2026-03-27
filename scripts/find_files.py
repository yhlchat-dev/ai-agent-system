import os
import re

root_dir = r"D:\Agent" # 你的项目根目录

targets = {
    "class CuriosityCore": [],
    "def search_capsules": []
}

for dirpath, dirnames, filenames in os.walk(root_dir):
    # 跳过 __pycache__ 和 .git 等文件夹
    if '__pycache__' in dirpath or '.git' in dirpath:
        continue
        
    for filename in filenames:
        if filename.endswith('.py'):
            filepath = os.path.join(dirpath, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    for key in targets:
                        if key in content:
                            targets[key].append(filepath)
            except Exception:
                pass

print("🔍 搜索结果：")
for key, files in targets.items():
    print(f"\n包含 '{key}' 的文件:")
    if files:
        for f in files:
            print(f"  -> {f}")
    else:
        print("  -> 未找到")