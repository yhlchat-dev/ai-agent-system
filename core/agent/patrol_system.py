#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Master Agent Patrol System

Features:
1. Prevent memory bloat
2. Data security review
3. Memory optimization
4. Sub-agent health check
5. Scheduled patrol mechanism
"""
import time
import threading
from typing import Optional, Dict, Any
from datetime import datetime


class MasterPatrolSystem:
    """Master Agent Patrol System: Anti-memory bloat + Data review + Health check"""
    
    def __init__(self, user_id: str, short_term=None, long_term=None, 
                 sub_agent_manager=None, patrol_interval: int = 60):
        """
        Initialize patrol system
        
        :param user_id: User ID
        :param short_term: Short-term memory instance
        :param long_term: Long-term memory instance
        :param sub_agent_manager: Sub-agent manager
        :param patrol_interval: Patrol interval (seconds, default 60s)
        """
        self.user_id = user_id
        self.short_term = short_term
        self.long_term = long_term
        self.sub_agent_manager = sub_agent_manager
        
        self.patrol_interval = patrol_interval
        self.max_memory_age = 300
        self.running = False
        self.patrol_thread = None
        
        self.patrol_count = 0
        self.last_patrol_time = None
        self.cleanup_stats = {
            "total_cleaned": 0,
            "sensitive_marked": 0,
            "optimizations": 0
        }
        
        print(f"[Patrol System] Initialized, patrol interval: {patrol_interval}s")
    
    def start(self):
        """Start patrol system"""
        if self.running:
            print("[Patrol System] Warning: Patrol system is already running")
            return
        
        self.running = True
        self.patrol_thread = threading.Thread(target=self._patrol_loop, daemon=True)
        self.patrol_thread.start()
        print("[Patrol System] Patrol system started")
    
    def _patrol_loop(self):
        """Patrol loop"""
        while self.running:
            try:
                self.patrol_count += 1
                self.last_patrol_time = datetime.now()
                
                print(f"\n[Patrol System] Patrol #{self.patrol_count} started...")
                
                self.data_cleanup()
                
                self.data_review()
                
                self.memory_optimize()
                
                self.sub_agent_health_check()
                
                print(f"[Patrol System] Patrol #{self.patrol_count} completed")
                
            except Exception as e:
                print(f"[Patrol System] Patrol error: {e}")
            
            finally:
                time.sleep(self.patrol_interval)
    
    def data_cleanup(self):
        """Clean up expired short-term memory, prevent memory bloat"""
        if not self.short_term:
            return
        
        try:
            deleted_count = 0
            
            if hasattr(self.short_term, 'cleanup_expired'):
                deleted_count = self.short_term.cleanup_expired(self.max_memory_age)
            
            elif hasattr(self.short_term, 'delete_old_logs'):
                cutoff_time = time.time() - self.max_memory_age
                self.short_term.delete_old_logs(cutoff_time)
                deleted_count = 1
            
            if deleted_count > 0:
                self.cleanup_stats["total_cleaned"] += deleted_count
                print(f"[Patrol System] Cleaned expired short-term memory: {deleted_count} records")
            else:
                print("[Patrol System] No expired data to clean")
                
        except Exception as e:
            print(f"[Patrol System] Data cleanup failed: {e}")
    
    def data_review(self):
        """Data security review: Sensitive information check + Redundancy marking"""
        if not self.short_term:
            return
        
        try:
            sensitive_count = 0
            
            all_memories = []
            if hasattr(self.short_term, 'get_all_memories'):
                all_memories = self.short_term.get_all_memories()
            elif hasattr(self.short_term, 'get_recent_logs'):
                all_memories = self.short_term.get_recent_logs(limit=1000)
            
            sensitive_keywords = ["phone", "bank card", "ID card", "password", "payment"]
            
            for item in all_memories:
                item_str = str(item)
                if any(keyword in item_str.lower() for keyword in sensitive_keywords):
                    if hasattr(self.short_term, 'mark_sensitive'):
                        self.short_term.mark_sensitive(item)
                    sensitive_count += 1
            
            if sensitive_count > 0:
                self.cleanup_stats["sensitive_marked"] += sensitive_count
                print(f"[Patrol System] Marked sensitive data: {sensitive_count} records")
            else:
                print("[Patrol System] No sensitive data to mark")
                
        except Exception as e:
            print(f"[Patrol System] Data review failed: {e}")
    
    def memory_optimize(self):
        """Memory optimization: Compression + Merge + Archive"""
        try:
            if self.short_term and hasattr(self.short_term, 'optimize_storage'):
                self.short_term.optimize_storage()
            
            if self.long_term and hasattr(self.long_term, 'compress_database'):
                self.long_term.compress_database()
            elif self.long_term and hasattr(self.long_term, 'optimize'):
                self.long_term.optimize()
            
            self.cleanup_stats["optimizations"] += 1
            print("[Patrol System] Memory optimization completed")
            
        except Exception as e:
            print(f"[Patrol System] Memory optimization failed: {e}")
    
    def sub_agent_health_check(self):
        """Sub-agent health check: Force cleanup of zombie processes"""
        if not self.sub_agent_manager:
            return
        
        try:
            stats = self.sub_agent_manager.get_stats()
            print(f"[Patrol System] Sub-agent status: {stats['total']}/{stats['max']} (usage: {stats['usage_rate']})")
            
            if hasattr(self.sub_agent_manager, '_cleanup_idle_agents'):
                self.sub_agent_manager._cleanup_idle_agents()
            
            stats_after = self.sub_agent_manager.get_stats()
            cleaned = stats['total'] - stats_after['total']
            
            if cleaned > 0:
                print(f"[Patrol System] Cleaned idle sub-agents: {cleaned}")
            
        except Exception as e:
            print(f"[Patrol System] Sub-agent health check failed: {e}")
    
    def stop(self):
        """Stop patrol system"""
        if not self.running:
            print("[Patrol System] Warning: Patrol system is not running")
            return
        
        self.running = False
        if self.patrol_thread:
            self.patrol_thread.join(timeout=5)
        print("[Patrol System] Patrol system stopped")
    
    def force_patrol(self):
        """Force execute one patrol"""
        print("[Patrol System] Force patrol started...")
        self.data_cleanup()
        self.data_review()
        self.memory_optimize()
        self.sub_agent_health_check()
        print("[Patrol System] Force patrol completed")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get patrol system statistics"""
        return {
            "running": self.running,
            "patrol_count": self.patrol_count,
            "last_patrol_time": self.last_patrol_time.isoformat() if self.last_patrol_time else None,
            "patrol_interval": self.patrol_interval,
            "max_memory_age": self.max_memory_age,
            "cleanup_stats": self.cleanup_stats.copy()
        }
    
    def update_config(self, patrol_interval: int = None, max_memory_age: int = None):
        """Update patrol configuration"""
        if patrol_interval is not None:
            self.patrol_interval = patrol_interval
            print(f"[Patrol System] Updated patrol interval: {patrol_interval}s")
        
        if max_memory_age is not None:
            self.max_memory_age = max_memory_age
            print(f"[Patrol System] Updated memory expiration time: {max_memory_age}s")
    
    def __del__(self):
        """Destructor: Ensure patrol system stops"""
        if self.running:
            self.stop()
