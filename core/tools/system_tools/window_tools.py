# -*- coding: utf-8 -*-
"""
Window Operation & Monitoring Tools
"""
import time
import threading
import queue
from collections import namedtuple

try:
    import pygetwindow as gw
    PYGETWINDOW_AVAILABLE = True
except ImportError:
    PYGETWINDOW_AVAILABLE = False
    gw = None

WindowEvent = namedtuple('WindowEvent', ['type', 'window_title', 'timestamp'])

_window_monitor_thread = None
_window_events = queue.Queue()
_monitor_running = False
_last_window_set = set()

def find_window(title_contains=None, class_name=None, timeout=5):
    """Find specified window"""
    try:
        from utils.ui_automation import ui_auto
        return ui_auto.find_window(title_contains, class_name, timeout)
    except ImportError:
        print("[Error] ui_automation module not found")
        return None

def find_control(parent, condition, timeout=3):
    """Find window control"""
    try:
        from utils.ui_automation import ui_auto
        return ui_auto.find_control(parent, condition, timeout)
    except ImportError:
        print("[Error] ui_automation module not found")
        return None

def click(control, forbidden_areas=None):
    """Safe click control"""
    try:
        from utils.ui_automation import ui_auto
    except ImportError:
        print("[Error] ui_automation module not found")
        return False

    try:
        rect = control.BoundingRectangle
        x = rect.left + rect.width // 2
        y = rect.top + rect.height // 2
    except AttributeError:
        print("[Warning] Cannot get control coordinates, skipping forbidden area check")
        ui_auto.click(control)
        return True

    forbidden_areas = forbidden_areas or []
    for area in forbidden_areas:
        if (area.get('x1', 0) <= x <= area.get('x2', 0) and 
            area.get('y1', 0) <= y <= area.get('y2', 0)):
            print(f"[Security] Click blocked by forbidden area: coordinates ({x}, {y})")
            return False

    ui_auto.click(control)
    return True

def type_text(control, text: str):
    """Input text to control"""
    try:
        from utils.ui_automation import ui_auto
        ui_auto.send_keys(control, text)
    except ImportError:
        print("[Error] ui_automation module not found")

def get_text(control) -> str:
    """Get control text"""
    try:
        from utils.ui_automation import ui_auto
        return ui_auto.get_text(control)
    except ImportError:
        print("[Error] ui_automation module not found")
        return ""

def focus_window(window):
    """Focus window"""
    try:
        from utils.ui_automation import ui_auto
        ui_auto.focus_window(window)
    except ImportError:
        print("[Error] ui_automation module not found")

def _window_monitor_loop():
    """Window monitor background thread"""
    global _monitor_running, _last_window_set, _window_events
    while _monitor_running:
        try:
            current_windows = gw.getAllWindows() if PYGETWINDOW_AVAILABLE else []
            current_titles = {w.title for w in current_windows if w.title.strip()}
            
            new_titles = current_titles - _last_window_set
            for title in new_titles:
                _window_events.put(WindowEvent('created', title, time.time()))
            
            closed_titles = _last_window_set - current_titles
            for title in closed_titles:
                _window_events.put(WindowEvent('closed', title, time.time()))
            
            _last_window_set = current_titles
        except Exception as e:
            print(f"Window monitor error: {e}")
        time.sleep(1)

def _start_window_monitor(**kwargs) -> dict:
    """Start window monitor"""
    global _monitor_running, _window_monitor_thread
    if _monitor_running:
        return {"success": True, "result": "Monitor already running", "error": None}
        
    _monitor_running = True
    _window_monitor_thread = threading.Thread(target=_window_monitor_loop, daemon=True)
    _window_monitor_thread.start()
    return {"success": True, "result": "Window monitor started", "error": None}

def _stop_window_monitor(**kwargs) -> dict:
    """Stop window monitor"""
    global _monitor_running, _window_monitor_thread
    _monitor_running = False
    if _window_monitor_thread:
        _window_monitor_thread.join(timeout=2)
    return {"success": True, "result": "Window monitor stopped", "error": None}

def _get_window_events(**kwargs) -> dict:
    """Get window events"""
    global _window_events
    events = []
    while not _window_events.empty():
        events.append(_window_events.get_nowait())
    return {"success": True, "result": events, "error": None}
