#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Agent Capsule: Store Agent's experience/behavior records"""
import time
from utils.config import CONFIG
from utils.logging import capsule_logger

class AgentCapsule:
    """Agent Experience Capsule"""
    def __init__(self, agent_id, content, capsule_type="experience"):
        self.schema_version = CONFIG["capsule"]["schema_version"]
        self.agent_id = agent_id
        self.content = content
        self.capsule_type = capsule_type
        self.create_time = time.time()
    
    def to_dict(self):
        """Convert to dict for storage"""
        return {
            "schema_version": self.schema_version,
            "agent_id": self.agent_id,
            "content": self.content,
            "capsule_type": self.capsule_type,
            "create_time": self.create_time
        }
    
    def __str__(self):
        return f"AgentCapsule(agent_id={self.agent_id}, type={self.capsule_type}, content={self.content[:20]}...)"
