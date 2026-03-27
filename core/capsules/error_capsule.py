#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Error Capsule: Store Agent's error/exception/work log records

Three-level Classification:
1. Error log (error): System errors, crashes, execution failures
2. Exception log (warning): Logic exceptions, data exceptions, warning messages
3. Work log (info): Agent running records, task execution, interaction statistics
"""
import time
from datetime import datetime
from typing import Dict, List, Optional
from .agent_capsule import AgentCapsule


class ErrorCapsule(AgentCapsule):
    """Error Capsule: Inherits AgentCapsule, specifically stores error information"""
    
    LOG_LEVELS = {
        "error": {
            "priority": 1,
            "description": "Error log: System errors, crashes, execution failures"
        },
        "warning": {
            "priority": 2,
            "description": "Exception log: Logic exceptions, data exceptions, warning messages"
        },
        "info": {
            "priority": 3,
            "description": "Work log: Agent running records, task execution, interaction statistics"
        }
    }
    
    def __init__(self, agent_id, error_msg, error_type="error", 
                 traceback="", log_level="error", metadata=None):
        """
        Initialize error capsule
        
        :param agent_id: Agent ID
        :param error_msg: Error message
        :param error_type: Error type (e.g. ValueError/TypeError)
        :param traceback: Error traceback (optional)
        :param log_level: Log level (error/warning/info)
        :param metadata: Additional metadata
        """
        super().__init__(
            agent_id=agent_id,
            content=f"[{error_type}] {error_msg}",
            capsule_type=log_level
        )
        
        self.error_type = error_type
        self.traceback = traceback
        self.log_level = log_level
        self.metadata = metadata or {}
        self.timestamp = datetime.now().isoformat()
        
        if log_level not in self.LOG_LEVELS:
            self.log_level = "error"
    
    def to_dict(self) -> Dict:
        """
        Extended dict format, includes error details
        
        :return: Dict format data
        """
        base_dict = super().to_dict()
        base_dict.update({
            "error_type": self.error_type,
            "traceback": self.traceback,
            "log_level": self.log_level,
            "log_level_desc": self.LOG_LEVELS.get(self.log_level, {}).get("description", ""),
            "timestamp": self.timestamp,
            "metadata": self.metadata
        })
        return base_dict
    
    @classmethod
    def create_error_log(cls, agent_id: str, error_msg: str, 
                         error_type: str = "SystemError", 
                         traceback: str = "", metadata: Dict = None) -> 'ErrorCapsule':
        """
        Create error log capsule (Category 1)
        
        :param agent_id: Agent ID
        :param error_msg: Error message
        :param error_type: Error type
        :param traceback: Error traceback
        :param metadata: Additional metadata
        :return: Error capsule instance
        """
        return cls(
            agent_id=agent_id,
            error_msg=error_msg,
            error_type=error_type,
            traceback=traceback,
            log_level="error",
            metadata=metadata
        )
    
    @classmethod
    def create_warning_log(cls, agent_id: str, warning_msg: str,
                           warning_type: str = "LogicWarning",
                           metadata: Dict = None) -> 'ErrorCapsule':
        """
        Create exception log capsule (Category 2)
        
        :param agent_id: Agent ID
        :param warning_msg: Warning message
        :param warning_type: Warning type
        :param metadata: Additional metadata
        :return: Exception capsule instance
        """
        return cls(
            agent_id=agent_id,
            error_msg=warning_msg,
            error_type=warning_type,
            traceback="",
            log_level="warning",
            metadata=metadata
        )
    
    @classmethod
    def create_work_log(cls, agent_id: str, action: str, result: str,
                        metadata: Dict = None) -> 'ErrorCapsule':
        """
        Create work log capsule (Category 3)
        
        :param agent_id: Agent ID
        :param action: Executed action
        :param result: Execution result
        :param metadata: Additional metadata
        :return: Work log capsule instance
        """
        work_msg = f"{action}: {result}"
        return cls(
            agent_id=agent_id,
            error_msg=work_msg,
            error_type="WorkLog",
            traceback="",
            log_level="info",
            metadata=metadata
        )
    
    def get_priority(self) -> int:
        """
        Get log priority
        
        :return: Priority (1=highest, 3=lowest)
        """
        return self.LOG_LEVELS.get(self.log_level, {}).get("priority", 3)
    
    def is_critical(self) -> bool:
        """
        Determine if critical error
        
        :return: Whether critical
        """
        return self.log_level == "error"
    
    def get_summary(self) -> str:
        """
        Get log summary
        
        :return: Summary string
        """
        level_emoji = {
            "error": "[X]",
            "warning": "[!]",
            "info": "[i]"
        }
        
        emoji = level_emoji.get(self.log_level, "[?]")
        return f"{emoji} [{self.log_level.upper()}] {self.error_type}: {self.content[:50]}..."


class WorkLogCapsule(ErrorCapsule):
    """Work Log Capsule: Specifically stores Agent running records"""
    
    def __init__(self, agent_id: str, action: str, result: str, 
                 task_id: str = None, duration: float = None):
        """
        Initialize work log capsule
        
        :param agent_id: Agent ID
        :param action: Executed action
        :param result: Execution result
        :param task_id: Task ID
        :param duration: Execution duration (seconds)
        """
        metadata = {
            "task_id": task_id,
            "duration": duration,
            "timestamp": datetime.now().isoformat()
        }
        
        super().__init__(
            agent_id=agent_id,
            error_msg=f"{action}: {result}",
            error_type="WorkLog",
            traceback="",
            log_level="info",
            metadata=metadata
        )
        
        self.action = action
        self.result = result
        self.task_id = task_id
        self.duration = duration
    
    def to_dict(self) -> Dict:
        """
        Extended dict format
        
        :return: Dict format data
        """
        base_dict = super().to_dict()
        base_dict.update({
            "action": self.action,
            "result": self.result,
            "task_id": self.task_id,
            "duration": self.duration
        })
        return base_dict


class WarningLogCapsule(ErrorCapsule):
    """Exception Log Capsule: Specifically stores exceptions and warnings"""
    
    def __init__(self, agent_id: str, warning_msg: str,
                 warning_type: str = "LogicWarning",
                 impact: str = "low", metadata: Dict = None):
        """
        Initialize exception log capsule
        
        :param agent_id: Agent ID
        :param warning_msg: Warning message
        :param warning_type: Warning type
        :param impact: Impact level (low/medium/high)
        :param metadata: Additional metadata
        """
        if metadata is None:
            metadata = {}
        
        metadata["impact"] = impact
        
        super().__init__(
            agent_id=agent_id,
            error_msg=warning_msg,
            error_type=warning_type,
            traceback="",
            log_level="warning",
            metadata=metadata
        )
        
        self.warning_type = warning_type
        self.impact = impact
    
    def to_dict(self) -> Dict:
        """
        Extended dict format
        
        :return: Dict format data
        """
        base_dict = super().to_dict()
        base_dict.update({
            "warning_type": self.warning_type,
            "impact": self.impact
        })
        return base_dict
