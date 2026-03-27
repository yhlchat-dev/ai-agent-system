import sqlite3
from pathlib import Path

base = Path("D:/Agent/data/default/")

# 查看 short_term.db
short_db = base / "short_term.db"
if short_db.exists():
    conn = sqlite3.connect(str(short_db))
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    print("short_term.db tables:", [row[0] for row in cursor.fetchall()])
    conn.close()
else:
    print("short_term.db not found")

# 查看 tasks.db
tasks_db = base / "tasks.db"
if tasks_db.exists():
    conn = sqlite3.connect(str(tasks_db))
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    print("tasks.db tables:", [row[0] for row in cursor.fetchall()])
    conn.close()
else:
    print("tasks.db not found")

# 查看 long_term.db
long_db = base / "long_term.db"
if long_db.exists():
    conn = sqlite3.connect(str(long_db))
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    print("long_term.db tables:", [row[0] for row in cursor.fetchall()])
    conn.close()
else:
    print("long_term.db not found")

# 查看 curiosity_log.json
log_file = base / "curiosity_log.json"
print("curiosity_log.json exists:", log_file.exists())