#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Agent Full-Chain Monitoring UI System (Real Data Version) - Final Performance Optimized Complete Version
Completely resolved UI lag and freezing
Fixed matplotlib memory leak
Background thread data collection, UI never blocks
Reduced refresh frequency, significantly lower CPU usage
Single file, run directly
Features, interface, buttons, shortcuts fully consistent with original version
"""

import sys
import os

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import psutil
import time
import threading
import sqlite3
import schedule
import json
import gc
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from collections import deque

import yaml
import win32gui
import win32con
import win32api

import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

sys.path.insert(0, str(Path(__file__).parent))
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from core.agent.main_agent import AgentCore
    from core.llm.factory import LLMFactory
    CORE_AVAILABLE = True
except Exception as e:
    print(f"Core module loading failed: {e}")
    AgentCore = None
    LLMFactory = None
    CORE_AVAILABLE = False


class Config:
    FLOAT_WIN_SIZE = (320, 280)
    FLOAT_WIN_POS = (100, 100)
    MAIN_WIN_SIZE = (900, 700)
    REFRESH_INTERVAL = 1000
    DB_PATH = "agent_memory.db"
    CLEAR_TIME = "00:00"
    FORBIDDEN_CONFIG = "forbidden_areas.yaml"
    HISTORY_FILE = "data/ui_history.json"
    
    THEMES = {
        "dark": {
            "bg": "#2c3e50",
            "fg": "#ecf0f1",
            "accent": "#3498db",
            "success": "#2ecc71",
            "warning": "#f39c12",
            "danger": "#e74c3c",
            "info": "#9b59b6"
        },
        "light": {
            "bg": "#ecf0f1",
            "fg": "#2c3e50",
            "accent": "#3498db",
            "success": "#27ae60",
            "warning": "#f39c12",
            "danger": "#c0392b",
            "info": "#8e44ad"
        },
        "ocean": {
            "bg": "#1a1a2e",
            "fg": "#eaeaea",
            "accent": "#0f3460",
            "success": "#16c79a",
            "warning": "#f9a828",
            "danger": "#e94560",
            "info": "#533483"
        }
    }


class GlobalState:
    is_running: bool = True
    curiosity_level: int = 5
    forbidden_areas: List[Dict] = []
    short_term_memory: List[Dict] = []
    current_model: str = "deepseek"
    float_win: Any = None
    main_win: Any = None
    monitor_running: bool = False
    is_background: bool = False
    current_theme: str = "dark"
    agent: Any = None
    total_tokens: int = 0
    curiosity_triggers: int = 0
    shutdown_flag: bool = False
    
    @classmethod
    def get_theme(cls):
        return Config.THEMES.get(cls.current_theme, Config.THEMES["dark"])


GLOBAL_STATE = GlobalState()


class DataHistory:
    """History data recorder for chart display"""
    def __init__(self, max_size: int = 60):
        self.max_size = max_size
        self.data = {
            "cpu": deque(maxlen=max_size),
            "memory": deque(maxlen=max_size),
            "tokens": deque(maxlen=max_size),
            "short_term": deque(maxlen=max_size),
            "long_term": deque(maxlen=max_size),
            "task_queue": deque(maxlen=max_size),
            "capsules": deque(maxlen=max_size),
            "curiosity": deque(maxlen=max_size),
            "timestamps": deque(maxlen=max_size)
        }
        self._load_history()
    
    def _load_history(self):
        try:
            if os.path.exists(Config.HISTORY_FILE):
                with open(Config.HISTORY_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    for key in self.data:
                        if key in saved and isinstance(saved[key], list):
                            self.data[key] = deque(saved[key][:self.max_size], maxlen=self.max_size)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"History data loading failed, using defaults: {e}")
    
    def save_history(self):
        if GLOBAL_STATE.shutdown_flag:
            return
        try:
            os.makedirs(os.path.dirname(Config.HISTORY_FILE), exist_ok=True)
            with open(Config.HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump({k: list(v) for k, v in self.data.items()}, f)
        except Exception as e:
            print(f"Failed to save history data: {e}")
    
    def add_data_point(self, key: str, value: float):
        if key in self.data:
            self.data[key].append(value)
    
    def add_timestamp(self):
        self.data["timestamps"].append(datetime.now().strftime("%H:%M"))
    
    def get_data(self, key: str) -> List:
        return list(self.data.get(key, []))
    
    def get_timestamps(self) -> List:
        return list(self.data.get("timestamps", []))


data_history = DataHistory()


def load_forbidden_areas():
    try:
        if os.path.exists(Config.FORBIDDEN_CONFIG):
            with open(Config.FORBIDDEN_CONFIG, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or []
                if isinstance(data, list):
                    if len(data) > 0 and isinstance(data[0], str):
                        GLOBAL_STATE.forbidden_areas = [{"type": "path", "value": p} for p in data]
                    else:
                        GLOBAL_STATE.forbidden_areas = [item for item in data if isinstance(item, dict)]
                else:
                    GLOBAL_STATE.forbidden_areas = []
        else:
            GLOBAL_STATE.forbidden_areas = []
    except Exception as e:
        print(f"Failed to load forbidden areas: {e}")
        GLOBAL_STATE.forbidden_areas = []
    print(f"Loaded forbidden areas: {GLOBAL_STATE.forbidden_areas}")


def save_forbidden_areas():
    try:
        with open(Config.FORBIDDEN_CONFIG, "w", encoding="utf-8") as f:
            yaml.dump(GLOBAL_STATE.forbidden_areas, f, indent=2, allow_unicode=True)
    except Exception as e:
        print(f"Failed to save forbidden areas: {e}")


load_forbidden_areas()


class ScreenSelector:
    def __init__(self, callback: Callable):
        self.callback = callback
        self.start_x = None
        self.start_y = None
        self.rect = None

        self.root = tk.Tk()
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-alpha", 0.3)
        self.root.attributes("-topmost", True)
        self.root.config(bg="black")
        self.root.overrideredirect(True)

        self.canvas = tk.Canvas(self.root, cursor="cross", bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.root.bind("<Escape>", lambda e: self._cancel_selection())

    def _cancel_selection(self):
        self.root.destroy()

    def _on_press(self, e):
        self.start_x = e.x
        self.start_y = e.y

    def _on_drag(self, e):
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(
            self.start_x, self.start_y, e.x, e.y,
            outline="red", width=2
        )

    def _on_release(self, e):
        x1 = min(self.start_x, e.x)
        y1 = min(self.start_y, e.y)
        x2 = max(self.start_x, e.x)
        y2 = max(self.start_y, e.y)
        self.root.destroy()
        if abs(x2 - x1) > 5 and abs(y2 - y1) > 5:
            self.callback({"type": "screen", "value": (x1, y1, x2, y2)})


class AgentDataProvider:
    def __init__(self, agent: Any = None):
        self.agent = agent
    
    def set_agent(self, agent: Any):
        self.agent = agent
    
    def get_short_term_memory_count(self) -> int:
        if self.agent and hasattr(self.agent, 'short_term_memory') and self.agent.short_term_memory:
            try:
                logs = self.agent.short_term_memory.get_recent_logs(limit=1000)
                return len(logs) if logs else 0
            except Exception:
                pass
        return 0
    
    def get_long_term_memory_count(self) -> int:
        if self.agent and hasattr(self.agent, 'long_term_memory') and self.agent.long_term_memory:
            try:
                if hasattr(self.agent.long_term_memory, 'collection'):
                    return self.agent.long_term_memory.collection.count()
            except Exception:
                pass
        return 0
    
    def get_task_queue_count(self) -> int:
        if self.agent and hasattr(self.agent, 'task_queue'):
            try:
                return self.agent.task_queue.qsize()
            except Exception:
                pass
        return 0
    
    def get_capsule_count(self) -> int:
        if self.agent and hasattr(self.agent, 'capsule_manager') and self.agent.capsule_manager:
            try:
                capsules = self.agent.capsule_manager.get_capsules_by_agent('default', limit=1000)
                return len(capsules) if capsules else 0
            except Exception:
                pass
        return 0
    
    def get_curiosity_triggers(self) -> int:
        if self.agent and hasattr(self.agent, 'curiosity_system') and self.agent.curiosity_system:
            try:
                if hasattr(self.agent.curiosity_system, 'get_trigger_count'):
                    return self.agent.curiosity_system.get_trigger_count()
            except Exception:
                pass
        return GLOBAL_STATE.curiosity_triggers
    
    def get_token_usage(self) -> int:
        return GLOBAL_STATE.total_tokens
    
    def add_token_usage(self, tokens: int):
        GLOBAL_STATE.total_tokens += tokens
    
    def get_recent_memories(self, limit: int = 20) -> List[Dict]:
        if self.agent and hasattr(self.agent, 'short_term_memory') and self.agent.short_term_memory:
            try:
                logs = self.agent.short_term_memory.get_recent_logs(limit=limit)
                return logs if logs else []
            except Exception:
                pass
        return []
    
    def get_recent_capsules(self, limit: int = 10) -> List[Dict]:
        if self.agent and hasattr(self.agent, 'capsule_manager') and self.agent.capsule_manager:
            try:
                capsules = self.agent.capsule_manager.get_capsules_by_agent('default', limit=limit)
                return capsules if capsules else []
            except Exception:
                pass
        return []


data_provider = AgentDataProvider()


class FloatMonitorWindow:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Agent Full-Chain Monitor")
        self.root.geometry(f"{Config.FLOAT_WIN_SIZE[0]}x{Config.FLOAT_WIN_SIZE[1]}+{Config.FLOAT_WIN_POS[0]}+{Config.FLOAT_WIN_POS[1]}")
        self.root.attributes('-topmost', True)
        self.root.overrideredirect(True)
        
        self.theme = GLOBAL_STATE.get_theme()
        self.root.configure(bg=self.theme["bg"])
        
        self.x = 0
        self.y = 0
        self._update_count = 0
        self._status_count = 0
        self.cache = {}
        
        self._create_panel()
        self.root.bind("<ButtonPress-1>", self._start_move)
        self.root.bind("<B1-Motion>", self._on_move)
        self.start_data_thread()

    def start_data_thread(self):
        """Background thread collects data without blocking UI"""
        def run():
            while not GLOBAL_STATE.shutdown_flag:
                try:
                    short_count = data_provider.get_short_term_memory_count()
                    long_count = data_provider.get_long_term_memory_count()
                    task_count = data_provider.get_task_queue_count()
                    capsule_count = data_provider.get_capsule_count()
                    token_usage = data_provider.get_token_usage()
                    cpu_percent = psutil.cpu_percent(interval=0)
                    mem_percent = psutil.virtual_memory().percent
                    curiosity_count = data_provider.get_curiosity_triggers()

                    self.cache = {
                        "short": short_count, "long": long_count, "task": task_count,
                        "capsule": capsule_count, "token": token_usage,
                        "cpu": cpu_percent, "mem": mem_percent, "curiosity": curiosity_count
                    }
                    self.root.after(0, self.update_ui)
                except Exception as e:
                    print(f"Data collection exception: {e}")
                time.sleep(10)
        threading.Thread(target=run, daemon=True).start()

    def update_ui(self):
        """UI thread updates interface, only reads cache, no time-consuming operations"""
        if GLOBAL_STATE.shutdown_flag:
            return
        c = self.cache
        self.data_items["short_term"].config(text=f"Short-term Memory: {c['short']} items")
        self.data_items["long_term"].config(text=f"Long-term Memory: {c['long']} items")
        self.data_items["task_queue"].config(text=f"Task Queue: {c['task']} pending")
        self.data_items["capsules"].config(text=f"Experience Capsules: {c['capsule']} items")
        self.data_items["llm_tokens"].config(text=f"{GLOBAL_STATE.current_model}: {c['token']} tokens")

        cpu_bar = self._get_progress_bar(c['cpu'])
        self.data_items["cpu"].config(text=f"CPU: {cpu_bar} {c['cpu']:.1f}%")
        mem_bar = self._get_progress_bar(c['mem'])
        self.data_items["memory"].config(text=f"Memory: {mem_bar} {c['mem']:.1f}%")
        self.data_items["curiosity"].config(text=f"Curiosity Triggers: {c['curiosity']} times")

        data_history.add_data_point("short_term", c['short'])
        data_history.add_data_point("long_term", c['long'])
        data_history.add_data_point("task_queue", c['task'])
        data_history.add_data_point("capsules", c['capsule'])
        data_history.add_data_point("tokens", c['token'])
        data_history.add_data_point("cpu", c['cpu'])
        data_history.add_data_point("memory", c['mem'])
        data_history.add_data_point("curiosity", c['curiosity'])
        data_history.add_timestamp()

        self._status_count += 1
        if self._status_count >= 5:
            status_text = "Online" if GLOBAL_STATE.is_running else "Offline"
            status_color = self.theme["success"] if GLOBAL_STATE.is_running else self.theme["danger"]
            self.data_items["agent_status"].config(text=f"Agent Status: {status_text}", fg=status_color)
            self._status_count = 0

        self._update_count += 1
        if self._update_count >= 120:
            data_history.save_history()
            self._update_count = 0

    def _create_panel(self):
        main_frame = tk.Frame(self.root, bg=self.theme["bg"])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        title_label = tk.Label(
            main_frame, text="Agent Full-Chain Monitor",
            bg=self.theme["bg"], fg=self.theme["fg"], font=("Consolas", 12, "bold")
        )
        title_label.pack(fill=tk.X, pady=(0, 5))

        ttk.Separator(main_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=2)

        data_frame = tk.Frame(main_frame, bg=self.theme["bg"])
        data_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.data_items = {}
        items_config = [
            ("short_term", "Short-term Memory: 0 items", self.theme["success"]),
            ("long_term", "Long-term Memory: 0 items", self.theme["success"]),
            ("task_queue", "Task Queue: 0 pending", self.theme["success"]),
            ("capsules", "Experience Capsules: 0 items", self.theme["success"]),
            ("llm_tokens", "Token Usage: 0 tokens", self.theme["accent"]),
            ("cpu", "CPU: ████░░░░ 0%", self.theme["warning"]),
            ("memory", "Memory: ██████░░ 0%", self.theme["warning"]),
            ("curiosity", "Curiosity Triggers: 0 times/min", self.theme["info"]),
            ("agent_status", "Agent Status: Online", self.theme["success"])
        ]
        
        for key, text, color in items_config:
            label = tk.Label(data_frame, text=text, bg=self.theme["bg"], fg=color, font=("Consolas", 10))
            label.pack(anchor=tk.W, pady=2)
            label.bind("<Button-1>", lambda e, k=key: self._on_item_click(k))
            label.bind("<Enter>", lambda e, l=label: l.config(fg="white", cursor="hand2"))
            label.bind("<Leave>", lambda e, l=label, k=key: self._reset_label_color(l, k))
            self.data_items[key] = label

    def _reset_label_color(self, label, key):
        color_map = {
            "short_term": self.theme["success"], "long_term": self.theme["success"],
            "task_queue": self.theme["success"], "capsules": self.theme["success"],
            "cpu": self.theme["warning"], "memory": self.theme["warning"],
            "curiosity": self.theme["info"], "llm_tokens": self.theme["accent"],
            "agent_status": self.theme["success"] if GLOBAL_STATE.is_running else self.theme["danger"]
        }
        label.config(fg=color_map.get(key, self.theme["success"]), cursor="arrow")

    def _start_move(self, event):
        self.x = event.x
        self.y = event.y

    def _on_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")

    def _get_progress_bar(self, percent: float) -> str:
        bar_length = 10
        filled = int(bar_length * percent / 100)
        return "█" * filled + "░" * (bar_length - filled)

    def _on_item_click(self, item_key):
        if hasattr(self, f'_detail_win_{item_key}'):
            win = getattr(self, f'_detail_win_{item_key}')
            win.lift()
            win.focus_force()
            return
    
        detail_win = tk.Toplevel(self.root)
        detail_win.title(f"Details - {item_key}")
        detail_win.geometry("800x500")
        detail_win.attributes('-topmost', True)
        setattr(self, f'_detail_win_{item_key}', detail_win)
    
        tab_control = ttk.Notebook(detail_win)
        
        data_tab = ttk.Frame(tab_control)
        tab_control.add(data_tab, text="Scroll Data")
        self._fill_scroll_data(data_tab, item_key)
        
        chart_tab = ttk.Frame(tab_control)
        tab_control.add(chart_tab, text="Visual Chart")
        self._fill_chart_data(chart_tab, item_key)
        
        tab_control.pack(expand=1, fill="both")
    
        def on_close():
            detail_win.destroy()
            if hasattr(self, f'_detail_win_{item_key}'):
                delattr(self, f'_detail_win_{item_key}')
            plt.close('all')
            gc.collect()
        detail_win.protocol("WM_DELETE_WINDOW", on_close)

    def _fill_scroll_data(self, parent, item_key):
        scroll_text = scrolledtext.ScrolledText(parent, wrap=tk.WORD, font=("Consolas", 10))
        scroll_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        if item_key == "short_term":
            scroll_text.insert(tk.END, "=== Short-term Memory Records ===\n")
            memories = data_provider.get_recent_memories(limit=20)
            if memories:
                for mem in reversed(memories):
                    timestamp = mem.get('timestamp', 'N/A')
                    content = mem.get('content', mem.get('message', str(mem)))
                    scroll_text.insert(tk.END, f"[{timestamp}] {content}\n")
            else:
                scroll_text.insert(tk.END, "No short-term memory data\n")

        elif item_key == "long_term":
            scroll_text.insert(tk.END, "=== Long-term Memory Statistics ===\n")
            count = data_provider.get_long_term_memory_count()
            scroll_text.insert(tk.END, f"Total memory count: {count}\n")
            scroll_text.insert(tk.END, "(Long-term memory is stored in vector database, content cannot be displayed directly)\n")

        elif item_key == "task_queue":
            scroll_text.insert(tk.END, "=== Task Queue Status ===\n")
            count = data_provider.get_task_queue_count()
            scroll_text.insert(tk.END, f"Pending tasks: {count}\n")

        elif item_key == "capsules":
            scroll_text.insert(tk.END, "=== Experience Capsule Records ===\n")
            capsules = data_provider.get_recent_capsules(limit=10)
            if capsules:
                for cap in capsules:
                    cap_id = cap.get('capsule_id', 'N/A')
                    cap_type = cap.get('type', 'unknown')
                    scroll_text.insert(tk.END, f"[{cap_id}] Type: {cap_type}\n")
            else:
                scroll_text.insert(tk.END, "No capsule data\n")

        elif item_key in ["cpu", "memory", "llm_tokens", "curiosity"]:
            scroll_text.insert(tk.END, f"=== {item_key.upper()} History Data ===\n")
            history_data = data_history.get_data(item_key)
            timestamps = data_history.get_timestamps()
            if history_data and timestamps:
                for t, v in zip(timestamps[-20:], history_data[-20:]):
                    scroll_text.insert(tk.END, f"[{t}] {v:.2f}\n")
            else:
                scroll_text.insert(tk.END, "No history data\n")

        elif item_key == "llm_tokens":
            scroll_text.insert(tk.END, "=== LLM Token Usage Statistics ===\n")
            total = data_provider.get_token_usage()
            scroll_text.insert(tk.END, f"Total Token Usage: {total}\n")
            scroll_text.insert(tk.END, f"Current Model: {GLOBAL_STATE.current_model}\n")
            token_history = data_history.get_data("tokens")
            if token_history:
                scroll_text.insert(tk.END, "\nHistory Records:\n")
                for i, t in enumerate(token_history[-10:]):
                    scroll_text.insert(tk.END, f"  Record {i+1}: {t} tokens\n")

        elif item_key == "curiosity":
            scroll_text.insert(tk.END, "=== Curiosity System Status ===\n")
            count = data_provider.get_curiosity_triggers()
            scroll_text.insert(tk.END, f"Trigger Count: {count}\n")
            scroll_text.insert(tk.END, f"Curiosity Level: {GLOBAL_STATE.curiosity_level}\n")

        else:
            scroll_text.insert(tk.END, "=== Agent Status Information ===\n")
            scroll_text.insert(tk.END, f"Current Status: {'Online' if GLOBAL_STATE.is_running else 'Offline'}\n")
            scroll_text.insert(tk.END, f"Curiosity Level: {GLOBAL_STATE.curiosity_level}\n")
            scroll_text.insert(tk.END, f"Current Model: {GLOBAL_STATE.current_model}\n")
            scroll_text.insert(tk.END, f"Total Tokens: {GLOBAL_STATE.total_tokens}\n")
            if GLOBAL_STATE.forbidden_areas:
                forbidden_str = ""
                for area in GLOBAL_STATE.forbidden_areas:
                    if area["type"] == "path":
                        forbidden_str += f"\n- Path: {area['value']}"
                    else:
                        forbidden_str += f"\n- Screen Area: {area['value']}"
                no_forbidden = "\n- None"
                scroll_text.insert(tk.END, f"Forbidden Areas: {forbidden_str if forbidden_str else no_forbidden}\n")

    def _fill_chart_data(self, parent, item_key):
        try:
            fig, ax = plt.subplots(figsize=(8, 4))
            
            if item_key in ["cpu", "memory"]:
                data = data_history.get_data(item_key)
                timestamps = data_history.get_timestamps()
                if data and timestamps:
                    ax.plot(range(len(data)), data, marker='o', linestyle='-', color='#3498db')
                    ax.set_title(f"{item_key.upper()} Usage Trend")
                    ax.set_xlabel("Time Point")
                    ax.set_ylabel(f"{item_key.upper()} %")
                    ax.grid(True, alpha=0.3)
                else:
                    ax.text(0.5, 0.5, "No data available", ha='center', va='center')
            
            elif item_key == "llm_tokens":
                data = data_history.get_data("tokens")
                if data:
                    ax.bar(range(len(data)), data, color='#9b59b6')
                    ax.set_title("Token Usage History")
                    ax.set_xlabel("Time Point")
                    ax.set_ylabel("Tokens")
                    ax.grid(True, alpha=0.3)
                else:
                    ax.text(0.5, 0.5, "No data available", ha='center', va='center')
            
            elif item_key in ["short_term", "long_term", "task_queue", "capsules"]:
                data = data_history.get_data(item_key)
                if data:
                    ax.fill_between(range(len(data)), data, alpha=0.3, color='#2ecc71')
                    ax.plot(range(len(data)), data, color='#2ecc71')
                    ax.set_title(f"{item_key.replace('_', ' ').title()} Trend")
                    ax.set_xlabel("Time Point")
                    ax.set_ylabel("Count")
                    ax.grid(True, alpha=0.3)
                else:
                    ax.text(0.5, 0.5, "No data available", ha='center', va='center')
            
            else:
                data = data_history.get_data("curiosity")
                if data:
                    ax.plot(range(len(data)), data, marker='s', linestyle='--', color='#e74c3c')
                    ax.set_title("Curiosity Trigger Trend")
                    ax.set_xlabel("Time Point")
                    ax.set_ylabel("Trigger Count")
                    ax.grid(True, alpha=0.3)
                else:
                    ax.text(0.5, 0.5, "No data available", ha='center', va='center')
            
            plt.tight_layout()
            
            canvas = FigureCanvasTkAgg(fig, parent)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            
        except Exception as e:
            label = tk.Label(parent, text=f"Chart rendering failed: {e}", fg="red")
            label.pack(pady=50)


class MainChatWindow:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Agent Main Chat Window")
        self.root.geometry(f"{Config.MAIN_WIN_SIZE[0]}x{Config.MAIN_WIN_SIZE[1]}")
        
        self.theme = GLOBAL_STATE.get_theme()
        self.root.configure(bg=self.theme["bg"])
        
        self.agent = None
        self.agent_status_var = tk.BooleanVar(value=True)
        self.is_topmost = False
        self.model_var = tk.StringVar(value="deepseek")
        self.api_key_var = tk.StringVar()
        self.curiosity_var = tk.IntVar(value=5)
        
        self._create_ui()
        self._init_agent()
    
    def _create_ui(self):
        main_frame = tk.Frame(self.root, bg=self.theme["bg"])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self._create_sidebar(main_frame)
        self._create_chat_area(main_frame)
    
    def _create_sidebar(self, parent):
        self.sidebar = tk.Frame(parent, bg=self.theme["bg"], width=200)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        self.sidebar.pack_propagate(False)
        
        tk.Label(
            self.sidebar, text="Control Panel",
            bg=self.theme["bg"], fg=self.theme["fg"], font=("Arial", 12, "bold")
        ).pack(pady=(0, 10))
        
        ttk.Separator(self.sidebar, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        self.agent_status_check = tk.Checkbutton(
            self.sidebar, text="Agent Online",
            variable=self.agent_status_var, bg=self.theme["bg"], fg=self.theme["fg"],
            command=self._toggle_agent_status
        )
        self.agent_status_check.pack(anchor=tk.W, pady=5)
        
        tk.Label(
            self.sidebar, text="Curiosity (0-10):",
            bg=self.theme["bg"], fg=self.theme["fg"]
        ).pack(anchor=tk.W, pady=(10, 0))
        
        curiosity_scale = tk.Scale(
            self.sidebar, from_=0, to=10, orient=tk.HORIZONTAL,
            variable=self.curiosity_var, bg=self.theme["bg"], fg=self.theme["fg"],
            command=self._update_curiosity
        )
        curiosity_scale.pack(fill=tk.X, pady=5)
        
        ttk.Separator(self.sidebar, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
        tk.Label(
            self.sidebar, text="Forbidden Area Management",
            bg=self.theme["bg"], fg=self.theme["fg"], font=("Arial", 10, "bold")
        ).pack(pady=(0, 5))
        
        buttons_config = [
            ("Select Screen Area", self.theme["warning"], self._start_screen_select),
            ("Add File/Directory", self.theme["accent"], self._add_forbidden_path),
            ("Manage Forbidden Areas", self.theme["info"], self._manage_forbidden_areas),
        ]
        
        for text, color, cmd in buttons_config:
            btn = tk.Button(
                self.sidebar, text=text, bg=color, fg="white",
                command=cmd, width=18
            )
            btn.pack(pady=3)
        
        ttk.Separator(self.sidebar, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
        tk.Label(
            self.sidebar, text="LLM Configuration",
            bg=self.theme["bg"], fg=self.theme["fg"], font=("Arial", 10, "bold")
        ).pack(pady=(0, 5))
        
        tk.Label(
            self.sidebar, text="Model Type:",
            bg=self.theme["bg"], fg=self.theme["fg"]
        ).pack(anchor=tk.W)
        
        model_options = ["deepseek", "openai", "anthropic", "local"]
        model_menu = ttk.Combobox(
            self.sidebar, textvariable=self.model_var, values=model_options, state="readonly"
        )
        model_menu.pack(fill=tk.X, pady=5)
        model_menu.bind("<<ComboboxSelected>>", self._on_model_change)
        
        tk.Label(
            self.sidebar, text="API Key:",
            bg=self.theme["bg"], fg=self.theme["fg"]
        ).pack(anchor=tk.W, pady=(5, 0))
        
        api_entry = tk.Entry(
            self.sidebar, textvariable=self.api_key_var, show="*", width=20
        )
        api_entry.pack(fill=tk.X, pady=5)
        
        save_btn = tk.Button(
            self.sidebar, text="Save Config",
            bg=self.theme["accent"], fg="white",
            command=self._save_llm_config, width=18
        )
        save_btn.pack(pady=5)
        
        ttk.Separator(self.sidebar, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
        theme_btn = tk.Button(
            self.sidebar, text="Toggle Theme",
            bg=self.theme["info"], fg="white",
            command=self._toggle_theme, width=18
        )
        theme_btn.pack(pady=5)
    
    def _create_chat_area(self, parent):
        chat_frame = tk.Frame(parent, bg=self.theme["bg"])
        chat_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.chat_text = scrolledtext.ScrolledText(
            chat_frame, wrap=tk.WORD, font=("Arial", 10),
            bg=self.theme["bg"], fg=self.theme["fg"]
        )
        self.chat_text.pack(fill=tk.BOTH, expand=True)
        self.chat_text.config(state=tk.DISABLED)
        
        input_frame = tk.Frame(chat_frame, bg=self.theme["bg"])
        input_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.input_entry = tk.Entry(
            input_frame, font=("Arial", 10), bg=self.theme["bg"], fg=self.theme["fg"]
        )
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.input_entry.bind("<Return>", lambda e: self._send_message())
        
        send_btn = tk.Button(
            input_frame, text="Send", bg=self.theme["accent"], fg="white",
            command=self._send_message, width=10
        )
        send_btn.pack(side=tk.RIGHT)
        
        button_frame = tk.Frame(chat_frame, bg=self.theme["bg"])
        button_frame.pack(fill=tk.X, pady=(5, 0))
        
        release_btn = tk.Button(
            button_frame, text="Release Resources",
            bg=self.theme["warning"], fg="white",
            command=self._release_resources, width=12
        )
        release_btn.pack(side=tk.LEFT, padx=5)
        
        stop_btn = tk.Button(
            button_frame, text="Emergency Stop",
            bg=self.theme["danger"], fg="white",
            command=self._stop_agent, width=12
        )
        stop_btn.pack(side=tk.LEFT, padx=5)
        
        topmost_btn = tk.Button(
            button_frame, text="Pin Window",
            bg=self.theme["info"], fg="white",
            command=self._toggle_topmost, width=12
        )
        topmost_btn.pack(side=tk.LEFT, padx=5)
    
    def _init_agent(self):
        if not CORE_AVAILABLE:
            self._add_system_message("Core module missing, running in simulation mode")
            return
        
        try:
            self._add_system_message("Initializing Agent...")
            self.agent = AgentCore()
            GLOBAL_STATE.agent = self.agent
            data_provider.set_agent(self.agent)
            self._add_system_message("Agent initialized successfully")
        except Exception as e:
            self._add_system_message(f"Agent initialization failed, using simulation mode: {e}")
    
    def _toggle_agent_status(self):
        GLOBAL_STATE.is_running = self.agent_status_var.get()
        status = "Online" if GLOBAL_STATE.is_running else "Offline"
        self._add_system_message(f"Agent status changed to: {status}")
    
    def _toggle_topmost(self):
        self.is_topmost = not self.is_topmost
        self.root.attributes('-topmost', self.is_topmost)
        self._add_system_message(f"Window always on top: {'Enabled' if self.is_topmost else 'Disabled'}")
    
    def _toggle_theme(self):
        themes = list(Config.THEMES.keys())
        current_idx = themes.index(GLOBAL_STATE.current_theme)
        next_idx = (current_idx + 1) % len(themes)
        theme_name = themes[next_idx]
        GLOBAL_STATE.current_theme = theme_name
        self.theme = GLOBAL_STATE.get_theme()
        self._add_system_message(f"Theme switched to: {theme_name}")
        messagebox.showinfo("Theme Switch", f"Theme switched to: {theme_name}\nSome colors will take full effect after restart")
    
    def _on_model_change(self, event=None):
        GLOBAL_STATE.current_model = self.model_var.get()
        self._add_system_message(f"Model switched to: {GLOBAL_STATE.current_model}")
    
    def _start_screen_select(self):
        def callback(area):
            GLOBAL_STATE.forbidden_areas.append(area)
            save_forbidden_areas()
            if GLOBAL_STATE.float_win:
                GLOBAL_STATE.float_win.update_ui()
            messagebox.showinfo("Success", f"Added forbidden screen area: {area['value']}\nOnly effective when Agent is online")
        
        ScreenSelector(callback)
    
    def _add_forbidden_path(self):
        file_path = filedialog.askopenfilename(
            title="Select forbidden file (cancel to select folder)",
            filetypes=[("All Files", "*.*")]
        )
        
        if file_path:
            if not any(a["value"] == file_path for a in GLOBAL_STATE.forbidden_areas):
                GLOBAL_STATE.forbidden_areas.append({"type": "path", "value": file_path})
                save_forbidden_areas()
                messagebox.showinfo("Success", f"Added forbidden file: {file_path}")
            else:
                messagebox.showwarning("Notice", f"{file_path} is already in the forbidden list")
            return
        
        dir_path = filedialog.askdirectory(title="Select forbidden folder/drive")
        if dir_path:
            if not any(a["value"] == dir_path for a in GLOBAL_STATE.forbidden_areas):
                GLOBAL_STATE.forbidden_areas.append({"type": "path", "value": dir_path})
                save_forbidden_areas()
                messagebox.showinfo("Success", f"Added forbidden folder: {dir_path}")
            else:
                messagebox.showwarning("Notice", f"{dir_path} is already in the forbidden list")
    
    def _refresh_ui(self):
        self._add_system_message("Interface refreshed")
        if GLOBAL_STATE.float_win:
            GLOBAL_STATE.float_win.update_ui()

    def _stop_agent(self):
        self.agent_status_var.set(False)
        self._toggle_agent_status()

    def _release_resources(self):
        GLOBAL_STATE.short_term_memory = []
        gc.collect()
        messagebox.showinfo("Notice", "Resources released\n- Short-term memory cache cleared\n- Memory reclaimed")

    def _update_curiosity(self, value):
        GLOBAL_STATE.curiosity_level = int(value)
        self._add_system_message(f"Curiosity level adjusted to: {value}")

    def _add_system_message(self, message: str):
        self.chat_text.config(state=tk.NORMAL)
        self.chat_text.insert(tk.END, f"[System] {message}\n")
        self.chat_text.config(state=tk.DISABLED)
        self.chat_text.see(tk.END)

    def _manage_forbidden_areas(self):
        manage_win = tk.Toplevel(self.root)
        manage_win.title("Forbidden Area Management")
        manage_win.geometry("500x350")
        manage_win.attributes('-topmost', True)

        list_frame = tk.Frame(manage_win)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.forbidden_listbox = tk.Listbox(list_frame, font=("Arial", 10), width=60, height=12)
        self.forbidden_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.forbidden_listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.forbidden_listbox.yview)

        for idx, area in enumerate(GLOBAL_STATE.forbidden_areas):
            if area["type"] == "path":
                display_text = f"{idx+1}. [Path] {area['value']}"
            else:
                x1, y1, x2, y2 = area["value"]
                display_text = f"{idx+1}. [Screen] Coordinates({x1},{y1})-({x2},{y2})"
            self.forbidden_listbox.insert(tk.END, display_text)

        btn_frame = tk.Frame(manage_win)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)

        del_btn = tk.Button(
            btn_frame, text="Delete Selected", bg=self.theme["danger"], fg="white",
            command=self._delete_forbidden_area, width=10
        )
        del_btn.pack(side=tk.LEFT, padx=5)

        clear_btn = tk.Button(
            btn_frame, text="Clear All", bg=self.theme["warning"], fg="white",
            command=self._clear_forbidden_areas, width=10
        )
        clear_btn.pack(side=tk.LEFT, padx=5)

    def _delete_forbidden_area(self):
        try:
            selected_index = self.forbidden_listbox.curselection()[0]
            del GLOBAL_STATE.forbidden_areas[selected_index]
            self.forbidden_listbox.delete(selected_index)
            save_forbidden_areas()
            messagebox.showinfo("Success", "Deleted selected forbidden area")
        except IndexError:
            messagebox.showwarning("Notice", "Please select an area to delete first")

    def _clear_forbidden_areas(self):
        if messagebox.askyesno("Confirm", "Are you sure you want to clear all forbidden areas?"):
            GLOBAL_STATE.forbidden_areas.clear()
            self.forbidden_listbox.delete(0, tk.END)
            save_forbidden_areas()
            messagebox.showinfo("Success", "Cleared all forbidden areas")

    def _save_llm_config(self):
        model_type = self.model_var.get()
        api_key = self.api_key_var.get().strip()
        
        if not api_key:
            messagebox.showwarning("Notice", "Please enter API key")
            return
        
        try:
            from utils.security import encrypt_data
            encrypted_key = encrypt_data(api_key)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to encrypt API key: {str(e)}")
            return
        
        config_path = "agent_config.yaml"
        config_data = {}
        
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f) or {}
        
        if "llm" not in config_data:
            config_data["llm"] = {}
        config_data["llm"]["model_type"] = model_type
        config_data["llm"]["api_key"] = encrypted_key
        
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(config_data, f, ensure_ascii=False, indent=2)
            
            self.api_key_var.set("")
            GLOBAL_STATE.current_model = model_type
            messagebox.showinfo("Success", f"LLM configuration saved\nModel type: {model_type}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save configuration: {str(e)}")

    def _send_message(self):
        message = self.input_entry.get().strip()
        if not message:
            return

        self.input_entry.delete(0, tk.END)

        self.chat_text.config(state=tk.NORMAL)
        self.chat_text.insert(tk.END, f"You [{datetime.now().strftime('%H:%M:%S')}]: {message}\n")
        self.chat_text.see(tk.END)

        thinking_tag = f"thinking_{time.time()}"
        self.chat_text.insert(tk.END, f"Agent [{datetime.now().strftime('%H:%M:%S')}]: Thinking...\n", thinking_tag)
        self.chat_text.config(state=tk.DISABLED)
        self.chat_text.see(tk.END)

        def worker():
            try:
                if self.agent and GLOBAL_STATE.is_running:
                    reply = self.agent.process_message(message)
                    if isinstance(reply, dict):
                        agent_reply = reply.get("reply", reply.get("content", str(reply)))
                    else:
                        agent_reply = str(reply)
                    estimated_tokens = len(message) // 4 + len(agent_reply) // 4
                    data_provider.add_token_usage(estimated_tokens)
                    GLOBAL_STATE.curiosity_triggers += 1
                else:
                    agent_reply = f"Agent is currently offline, please check Agent status. Curiosity level: {GLOBAL_STATE.curiosity_level}"
            except Exception as e:
                agent_reply = f"Agent processing error: {str(e)}"

            if not GLOBAL_STATE.shutdown_flag:
                self.root.after(0, self._update_chat_reply, agent_reply, thinking_tag, message)

        threading.Thread(target=worker, daemon=True).start()

    def _update_chat_reply(self, agent_reply: str, thinking_tag: str, original_message: str):
        self.chat_text.config(state=tk.NORMAL)
        try:
            end_index = self.chat_text.index("end-1c")
            line_start = self.chat_text.index(f"{end_index} linestart")
            line_end = self.chat_text.index(f"{end_index} lineend")
            last_line = self.chat_text.get(line_start, line_end)
            if "Thinking..." in last_line:
                self.chat_text.delete(line_start, line_end)
                self.chat_text.insert(line_start, f"Agent [{datetime.now().strftime('%H:%M:%S')}]: {agent_reply}\n")
            else:
                self.chat_text.insert(tk.END, f"Agent [{datetime.now().strftime('%H:%M:%S')}]: {agent_reply}\n")
        except Exception:
            self.chat_text.insert(tk.END, f"Agent [{datetime.now().strftime('%H:%M:%S')}]: {agent_reply}\n")
        self.chat_text.config(state=tk.DISABLED)
        self.chat_text.see(tk.END)


def start_schedule():
    schedule.every().day.at(Config.CLEAR_TIME).do(lambda: data_history.save_history())
    
    def run_schedule():
        while not GLOBAL_STATE.shutdown_flag:
            schedule.run_pending()
            time.sleep(60)

    schedule_thread = threading.Thread(target=run_schedule, daemon=True)
    schedule_thread.start()


def main():
    start_schedule()

    main_root = tk.Tk()
    main_win = MainChatWindow(main_root)
    GLOBAL_STATE.main_win = main_win

    float_root = tk.Toplevel(main_root)
    float_win = FloatMonitorWindow(float_root)
    GLOBAL_STATE.float_win = float_win

    main_root.mainloop()


if __name__ == "__main__":
    required_packages = ['psutil', 'pywin32', 'schedule', 'matplotlib', 'pyyaml', 'python-dotenv']
    missing = []
    for pkg in required_packages:
        try:
            __import__(pkg.replace('-', '_'))
        except ImportError:
            missing.append(pkg)
    
    if missing:
        print(f"Missing dependencies, please run: pip install {' '.join(missing)}")
        sys.exit(1)
    
    main()
