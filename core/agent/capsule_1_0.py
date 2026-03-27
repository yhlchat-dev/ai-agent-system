#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
1.0 Dual Experience Capsule System

Features:
1. Success Capsule: Store successful task experiences
2. Failure Capsule: Store failure/error repair experiences
3. Experience Accumulation: Learn from history
"""
import time
from typing import List, Dict, Any


class DoubleCapsule:
    """1.0 Dual Experience Capsule: Success Capsule + Failure Capsule"""
    
    def __init__(self, user_id: str, ltm=None):
        """
        Initialize dual experience capsule
        
        :param user_id: User ID
        :param ltm: Long-term memory instance
        """
        self.user_id = user_id
        self.ltm = ltm
        
        self.success_capsule = self._load("success_capsule")
        self.fail_capsule = self._load("fail_capsule")
    
    def _load(self, name: str) -> List[Dict]:
        """
        Load capsule data from long-term memory
        
        :param name: Capsule name
        :return: Capsule data list
        """
        if not self.ltm or not hasattr(self.ltm, 'get_memory'):
            return []
        
        try:
            data = self.ltm.get_memory(self.user_id, name)
            return data if data else []
        except:
            return []
    
    def save_success(self, task: str, result: str):
        """
        Save successful experience
        
        :param task: Task description
        :param result: Successful result
        """
        data = {
            "time": time.time(),
            "task": task,
            "result": result
        }
        
        self.success_capsule.append(data)
        
        if self.ltm and hasattr(self.ltm, 'save_memory'):
            try:
                self.ltm.save_memory(self.user_id, "success_capsule", self.success_capsule)
            except:
                pass
    
    def save_fail(self, error: str, fix: str):
        """
        Save failure/error repair experience
        
        :param error: Error description
        :param fix: Repair solution
        """
        data = {
            "time": time.time(),
            "error": error,
            "fix": fix
        }
        
        self.fail_capsule.append(data)
        
        if self.ltm and hasattr(self.ltm, 'save_memory'):
            try:
                self.ltm.save_memory(self.user_id, "fail_capsule", self.fail_capsule)
            except:
                pass
    
    def get_success_experience(self, limit: int = 10) -> List[Dict]:
        """
        Get successful experiences
        
        :param limit: Return quantity limit
        :return: Success experience list
        """
        return self.success_capsule[-limit:] if self.success_capsule else []
    
    def get_fail_experience(self, limit: int = 10) -> List[Dict]:
        """
        Get failure experiences
        
        :param limit: Return quantity limit
        :return: Failure experience list
        """
        return self.fail_capsule[-limit:] if self.fail_capsule else []
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get capsule statistics
        
        :return: Statistics information
        """
        return {
            "success_count": len(self.success_capsule),
            "fail_count": len(self.fail_capsule),
            "total_experience": len(self.success_capsule) + len(self.fail_capsule)
        }
