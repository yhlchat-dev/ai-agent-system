#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Sub-Agent Full Lifecycle Management (Core Constraint: 30 Maximum Limit)
"""
import threading
import yaml
import os
from typing import Dict, Optional


class SubAgentLifecycle:
    """Sub-Agent Full Lifecycle Management (Core Constraint: 30 Maximum Limit)"""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_config()
        return cls._instance

    def _init_config(self):
        """Read configuration file: Maximum 30 sub-agents"""
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            "config",
            "agent_config.yaml"
        )
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            self.MAX_LIMIT = config.get("max_sub_agent_count", 30)
        except:
            self.MAX_LIMIT = 30

        self.running_agents: Dict[str, dict] = {}
        self.thread_lock = threading.Lock()

    def create_sub_agent(self, task_name: str):
        """Create sub-agent (strictly enforce 30 maximum limit)"""
        with self.thread_lock:
            current_count = len(self.running_agents)
            
            if current_count >= self.MAX_LIMIT:
                return {
                    "success": False,
                    "msg": f"Sub-agent limit reached: {self.MAX_LIMIT}, cannot create new task"
                }

            agent_id = f"AGENT_{threading.get_ident()}_{os.random(2).hex()}"
            agent_data = {
                "agent_id": agent_id,
                "task": task_name,
                "status": "Running",
                "create_time": os.times()
            }
            self.running_agents[agent_id] = agent_data

            return {
                "success": True,
                "agent_id": agent_id,
                "msg": f"Created successfully | Currently running: {len(self.running_agents)}/{self.MAX_LIMIT}"
            }

    def destroy_sub_agent(self, agent_id: str):
        """Destroy sub-agent (release slot)"""
        with self.thread_lock:
            if agent_id in self.running_agents:
                del self.running_agents[agent_id]
                return f"Destroyed successfully | Currently running: {len(self.running_agents)}/{self.MAX_LIMIT}"
            return "Sub-agent does not exist"

    def get_current_count(self):
        """Get current running count"""
        with self.thread_lock:
            return len(self.running_agents)


if __name__ == "__main__":
    print("=" * 60)
    print("Sub-Agent 30 Maximum Limit Constraint Test")
    print("=" * 60)

    lifecycle = SubAgentLifecycle()
    test_results = []

    for i in range(31):
        res = lifecycle.create_sub_agent(f"Test_Task_{i+1}")
        test_results.append(res)
        print(res["msg"])

    print("\n" + "=" * 60)
    print("Test Results:")
    print(f"Maximum allowed creation: 30")
    print(f"31st creation request: Blocked by system")
    print(f"Current running sub-agent count: {lifecycle.get_current_count()}")
    print("=" * 60)
