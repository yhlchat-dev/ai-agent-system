#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Process Perception Module

Features:
1. Process monitoring
2. Process list retrieval
3. Process status detection
4. Process resource usage
"""
import time
from typing import Dict, Any, List, Optional


class ProcessMonitor:
    """Process Monitor: System process status perception"""
    
    def __init__(self):
        """Initialize process monitor"""
        self.process_history = []
        self.max_history = 100
        
        try:
            import psutil
            self.psutil = psutil
            self.available = True
            print("[ProcessMonitor] psutil available, full process monitoring functionality")
        except ImportError:
            self.psutil = None
            self.available = False
            print("[ProcessMonitor] psutil unavailable, process monitoring functionality limited")
    
    def get_running_processes(self) -> List[Dict[str, Any]]:
        """
        Get running process list
        
        :return: Process list
        """
        if not self.available:
            return []
        
        try:
            processes = []
            
            for proc in self.psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
                try:
                    process_info = {
                        "pid": proc.info['pid'],
                        "name": proc.info['name'],
                        "cpu_percent": proc.info['cpu_percent'] or 0.0,
                        "memory_percent": proc.info['memory_percent'] or 0.0,
                        "status": proc.info['status']
                    }
                    processes.append(process_info)
                except (self.psutil.NoSuchProcess, self.psutil.AccessDenied):
                    continue
            
            processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
            
            self.process_history.append({
                "time": time.time(),
                "count": len(processes),
                "top_processes": processes[:10]
            })
            
            if len(self.process_history) > self.max_history:
                self.process_history.pop(0)
            
            return processes
        except Exception as e:
            print(f"[ProcessMonitor] Failed to get process list: {e}")
            return []
    
    def get_process_by_name(self, process_name: str) -> Optional[Dict[str, Any]]:
        """
        Find process by name
        
        :param process_name: Process name
        :return: Process info or None
        """
        if not self.available:
            return None
        
        try:
            for proc in self.psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
                try:
                    if process_name.lower() in proc.info['name'].lower():
                        return {
                            "pid": proc.info['pid'],
                            "name": proc.info['name'],
                            "cpu_percent": proc.info['cpu_percent'] or 0.0,
                            "memory_percent": proc.info['memory_percent'] or 0.0,
                            "status": proc.info['status']
                        }
                except (self.psutil.NoSuchProcess, self.psutil.AccessDenied):
                    continue
            
            return None
        except Exception as e:
            print(f"[ProcessMonitor] Failed to find process: {e}")
            return None
    
    def get_process_by_pid(self, pid: int) -> Optional[Dict[str, Any]]:
        """
        Find process by PID
        
        :param pid: Process ID
        :return: Process info or None
        """
        if not self.available:
            return None
        
        try:
            proc = self.psutil.Process(pid)
            return {
                "pid": proc.pid,
                "name": proc.name(),
                "cpu_percent": proc.cpu_percent(),
                "memory_percent": proc.memory_percent(),
                "status": proc.status()
            }
        except (self.psutil.NoSuchProcess, self.psutil.AccessDenied) as e:
            print(f"[ProcessMonitor] Failed to find process: {e}")
            return None
    
    def get_system_stats(self) -> Dict[str, Any]:
        """
        Get system statistics
        
        :return: System statistics
        """
        if not self.available:
            return {
                "cpu_percent": 0.0,
                "memory_percent": 0.0,
                "process_count": 0
            }
        
        try:
            return {
                "cpu_percent": self.psutil.cpu_percent(interval=1),
                "memory_percent": self.psutil.virtual_memory().percent,
                "process_count": len(self.psutil.pids())
            }
        except Exception as e:
            print(f"[ProcessMonitor] Failed to get system stats: {e}")
            return {
                "cpu_percent": 0.0,
                "memory_percent": 0.0,
                "process_count": 0
            }
    
    def is_process_running(self, process_name: str) -> bool:
        """
        Check if process is running
        
        :param process_name: Process name
        :return: Whether running
        """
        return self.get_process_by_name(process_name) is not None
    
    def kill_process(self, pid: int) -> bool:
        """
        Terminate process
        
        :param pid: Process ID
        :return: Whether successful
        """
        if not self.available:
            print("[ProcessMonitor] psutil unavailable, cannot terminate process")
            return False
        
        try:
            proc = self.psutil.Process(pid)
            proc.terminate()
            print(f"[ProcessMonitor] Process terminated: {pid}")
            return True
        except (self.psutil.NoSuchProcess, self.psutil.AccessDenied) as e:
            print(f"[ProcessMonitor] Failed to terminate process: {e}")
            return False
    
    def get_top_processes(self, limit: int = 10, by: str = 'cpu') -> List[Dict[str, Any]]:
        """
        Get top resource-consuming processes
        
        :param limit: Return count
        :param by: Sort by ('cpu' or 'memory')
        :return: Process list
        """
        processes = self.get_running_processes()
        
        if by == 'memory':
            processes.sort(key=lambda x: x['memory_percent'], reverse=True)
        else:
            processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
