# -*- coding: utf-8 -*-
"""
System Operation Tools: Process, screenshot, hotkey, window activation, etc.
"""
import tempfile
import os
from datetime import datetime

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

def list_processes(**kwargs) -> dict:
    """Get system process list"""
    if not PSUTIL_AVAILABLE:
        return {"success": False, "result": None, "error": "psutil library not installed"}
        
    try:
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'create_time']):
            try:
                processes.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
                
        processes.sort(key=lambda x: x.get('create_time', 0), reverse=True)
        return {"success": True, "result": processes[:100], "error": None}
    except Exception as e:
        return {"success": False, "result": None, "error": str(e)}

def list_windows(**kwargs) -> dict:
    """Get window list"""
    if not PYGETWINDOW_AVAILABLE:
        return {"success": False, "result": None, "error": "pygetwindow library not installed"}
        
    try:
        windows = gw.getAllWindows()
        win_list = []
        for win in windows:
            if win.title.strip():
                win_list.append({
                    "title": win.title,
                    "left": win.left,
                    "top": win.top,
                    "width": win.width,
                    "height": win.height,
                    "is_minimized": win.isMinimized,
                    "is_active": win.isActive
                })
        return {"success": True, "result": win_list, "error": None}
    except Exception as e:
        return {"success": False, "result": None, "error": str(e)}

def take_screenshot(save_dir=None, **kwargs) -> dict:
    """Take screenshot and save"""
    if not MSS_AVAILABLE:
        return {"success": False, "result": None, "error": "mss library not installed"}
        
    try:
        if save_dir is None:
            temp_dir = os.path.join(tempfile.gettempdir(), "agent_screenshots")
        else:
            temp_dir = save_dir
        os.makedirs(temp_dir, exist_ok=True)
        
        filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        filepath = os.path.join(temp_dir, filename)

        with mss.mss() as sct:
            sct.shot(output=filepath)
            
        return {"success": True, "result": filepath, "error": None}
    except Exception as e:
        return {"success": False, "result": None, "error": str(e)}

def activate_window(title_substring, exact=False):
    """Activate specified window"""
    if not PYGETWINDOW_AVAILABLE:
        return {"success": False, "result": None, "error": "pygetwindow library not installed"}
        
    try:
        if exact:
            windows = gw.getWindowsWithTitle(title_substring)
        else:
            windows = [w for w in gw.getAllWindows() if title_substring.lower() in w.title.lower()]
            
        if not windows:
            return {"success": False, "result": None, "error": f"Window not found"}
            
        win = windows[0]
        if win.isMinimized:
            win.restore()
        win.activate()
        
        return {"success": True, "result": f"Window activated: {win.title}", "error": None}
    except Exception as e:
        return {"success": False, "result": None, "error": str(e)}

def _type_text(text, interval=0.1):
    """Simulate keyboard input"""
    if not PYAUTOGUI_AVAILABLE:
        return {"success": False, "result": None, "error": "pyautogui library not installed"}
        
    try:
        pyautogui.typewrite(text, interval=interval)
        return {"success": True, "result": f"Text input completed", "error": None}
    except Exception as e:
        return {"success": False, "result": None, "error": str(e)}

def _press_hotkey(keys):
    """Simulate hotkey"""
    if not PYAUTOGUI_AVAILABLE:
        return {"success": False, "result": None, "error": "pyautogui library not installed"}
        
    try:
        pyautogui.hotkey(*keys.lower().split('+'))
        return {"success": True, "result": f"Hotkey {keys} pressed", "error": None}
    except Exception as e:
        return {"success": False, "result": None, "error": str(e)}
