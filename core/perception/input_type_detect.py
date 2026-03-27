#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Context Building: Concatenate conversation context (1.0 minimal version)"""
from memory.manage import memory_manager
from utils.logging import agent_logger
from memory.manage import memory_manager
from memory.archive_scheduler import archive_scheduler
from core.capsules.capsule_manager import capsule_manager
from utils.config import CONFIG

def main():
    archive_scheduler.start()
    
    pass

def build_context(user_input, recent_count=5):
    """Build conversation context: recent N memories + current input"""
    recent_memory = memory_manager.extract_recent(recent_count)
    context = "\n".join(recent_memory) + f"\nUser current input: {user_input}"
    agent_logger.debug(f"Context building complete, length: {len(context)}")
    return context
