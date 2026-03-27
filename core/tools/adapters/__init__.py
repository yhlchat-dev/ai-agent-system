# -*- coding: utf-8 -*-
"""
Tool Module Unified Export
"""

from .base_adapter import TokenBucket, BaseAPIAdapter

from .weather_adapter import WeatherAdapter, WeatherAPIAdapter
from .email_adapter import EmailAdapter
from .feishu_adapter import FeishuRobotAdapter

try:
    from .window_tools import (
        WindowEvent,
        find_window,
        find_control,
        click,
        type_text,
        get_text,
        focus_window,
        _window_monitor_loop,
        _start_window_monitor,
        _stop_window_monitor,
        _get_window_events,
    )
except Exception:
    pass

try:
    from .system_ops import (
        list_processes,
        list_windows,
        take_screenshot,
        activate_window,
        _type_text,
        _press_hotkey,
    )
except Exception:
    pass

try:
    from .file_manager import (
        register_file,
        search_files,
        list_files,
        read_file,
        write_file,
    )
except Exception:
    pass

try:
    from .custom_storage import (
        save_custom_data,
        search_custom_storage,
    )
except Exception:
    pass
