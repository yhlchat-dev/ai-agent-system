#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Sub-Agent Module: Complete Implementation - Supports quantity limit, real-time destruction, permission control, config loading
"""

import json
import time
import uuid
import yaml
import os
from queue import Queue
from typing import Any, Dict, Optional, List
from threading import Lock

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 
                           "config/agent_config.yaml")
def log_agent_action(action: str, user_id: str, detail: str = ""):
    """Unified log format, aligned with main Agent"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    print(f"[{timestamp}] [{user_id}] {action}: {detail}")

def load_agent_config():
    """Load Agent core config"""
    default_config = {"sub_agent_max_count": 30}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        return {**default_config, **config}
    except FileNotFoundError:
        os.makedirs("config", exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True)
        return default_config

agent_config = load_agent_config()
SUB_AGENT_MAX_COUNT = agent_config["sub_agent_max_count"]
sub_agent_pool = {}
pool_lock = Lock()


class SubAgent:
    """Complete Sub-Agent Class: Supports quantity limit, real-time destruction, permission control, task execution"""

    def __init__(self, supervisor_queue, tool_manager, long_term_memory, 
                 user_id: str, short_term_memory=None, permissions: Dict[str, bool] = None):
        self.agent_id = f"sub_agent_{uuid.uuid4().hex[:8]}"
        self.supervisor_queue = supervisor_queue
        self.tool_manager = tool_manager
        self.ltm = long_term_memory
        self.stm = short_term_memory
        self.user_id = user_id
        
        self.permissions = {
            "allow_llm": False,
            "allow_network": False,
            "allow_memory_access": False,
            "allow_communication": True
        }
        
        self.log = []
        self.status = "idle"
        self.result = None
        self.error = None
        self.created_at = time.time()
        self.finished_at = None
        
        with pool_lock:
            if len(sub_agent_pool) >= SUB_AGENT_MAX_COUNT:
                raise RuntimeError(f"Sub-Agent count reached limit ({SUB_AGENT_MAX_COUNT}), cannot create new instance")
            sub_agent_pool[self.agent_id] = self
            self.log.append({"action": "agent_created", "time": time.time(), 
                            "current_count": len(sub_agent_pool)})

    def execute(self, task: Dict[str, Any]):
        """Execute task (thread-safe)"""
        if self.status in ["done", "failed", "killed"]:
            raise RuntimeError(f"Sub-Agent {self.agent_id} has terminated, cannot execute task")
        
        self.status = "running"
        task_desc = task.get("description", "")
        task_id = task.get("task_id", str(uuid.uuid4().hex[:6]))
        
        try:
            self.log.append({"action": "task_start", "task_id": task_id, 
                            "task_desc": task_desc, "time": time.time()})
            
            result = self._process(task_desc)
            self.result = result
            self.status = "done"
            self.finished_at = time.time()
            
            self.log.append({"action": "task_success", "task_id": task_id, 
                            "result": result, "time": time.time()})

            if self.stm:
                self.stm.save_memory({
                    "source": "sub_agent",
                    "agent_id": self.agent_id,
                    "task_id": task_id,
                    "result": result,
                    "time": time.time()
                })
            
        except Exception as e:
            self.error = str(e)
            self.status = "failed"
            self.finished_at = time.time()
            
            self.log.append({"action": "task_failed", "task_id": task_id, 
                            "error": str(e), "time": time.time()})
            
        finally:
            self._report_to_supervisor(task_id)
            self.destroy()

    def _process(self, task_desc: str) -> Any:
        """Execute specific task, complete permission check and task processing logic"""
        if any(key in task_desc for key in ["memory", "phone", "preference"]) and not self.permissions.get("allow_memory_access"):
            return f"[Permission Denied] Sub-Agent {self.agent_id} has no memory access permission"
        
        if "weather" in task_desc:
            if not self.permissions.get("allow_network", False):
                return f"[Permission Denied] Sub-Agent {self.agent_id} has no network permission, cannot query weather"
            city = task_desc.split(":")[-1].strip() if ":" in task_desc else "Beijing"
            return f"[Simulated] {city} today's weather: Sunny, 20C (Sub-Agent: {self.agent_id})"
        
        if "summary" in task_desc:
            if not self.permissions.get("allow_llm", False):
                return f"[Permission Denied] Sub-Agent {self.agent_id} has no LLM permission, cannot generate summary"
            return f"[Simulated] Text summary result: {task_desc[:20]}... (Sub-Agent: {self.agent_id})"
        
        if "file" in task_desc:
            return f"[Simulated] File operation executed successfully: {task_desc} (Sub-Agent: {self.agent_id})"
        
        return f"[Simulated] Sub-task '{task_desc}' executed successfully (Sub-Agent: {self.agent_id})"

    def _report_to_supervisor(self, task_id: str):
        """Report task result to main Agent"""
        report = {
            "agent_id": self.agent_id,
            "user_id": self.user_id,
            "task_id": task_id,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "execution_time": self.finished_at - self.created_at if self.finished_at else None,
            "log": self.log
        }
        self.supervisor_queue.put(report)

    def destroy(self):
        """Real-time destroy sub-agent (core feature)"""
        with pool_lock:
            if self.agent_id in sub_agent_pool:
                self.status = "killed"
                self.finished_at = time.time()
                
                self.log.append({"action": "agent_destroyed", "time": time.time(), 
                                "remaining_count": len(sub_agent_pool) - 1})
                del sub_agent_pool[self.agent_id]
                
                self.tool_manager = None
                self.ltm = None
                self.supervisor_queue = None
                
                print(f"Sub-Agent {self.agent_id} destroyed in real-time, current active count: {len(sub_agent_pool)}")
            else:
                self.log.append({"action": "destroy_failed", "reason": "agent not found in pool", "time": time.time()})

    @classmethod
    def get_active_agents(cls) -> List[str]:
        """Get current active sub-agent list (class method)"""
        with pool_lock:
            return list(sub_agent_pool.keys())

    @classmethod
    def force_destroy_all(cls):
        """Force destroy all active sub-agents (emergency method)"""
        with pool_lock:
            agent_ids = list(sub_agent_pool.keys())
            for agent_id in agent_ids:
                try:
                    sub_agent_pool[agent_id].destroy()
                except Exception as e:
                    print(f"Failed to destroy sub-agent {agent_id}: {e}")
        print(f"All sub-agents destroyed, current active count: {len(sub_agent_pool)}")


if __name__ == "__main__":
    from queue import Queue
    class MockToolManager:
        def call_tool(self, tool_name, **kwargs):
            return f"Simulated {tool_name} call result: {kwargs}"
    
    supervisor_queue = Queue()
    tool_manager = MockToolManager()
    ltm = "Simulated long-term memory"
    
    try:
        agent1 = SubAgent(supervisor_queue, tool_manager, ltm, user_id="test_user_001",
                         permissions={"allow_llm": True, "allow_network": True})
        print(f"Created sub-agent: {agent1.agent_id}")
        agent1.execute({"description": "Query Beijing weather"})
    except Exception as e:
        print(f"Test 1 failed: {e}")
    
    print("\n=== Test Quantity Limit ===")
    created_agents = []
    for i in range(SUB_AGENT_MAX_COUNT):
        try:
            agent = SubAgent(supervisor_queue, tool_manager, ltm, user_id="test_user_001")
            created_agents.append(agent)
            print(f"Created sub-agent {i+1}: {agent.agent_id}")
        except Exception as e:
            print(f"Failed to create sub-agent {i+1}: {e}")
            break
    
    print("\n=== Force Destroy All Sub-Agents ===")
    SubAgent.force_destroy_all()
