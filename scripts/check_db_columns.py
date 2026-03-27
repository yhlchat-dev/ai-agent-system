import sqlite3
import os

databases = [
    'data/default/short_term.db',
    'data/default/long_term.db',
    'data/temp_memory.db'
]

for db_path in databases:
    if os.path.exists(db_path):
        print(f'\n=== {db_path} ===')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        for table in tables:
            print(f'表: {table[0]}')
            cursor.execute(f'PRAGMA table_info({table[0]})')
            cols = cursor.fetchall()
            print(f'  列: {[c[1] for c in cols]}')
        conn.close()
    else:
        print(f'{db_path} 不存在')
