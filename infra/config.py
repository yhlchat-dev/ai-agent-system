#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Centralized Configuration Management Module
All configurable items are unified here for easy maintenance and customization.
Forces use of environment variables for improved security.
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent

DATA_DIR_ENV = os.getenv('AGENT_DATA_DIR')
if DATA_DIR_ENV:
    DATA_DIR = Path(DATA_DIR_ENV)
    DATA_DIR = Path("./data")
    DATA_DIR.mkdir(exist_ok=True)
else:
    if sys.platform == 'win32':
        base = Path(os.environ.get('APPDATA', '')) / 'YourAgent'
    else:
        base = Path.home() / '.youragent'
    DATA_DIR = base / 'data'

SHORT_TERM_DB = DATA_DIR / "short_term_memory.db"
LONG_TERM_DB = DATA_DIR / "long_term.db"
TASKS_DB = DATA_DIR / "tasks.db"
FILE_INDEX_DB = DATA_DIR / "file_index.db"

ERRORS_JSON = DATA_DIR / "errors.json"
CURIOSITY_LOG = DATA_DIR / "curiosity_log.json"
MONITOR_LOG = DATA_DIR / "monitor.log"
BEHAVIOR_LOG = DATA_DIR / "behavior_log.csv"
ADAPTER_CONFIG = DATA_DIR / "adapter_config.json"
CAPSULES_FILE = DATA_DIR / "capsules.json"
RESTART_LOG = BASE_DIR / "restart.log"

ENCRYPT_KEY = os.getenv('ENCRYPT_KEY', 'gAAAAABlZ9Z8Z8Z8Z8Z8Z8Z8Z8Z8Z8Z8Z8Z8Z8Z8Z8Z8Z8Z8Z8Z8Z8Z8Z8=')
if not ENCRYPT_KEY:
    raise ValueError("Must set environment variable ENCRYPT_KEY for data encryption")

IDLE_MOUSE_THRESHOLD = int(os.getenv('IDLE_MOUSE_THRESHOLD', '300'))
IDLE_KEYBOARD_THRESHOLD = int(os.getenv('IDLE_KEYBOARD_THRESHOLD', '300'))
SCREEN_CHANGE_RATIO = float(os.getenv('SCREEN_CHANGE_RATIO', '0.1'))
HANG_THRESHOLD = int(os.getenv('HANG_THRESHOLD', '300'))
COMPRESS_INTERVAL_HOURS = int(os.getenv('COMPRESS_INTERVAL_HOURS', '1'))
ARCHIVE_INTERVAL_DAYS = int(os.getenv('ARCHIVE_INTERVAL_DAYS', '7'))
SHORT_TERM_KEEP = int(os.getenv('SHORT_TERM_KEEP', '100'))
DEFAULT_EXPLORE_LEVEL = int(os.getenv('DEFAULT_EXPLORE_LEVEL', '5'))
SUBAGENT_MAX_WORKERS = int(os.getenv('SUBAGENT_MAX_WORKERS', '5'))
CAPSULE_TOP_K = int(os.getenv('CAPSULE_TOP_K', '5'))
PATROL_MAX_RESULTS = int(os.getenv('PATROL_MAX_RESULTS', '5'))
RECENT_CHAT_LIMIT = int(os.getenv('RECENT_CHAT_LIMIT', '10'))
RECENT_LOG_LIMIT = int(os.getenv('RECENT_LOG_LIMIT', '100'))

DISK_THRESHOLD = int(os.getenv('DISK_THRESHOLD', '90'))
MEM_THRESHOLD_MB = int(os.getenv('MEM_THRESHOLD_MB', '500'))
CPU_THRESHOLD = int(os.getenv('CPU_THRESHOLD', '80'))
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '300'))
ALERT_ENABLED = os.getenv('ALERT_ENABLED', 'false').lower() == 'true'

UI_REFRESH_INTERVAL = int(os.getenv('UI_REFRESH_INTERVAL', '2000'))
CHAT_DISPLAY_LIMIT = int(os.getenv('CHAT_DISPLAY_LIMIT', '10'))
TASK_DISPLAY_LIMIT = int(os.getenv('TASK_DISPLAY_LIMIT', '20'))
MEMORY_DISPLAY_LIMIT = int(os.getenv('MEMORY_DISPLAY_LIMIT', '20'))

REFRESH_INTERVAL_MS = int(os.getenv('REFRESH_INTERVAL_MS', '5000'))
MAX_POINTS_PER_TYPE = int(os.getenv('MAX_POINTS_PER_TYPE', '200'))

SELF_TEST_INTERVAL = int(os.getenv('SELF_TEST_INTERVAL', '30'))

ENABLE_SENSITIVE_CHECK = os.getenv('ENABLE_SENSITIVE_CHECK', 'true').lower() == 'true'
SENSITIVE_ACTION = os.getenv('SENSITIVE_ACTION', 'MASK').upper()

MEMORY_SHORT_TERM_LIMIT = int(os.getenv('MEMORY_SHORT_TERM_LIMIT', '20'))
MEMORY_ARCHIVE_THRESHOLD = float(os.getenv('MEMORY_ARCHIVE_THRESHOLD', '0.8'))
MEMORY_HOT_LIMIT = int(os.getenv('MEMORY_HOT_LIMIT', '50'))
MEMORY_MAX_LIMIT = int(os.getenv('MEMORY_MAX_LIMIT', '1000'))
MEMORY_DECAY_RATE = float(os.getenv('MEMORY_DECAY_RATE', '0.01'))

CURIOSITY_SENSITIVITY = float(os.getenv('CURIOSITY_SENSITIVITY', '0.5'))

CAPSULE_ENABLE_TAGS = os.getenv('CAPSULE_ENABLE_TAGS', 'true').lower() == 'true'
CAPSULE_ENABLE_VERSIONING = os.getenv('CAPSULE_ENABLE_VERSIONING', 'true').lower() == 'true'

def get_user_data_dir(user_id: str) -> Path:
    return DATA_DIR / user_id


import getpass
def get_current_user():
    """Get current logged-in system username"""
    return getpass.getuser()
    
def get_current_user() -> str:
    import getpass
    return getpass.getuser()

CURRENT_USER_DIR = Path(f"./data/{get_current_user()}")    


def init_user_dirs(username: str = None):
    """Automatically create all subdirectories for user (db/vector_store/secure_data etc.)"""
    if username is None:
        username = get_current_user()
    user_dir = get_user_data_dir(username)
    sub_dirs = [
        user_dir / "db",
        user_dir / "vector_store",
        user_dir / "configs",
        user_dir / "logs",
        user_dir / "secure_data",
        user_dir / "backups"
    ]
    for d in sub_dirs:
        d.mkdir(parents=True, exist_ok=True)
    return user_dir


CURRENT_USER_DIR = init_user_dirs()


def get_encrypt_key():
    """Unified encryption key provider, maintains compatibility with existing code"""
    return ENCRYPT_KEY
