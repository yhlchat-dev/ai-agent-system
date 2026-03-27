import csv
import time
from pathlib import Path
from infra.config import DATA_DIR

f = DATA_DIR / 'behavior_log.csv'
f.parent.mkdir(exist_ok=True)
with open(f, 'w', newline='', encoding='utf-8') as fp:
    writer = csv.writer(fp)
    writer.writerow(['timestamp', 'behavior_type', 'value', 'user_id'])
    now = time.time()
    types = ['聊天', '任务', '探索', '工具']
    for i in range(100):
        for t in types:
            writer.writerow([now - i*60, t, 50 + (i % 50), 'default'])
print('模拟数据已生成，包含多种行为类型')