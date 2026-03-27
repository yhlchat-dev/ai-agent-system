#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Sub-Agent Manager

Features:
1. Singleton pattern management
2. Sub-agent quantity control (max 30)
3. Automatic cleanup of idle agents
4. Thread-safe management
"""
import time
import threading
from typing import Dict, Optional, Any


class SubAgentManager:
    """Sub-Agent Manager: Singleton pattern + Quantity control + Auto cleanup"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        """Singleton pattern: Ensure only one manager instance globally"""
        with cls._lock:
            if not cls._instance:
                cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, max_agents: int = 30):
        """
        Initialize sub-agent manager
        
        :param max_agents: Maximum sub-agent count (default 30)
        """
        if not hasattr(self, 'initialized'):
            self.max_agents = max_agents
            self.agents: Dict[str, Dict[str, Any]] = {}
            self.lock = threading.RLock()
            self.initialized = True
            print(f"[SubAgentManager] Initialized, max agent count: {max_agents}")
    
    def create_agent(self, agent_id: str, agent_instance: Any = None, 
                     metadata: Dict = None) -> Optional[str]:
        """
        Create sub-agent
        
        :param agent_id: Agent ID
        :param agent_instance: Agent instance (optional)
        :param metadata: Agent metadata (optional)
        :return: Agent ID or None
        """
        with self.lock:
            if len(self.agents) >= self.max_agents:
                self._cleanup_idle_agents()
                
                if len(self.agents) >= self.max_agents:
                    print(f"[SubAgentManager] Error: Maximum sub-agent count reached: {self.max_agents}")
                    return None
            
            self.agents[agent_id] = {
                "instance": agent_instance,
                "created_at": time.time(),
                "last_active": time.time(),
                "metadata": metadata or {}
            }
            
            print(f"[SubAgentManager] Created sub-agent: {agent_id} (total: {len(self.agents)}/{self.max_agents})")
            return agent_id
    
    def get_agent(self, agent_id: str) -> Optional[Any]:
        """
        Get sub-agent instance
        
        :param agent_id: Agent ID
        :return: Agent instance or None
        """
        with self.lock:
            if agent_id in self.agents:
                self.agents[agent_id]["last_active"] = time.time()
                return self.agents[agent_id]["instance"]
        return None
    
    def update_agent_activity(self, agent_id: str) -> bool:
        """
        Update agent activity time
        
        :param agent_id: Agent ID
        :return: Success or not
        """
        with self.lock:
            if agent_id in self.agents:
                self.agents[agent_id]["last_active"] = time.time()
                return True
        return False
    
    def destroy_agent(self, agent_id: str) -> bool:
        """
        Destroy sub-agent
        
        :param agent_id: Agent ID
        :return: Success or not
        """
        with self.lock:
            if agent_id in self.agents:
                agent_data = self.agents[agent_id]
                
                if agent_data["instance"] and hasattr(agent_data["instance"], 'destroy'):
                    try:
                        agent_data["instance"].destroy()
                    except Exception as e:
                        print(f"[SubAgentManager] Warning: Agent destruction failed: {e}")
                
                del self.agents[agent_id]
                print(f"[SubAgentManager] Destroyed sub-agent: {agent_id} (remaining: {len(self.agents)}/{self.max_agents})")
                return True
        return False
    
    def _cleanup_idle_agents(self, idle_timeout: int = 300):
        """
        Cleanup idle agents (default 5 minutes of inactivity)
        
        :param idle_timeout: Idle timeout (seconds)
        """
        now = time.time()
        with self.lock:
            to_delete = [
                agent_id for agent_id, data in self.agents.items()
                if now - data["last_active"] > idle_timeout
            ]
            
            for agent_id in to_delete:
                self.destroy_agent(agent_id)
            
            if to_delete:
                print(f"[SubAgentManager] Cleaned idle agents: {len(to_delete)}")
    
    def destroy_all_agents(self) -> int:
        """
        Destroy all sub-agents
        
        :return: Number of destroyed agents
        """
        with self.lock:
            agent_ids = list(self.agents.keys())
            for agent_id in agent_ids:
                self.destroy_agent(agent_id)
        print(f"[SubAgentManager] Destroyed all agents: {len(agent_ids)}")
        return len(agent_ids)
    
    def get_stats(self) -> dict:
        """
        Get manager statistics
        
        :return: Statistics info
        """
        with self.lock:
            now = time.time()
            
            active_count = sum(
                1 for data in self.agents.values()
                if now - data["last_active"] <= 300
            )
            
            return {
                "total": len(self.agents),
                "active": active_count,
                "idle": len(self.agents) - active_count,
                "max": self.max_agents,
                "agents": list(self.agents.keys()),
                "usage_rate": f"{len(self.agents) / self.max_agents * 100:.1f}%"
            }
    
    def get_agent_info(self, agent_id: str) -> Optional[Dict]:
        """
        Get agent detailed info
        
        :param agent_id: Agent ID
        :return: Agent info or None
        """
        with self.lock:
            if agent_id in self.agents:
                data = self.agents[agent_id]
                now = time.time()
                
                return {
                    "agent_id": agent_id,
                    "created_at": data["created_at"],
                    "last_active": data["last_active"],
                    "idle_time": now - data["last_active"],
                    "lifetime": now - data["created_at"],
                    "metadata": data["metadata"]
                }
        return None
    
    def list_agents(self) -> list:
        """
        List all agent IDs
        
        :return: Agent ID list
        """
        with self.lock:
            return list(self.agents.keys())
    
    def force_cleanup(self, idle_timeout: int = 60):
        """
        Force cleanup idle agents (used when memory is tight)
        
        :param idle_timeout: Idle timeout (seconds, default 1 minute)
        """
        print(f"[SubAgentManager] Force cleanup idle agents (timeout: {idle_timeout}s)")
        self._cleanup_idle_agents(idle_timeout)


_sub_agent_manager = None


def get_sub_agent_manager(max_agents: int = 30) -> SubAgentManager:
    """
    Get global sub-agent manager instance
    
    :param max_agents: Maximum agent count
    :return: SubAgentManager instance
    """
    global _sub_agent_manager
    if _sub_agent_manager is None:
        _sub_agent_manager = SubAgentManager(max_agents)
    return _sub_agent_manager
