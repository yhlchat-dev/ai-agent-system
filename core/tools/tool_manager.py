#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Tool Manager: Unified dispatch for all split tools/adapters (simplified version)
"""
import json
import os
import time
import threading
import queue
import sqlite3
from pathlib import Path
from datetime import datetime

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    from utils.security import decrypt_data, encrypt_data
    SECURITY_AVAILABLE = True
except ImportError:
    SECURITY_AVAILABLE = False
    encrypt_data = decrypt_data = None

try:
    from core.cognition.curiosity_core import CuriosityCore
    CURIOSITY_AVAILABLE = True
except ImportError:
    CURIOSITY_AVAILABLE = False
    CuriosityCore = None

try:
    from core.capsules.capsule_manager import CapsuleManager
    CAPSULE_AVAILABLE = True
except ImportError:
    CAPSULE_AVAILABLE = False
    CapsuleManager = None

try:
    import pygetwindow as gw
    PYGETWINDOW_AVAILABLE = True
except ImportError:
    PYGETWINDOW_AVAILABLE = False
    gw = None

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    pyautogui = None

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None

try:
    import mss
    MSS_AVAILABLE = True
except ImportError:
    MSS_AVAILABLE = False
    mss = None

from infra.config import DATA_DIR

from core.tools.adapters import (
    TokenBucket, BaseAPIAdapter,
    WeatherAdapter, WeatherAPIAdapter,
    EmailAdapter, FeishuRobotAdapter
)

try:
    from core.tools.system_tools import (
        WindowEvent, find_window, find_control, click, type_text, get_text, focus_window,
        _window_monitor_loop, _start_window_monitor, _stop_window_monitor, _get_window_events,
        list_processes, list_windows, take_screenshot, activate_window, _type_text, _press_hotkey
    )
except Exception:
    WindowEvent = object
    def find_window(*a, **k): return {"success": False, "result": None, "error": "system_tools_not_available"}
    def find_control(*a, **k): return {"success": False, "result": None, "error": "system_tools_not_available"}
    def click(*a, **k): return {"success": False, "result": None, "error": "system_tools_not_available"}
    def type_text(*a, **k): return {"success": False, "result": None, "error": "system_tools_not_available"}
    def get_text(*a, **k): return {"success": False, "result": None, "error": "system_tools_not_available"}
    def focus_window(*a, **k): return {"success": False, "result": None, "error": "system_tools_not_available"}
    def _window_monitor_loop(*a, **k): return None
    def _start_window_monitor(*a, **k): return {"success": False, "result": None, "error": "system_tools_not_available"}
    def _stop_window_monitor(*a, **k): return {"success": False, "result": None, "error": "system_tools_not_available"}
    def _get_window_events(*a, **k): return {"success": True, "result": [], "error": None}
    def list_processes(*a, **k): return {"success": True, "result": [], "error": None}
    def list_windows(*a, **k): return {"success": True, "result": [], "error": None}
    def take_screenshot(*a, **k): return {"success": False, "result": None, "error": "system_tools_not_available"}
    def activate_window(*a, **k): return {"success": False, "result": None, "error": "system_tools_not_available"}
    def _type_text(*a, **k): return None
    def _press_hotkey(*a, **k): return None

try:
    from core.tools.file_tools import (
        register_file, search_files, list_files, read_file, write_file,
        save_custom_data, search_custom_storage
    )
except Exception:
    def register_file(*a, **k): return {"success": False, "result": None, "error": "file_tools_not_available"}
    def search_files(*a, **k): return {"success": True, "result": [], "error": None}
    def list_files(*a, **k): return {"success": True, "result": [], "error": None}
    def read_file(*a, **k): return {"success": False, "result": None, "error": "file_tools_not_available"}
    def write_file(*a, **k): return {"success": False, "result": None, "error": "file_tools_not_available"}
    def save_custom_data(*a, **k): return {"success": False, "result": None, "error": "file_tools_not_available"}
    def search_custom_storage(*a, **k): return {"success": True, "result": [], "error": None}

try:
    from core.tools.patrol_tools import (
        patrol_recent, patrol_facts, patrol_knowledge,
        capsule_search, capsule_add, capsule_update
    )
except Exception:
    def patrol_recent(*a, **k): return {"success": True, "result": [], "error": None}
    def patrol_facts(*a, **k): return {"success": True, "result": [], "error": None}
    def patrol_knowledge(*a, **k): return {"success": True, "result": [], "error": None}
    def capsule_search(*a, **k): return {"success": True, "result": [], "error": None}
    def capsule_add(*a, **k): return {"success": False, "result": None, "error": "patrol_tools_not_available"}
    def capsule_update(*a, **k): return {"success": False, "result": None, "error": "patrol_tools_not_available"}

class ToolManager:
    """Tool Manager Core Class: Unified dispatch for all split tools/adapters"""
    def __init__(self, data_dir=None, security=None, curiosity_hook=None):
        if data_dir is None:
            data_dir = DATA_DIR
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

        self.security = security
        self.curiosity = curiosity_hook if curiosity_hook else (
            CuriosityCore(data_dir=DATA_DIR) if CURIOSITY_AVAILABLE else None
        )

        self.tools = {}
        self.adapters = {}
        self.sub_agents = {}
        
        self.forbidden_areas = []
        self._load_forbidden_areas()

        if CAPSULE_AVAILABLE:
            self.capsule_manager = CapsuleManager(data_dir=self.data_dir)
        else:
            self.capsule_manager = None
        
        self._init_file_database()
        self._load_adapter_config()
        self._register_builtin_tools()

        self._window_monitor_thread = None
        self._window_events = queue.Queue()
        self._monitor_running = False
        self._last_window_set = set()

    def _load_forbidden_areas(self):
        """Load user-configured forbidden operation areas"""
        self.forbidden_areas = []
        try:
            from core.user.user_data import UserData
            user_data = UserData()
            self.forbidden_areas = user_data.get_forbidden_areas()
        except Exception as e:
            print(f"[ToolManager] Failed to load forbidden areas: {e}")

    def _init_file_database(self):
        """Initialize file index database"""
        try:
            conn = sqlite3.connect(self.data_dir / "file_index.db")
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT UNIQUE,
                    filename TEXT,
                    tags TEXT,
                    description TEXT,
                    created_at REAL,
                    user_id TEXT
                )
            ''')
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[ToolManager] Failed to initialize file database: {e}")

    def is_point_allowed(self, x: int, y: int) -> bool:
        """Check if coordinates are in forbidden operation area"""
        for area in self.forbidden_areas:
            if (area.get('x1', 0) <= x <= area.get('x2', 0) and 
                area.get('y1', 0) <= y <= area.get('y2', 0)):
                return False
        return True

    def _load_adapter_config(self):
        """Load API adapter config"""
        config_file = self.data_dir / 'adapter_config.json'
        
        if not config_file.exists():
            default_config = {
                "weather": {"api_key": "", "rate_limit": 60, "allowed_users": ["*"]},
                "weatherapi": {"api_key": "", "rate_limit": 60, "allowed_users": ["*"]},
                "email": {
                    "smtp_server": "smtp.gmail.com", 
                    "smtp_port": 587,
                    "username": "", 
                    "password": "", 
                    "rate_limit": 10, "allowed_users": ["*"]
                },
                "feishu": {"webhook_url": "", "rate_limit": 10, "allowed_users": ["*"]}
            }
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)

        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                raw_config = json.load(f)
        except Exception as e:
            print(f"[ToolManager] Failed to load adapter config: {e}")
            raw_config = {}

        for name, cfg in raw_config.items():
            adapter_class = self._get_adapter_class(name)
            if adapter_class:
                rate_limit = cfg.get('rate_limit', 60)
                bucket = TokenBucket(rate_limit / 60, rate_limit)
                adapter = adapter_class(name, cfg, security=self.security)
                
                self.adapters[name] = {
                    'instance': adapter,
                    'bucket': bucket,
                    'allowed_users': cfg.get('allowed_users', ['*'])
                }

    def _get_adapter_class(self, name):
        """Get adapter class"""
        adapter_map = {
            'weather': WeatherAdapter,
            'weatherapi': WeatherAPIAdapter,
            'email': EmailAdapter,
            'feishu': FeishuRobotAdapter
        }
        return adapter_map.get(name)

    def _register_builtin_tools(self):
        """Register all split built-in tools"""
        self.register_tool(
            name="register_file",
            func=lambda **kwargs: register_file(data_dir=self.data_dir,** kwargs),
            description="Copy file to Agent storage and record metadata",
            parameters={"src_path": "Source file path", "tags": "Tags", "description": "Description", "user_id": "User ID"}
        )
        self.register_tool(
            name="search_files",
            func=lambda **kwargs: search_files(data_dir=self.data_dir, **kwargs),
            description="Search stored files by tags or description",
            parameters={"query": "Search keyword", "tag_only": "Search tags only"}
        )
        self.register_tool(
            name="list_files",
            func=lambda **kwargs: list_files(data_dir=self.data_dir, **kwargs),
            description="List all stored files",
            parameters={}
        )

        self.register_tool(
            name="type_text",
            func=_type_text,
            description="Simulate keyboard text input",
            parameters={"text": "Text to input", "interval": "Key interval"}
        )
        self.register_tool(
            name="press_hotkey",
            func=_press_hotkey,
            description="Simulate keyboard hotkey",
            parameters={"keys": "Hotkey string"}
        )

        self.register_tool(
            name="read_file",
            func=read_file,
            description="Read text file content",
            parameters={"file_path": "File path"}
        )
        self.register_tool(
            name="write_file",
            func=write_file,
            description="Write content to file",
            parameters={"file_path": "Target path", "content": "Content"}
        )

        self.register_tool(
            name="summarize_text",
            func=lambda text: f"[Simulated summary] {text[:50]}...",
            description="Summarize text",
            parameters={"text": "Text to summarize"}
        )
        self.register_tool(
            name="search_web",
            func=lambda query: f"[Simulated] Search result for '{query}'",
            description="Search web resources",
            parameters={"query": "Search keyword"}
        )
        self.register_tool(
            name="get_current_time",
            func=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            description="Get current date and time",
            parameters={}
        )

        self.register_tool(
            name="patrol_recent",
            func=lambda **kwargs: patrol_recent(data_dir=self.data_dir, **kwargs),
            description="Check conversation summary for last N days",
            parameters={"days": "Number of days", "user_id": "User ID", "max_results": "Max results"}
        )
        self.register_tool(
            name="patrol_facts",
            func=lambda **kwargs: patrol_facts(data_dir=self.data_dir, **kwargs),
            description="Search facts, preferences, habits",
            parameters={"keywords": "Keywords", "user_id": "User ID", "max_results": "Max results"}
        )
        self.register_tool(
            name="patrol_knowledge",
            func=patrol_knowledge,
            description="Search in personal notes",
            parameters={"query": "Query string", "user_id": "User ID", "max_results": "Max results"}
        )

        if self.capsule_manager:
            self.register_tool(
                name="capsule_search",
                func=lambda **kwargs: capsule_search(capsule_manager=self.capsule_manager, **kwargs),
                description="Search experience capsules by question",
                parameters={"query": "User question", "user_id": "User ID", "top_k": "Return count"}
            )
            self.register_tool(
                name="capsule_add",
                func=lambda **kwargs: capsule_add(capsule_manager=self.capsule_manager, **kwargs),
                description="Add new experience capsule",
                parameters={"problem": "Problem", "solution": "Solution", "tags": "Tags", "creator": "Creator"}
            )
            self.register_tool(
                name="capsule_update",
                func=lambda **kwargs: capsule_update(capsule_manager=self.capsule_manager, **kwargs),
                description="Update capsule usage result",
                parameters={"capsule_id": "Capsule ID", "success": "Whether successful"}
            )

        self.register_tool(
            name="activate_window",
            func=activate_window,
            description="Activate window",
            parameters={"title_substring": "Window title", "exact": "Exact match"}
        )
        self.register_tool(
            name="list_windows",
            func=list_windows,
            description="Get all visible window list",
            parameters={}
        )
        self.register_tool(
            name="send_feishu_message",
            func=self._send_feishu_message,
            description="Send Feishu message",
            parameters={"message": "Message content"}
        )
        self.register_tool(
            name="list_processes",
            func=list_processes,
            description="Get current system process list",
            parameters={}
        )
        self.register_tool(
            name="take_screenshot",
            func=take_screenshot,
            description="Take screenshot, return image file path",
            parameters={}
        )
        self.register_tool(
            name="start_window_monitor",
            func=_start_window_monitor,
            description="Start window change monitor (background thread)",
            parameters={}
        )
        self.register_tool(
            name="stop_window_monitor",
            func=_stop_window_monitor,
            description="Stop window monitor",
            parameters={}
        )
        self.register_tool(
            name="get_window_events",
            func=_get_window_events,
            description="Get window change events since last query",
            parameters={}
        )

        self.register_tool(
            name="save_custom_data",
            func=lambda **kwargs: save_custom_data(data_dir=self.data_dir, **kwargs),
            description="Save text or attachment to custom category directory",
            parameters={"category": "Category name", "content": "Text content", "tags": "Tags", "attachment": "Attachment path"}
        )
        self.register_tool(
            name="search_custom_storage",
            func=lambda **kwargs: search_custom_storage(data_dir=self.data_dir, **kwargs),
            description="Search custom stored data",
            parameters={"category": "Category", "query": "Keyword", "limit": "Return count"}
        )

    def register_tool(self, name, func, description, parameters):
        """Register tool (core method)"""
        self.tools[name] = {
            "func": func,
            "description": description,
            "parameters": parameters
        }

    def _send_feishu_message(self, message, **kwargs):
        """Send Feishu message (adapter call)"""
        return self._call_adapter('feishu', None, message=message)

    def call_tool(self, tool_name, user_id=None, **kwargs):
        """Unified tool call entry"""
        if tool_name in self.adapters:
            return self._call_adapter(tool_name, user_id, **kwargs)
        elif tool_name in self.tools:
            return self._call_regular_tool(tool_name, **kwargs)
        else:
            error_msg = f"Unknown tool: {tool_name}"
            if self.curiosity:
                self.curiosity.explore(f"Unknown tool call: {tool_name}", context=kwargs)
            return {"success": False, "result": None, "error": error_msg}

    def _call_adapter(self, name, user_id, **kwargs):
        """Call API adapter"""
        adapter_info = self.adapters.get(name)
        if not adapter_info:
            return {"success": False, "result": None, "error": f"Adapter {name} not found"}

        allowed = adapter_info['allowed_users']
        if '*' not in allowed and user_id not in allowed:
            return {"success": False, "result": None, "error": "Permission denied"}

        if not adapter_info['bucket'].consume():
            return {"success": False, "result": None, "error": "Rate limit exceeded"}

        try:
            result = adapter_info['instance'].call(**kwargs)
            return result
        except Exception as e:
            error_msg = str(e)
            if self.curiosity:
                self.curiosity.explore(f"Adapter call failed {name}: {error_msg}", context=kwargs)
            return {"success": False, "result": None, "error": error_msg}

    def _call_regular_tool(self, name, **kwargs):
        """Call built-in tool"""
        tool = self.tools.get(name)
        if not tool:
            return {"success": False, "result": None, "error": f"Tool {name} not found"}

        try:
            result = tool["func"](** kwargs)
            
            if isinstance(result, dict) and "success" in result:
                return result
            else:
                return {"success": True, "result": result, "error": None}
                
        except Exception as e:
            error_msg = str(e)
            if self.curiosity:
                 self.curiosity.explore(f"Regular tool call failed {name}: {error_msg}", kwargs)
            return {"success": False, "result": None, "error": error_msg}

if __name__ == "__main__":
    tm = ToolManager()
    
    print("=== Basic Tool Tests ===")
    print("Current time:", tm.call_tool("get_current_time"))
    print("Text summary:", tm.call_tool("summarize_text", text="This is a test text to verify the summary function works properly"))
    
    print("\n=== Dependency Check ===")
    print(f"requests: {REQUESTS_AVAILABLE}")
    print(f"pygetwindow: {PYGETWINDOW_AVAILABLE}")
    print(f"pyautogui: {PYAUTOGUI_AVAILABLE}")
    print(f"psutil: {PSUTIL_AVAILABLE}")
    print(f"mss: {MSS_AVAILABLE}")
    print(f"security: {SECURITY_AVAILABLE}")
    print(f"curiosity: {CURIOSITY_AVAILABLE}")
    print(f"capsule: {CAPSULE_AVAILABLE}")
