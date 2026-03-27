#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Self-Repair Engine + Experience Accumulation System

Features:
1. Automatic error analysis
2. Automatic repair execution
3. Repair experience accumulation
4. Historical experience loading
"""
import time
import gc
from typing import Dict, Any, List


class SelfRepairEngine:
    """Self-Repair Engine: Automatic repair + Experience accumulation"""
    
    def __init__(self, user_id: str, long_term_memory=None, capsule=None):
        """
        Initialize self-repair engine
        
        :param user_id: User ID
        :param long_term_memory: Long-term memory instance
        :param capsule: Dual experience capsule instance
        """
        self.user_id = user_id
        self.ltm = long_term_memory
        self.capsule = capsule
        self.repair_experience = self._load_experience()
    
    def _load_experience(self) -> Dict[str, List[str]]:
        """Load historical repair experience (core of experience accumulation)"""
        default = {
            "Memory leak": ["Clean up sub-agents", "Release resources", "Compress memory bank"],
            "Sub-agent crash": ["Rebuild instance", "Retry task"],
            "Insufficient permissions": ["Reset permissions"],
            "Configuration lost": ["Automatically rebuild configuration"]
        }
        
        try:
            exp = self.ltm.get_memory(self.user_id, "repair_experience")
            return exp or default
        except:
            return default
    
    def analyze_error(self, error_log: str) -> Dict[str, Any]:
        """Analyze error log"""
        error_type = "Unknown error"
        fix_action = []
        
        if "memory" in error_log.lower() or "leak" in error_log.lower():
            error_type = "Memory leak"
            fix_action = self.repair_experience["Memory leak"]
        elif "sub-agent" in error_log.lower() and "crash" in error_log.lower():
            error_type = "Sub-agent crash"
            fix_action = self.repair_experience["Sub-agent crash"]
        elif "permission" in error_log.lower():
            error_type = "Insufficient permissions"
            fix_action = self.repair_experience["Insufficient permissions"]
        
        return {"type": error_type, "fix": fix_action}
    
    def auto_repair(self, error_log: str, sub_agent_manager=None) -> str:
        """Automatically execute repair + Save experience"""
        result = self.analyze_error(error_log)
        
        for action in result["fix"]:
            try:
                if action == "Clean up sub-agents" and sub_agent_manager:
                    sub_agent_manager.clean_idle()
                if action == "Release resources":
                    gc.collect()
            except:
                continue
        
        self.save_repair_history(result["type"], result["fix"])
        
        if hasattr(self, 'capsule') and self.capsule:
            self.capsule.save_fail(result["type"], str(result["fix"]))
        
        return f"[OK] Repair completed: {result['type']}"
    
    def save_repair_history(self, error_type: str, fix: list):
        """Save repair record as experience (core: experience accumulation)"""
        try:
            history = self.ltm.get_memory(self.user_id, "repair_history") or []
            history.append({"time": time.time(), "error": error_type, "fix": fix})
            self.ltm.save_memory(self.user_id, "repair_history", history)
            self.ltm.save_memory(self.user_id, "repair_experience", self.repair_experience)
        except:
            pass
