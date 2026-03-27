# -*- coding: utf-8 -*-
"""
Agent Interface Module
"""

from .feishu import (
    init_feishu,
    set_agent,
    start_feishu_service,
    stop_feishu_service,
    send_feishu_message
)

__all__ = [
    'init_feishu',
    'set_agent',
    'start_feishu_service',
    'stop_feishu_service',
    'send_feishu_message'
]
