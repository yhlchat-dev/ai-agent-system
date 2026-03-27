# -*- coding: utf-8 -*-
"""
Main Agent Core: Complete Scheduling Logic (Priority + Load Balancing + Timeout Retry)
"""

import sys
import os
import argparse
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(ROOT_DIR, '.env'))

print(f"[ENV] LLM_MODEL = {os.getenv('LLM_MODEL')}")
print(f"[ENV] DEEPSEEK_API_KEY = {os.getenv('DEEPSEEK_API_KEY')[:10]}..." if os.getenv('DEEPSEEK_API_KEY') else "[ENV] DEEPSEEK_API_KEY not set")

from core.llm.factory import LLMFactory

os.environ["CHROMA_TELEMETRY_DISABLED"] = "true"
import logging
for logger in ["chromadb", "httpx", "sentence_transformers", "huggingface_hub"]:
    logging.getLogger(logger).setLevel(logging.CRITICAL)

sys.path.append(ROOT_DIR)

import queue
import threading
import time
import uuid
from datetime import datetime
from typing import Any

try:
    from core.agent.agent_brain import AgentBrain
except ImportError:
    AgentBrain = None

try:
    from sub_agent.sub_agent import SubAgent
except ImportError:
    SubAgent = None

try:
    from core.agent.memory_handler import MemoryHandler
except ImportError:
    MemoryHandler = None

try:
    from infra.log_manager import Logger, LogItem
except ImportError:
    Logger = None

try:
    from core.memory.short_term_memory import ShortTermMemory as RealShortTermMemory
except ImportError:
    RealShortTermMemory = None

try:
    from core.memory.long_term_memory import LongTermMemory as RealLongTermMemory
except ImportError:
    RealLongTermMemory = None

try:
    from core.user.user_data import UserData as RealUserData
except ImportError:
    RealUserData = None

try:
    from core.capsules.capsule_manager import CapsuleManager as RealCapsuleManager
except ImportError:
    RealCapsuleManager = None

try:
    from infra.config import SHORT_TERM_DB, get_user_data_dir
except ImportError:
    SHORT_TERM_DB = None
    def get_user_data_dir(user_id):
        return Path(f"data/{user_id}")

from core.agent.utils import (
    clean_text,
    format_timestamp,
    get_user_id_from_context,
    log_agent_action
)


class AgentCore:
    """Main Agent Core: Complete Scheduling Logic + Task Priority + Load Balancing + Complete Memory System"""
    def __init__(self, data_dir=None, feishu_enabled=False, llm=None):
        self.data_dir = data_dir or os.path.join(ROOT_DIR, "data")
        self.is_running = True
        self.feishu_enabled = feishu_enabled
        
        self.context_manager = ContextManager(max_history_len=50)
        
        self._init_memory_system()
        
        self.sub_agent_manager = SubAgentManager(max_sub_agents=30)
        self.reply_generator = ReplyGenerator(style="Butler", max_length=500)
        self.patrol_system = PatrolSystem(patrol_interval=60)
        self.tool_invoker = ToolInvoker(data_dir=self.data_dir)
        
        self.patrol_system.set_sub_agent_manager(self.sub_agent_manager)
        self.patrol_system.set_memory_handler(self.memory_handler)
        self.patrol_system.set_tool_invoker(self.tool_invoker)
        
        self.task_priority = {"critical": 0, "high": 1, "normal": 2, "low": 3}
        self.tool_timeout = 30
        self.max_retry = 2
        self.task_queue = queue.PriorityQueue()
        self.worker_threads = []
        self.max_workers = 5
        
        self.feishu_service = None
        if feishu_enabled:
            self._init_feishu_service()
        
        self._start_worker_threads()
        self.patrol_system.start_patrol()
        
        if llm is not None:
            self.llm = llm
            log_agent_action("LLM", "system", "LLM client injected externally")
        else:
            try:
                self.llm = LLMFactory.from_env()
                log_agent_action("LLM", "system", f"LLM client initialized successfully - Model type: {os.getenv('LLM_MODEL', 'qwen')}")
            except Exception as e:
                log_agent_action("LLM", "system", f"LLM client initialization failed: {e}")
                self.llm = None
        
        log_agent_action("Initialize Main Agent", "system", f"Scheduling system started | Worker threads: {self.max_workers} | Task priority: critical>high>normal>low")
        log_agent_action("Memory System", "system", "Short-term memory + Long-term memory + User data + Capsule system initialized")
        
        if feishu_enabled:
            log_agent_action("Feishu Integration", "system", "Feishu service enabled")
            
    def _init_memory_system(self):
        """Initialize complete memory system (standard storage pipeline)"""
        user_id = 'default'
        
        try:
            from core.memory.temp_database import TempDatabase
            self.temp_database = TempDatabase()
            log_agent_action("Memory System", "system", "Temp database initialized successfully")
        except Exception as e:
            log_agent_action("Memory System", "system", f"Temp database initialization failed: {e}")
            self.temp_database = None
        
        try:
            from core.memory.encrypted_memory import EncryptedMemory
            self.encrypted_memory = EncryptedMemory()
            log_agent_action("Memory System", "system", "Encrypted memory initialized successfully")
        except Exception as e:
            log_agent_action("Memory System", "system", f"Encrypted memory initialization failed: {e}")
            self.encrypted_memory = None
        
        if RealShortTermMemory:
            try:
                self.short_term_memory = RealShortTermMemory(user_id='default', db_path=None)
                log_agent_action("Memory System", "system", "Short-term memory initialized successfully")
            except Exception as e:
                log_agent_action("Memory System", "system", f"Short-term memory initialization failed: {e}")
                self.short_term_memory = None
        else:
            self.short_term_memory = None
        
        if RealLongTermMemory:
            try:
                self.long_term_memory = RealLongTermMemory(user_id='default', data_dir=None)
                log_agent_action("Memory System", "system", "Long-term memory initialized successfully")
            except Exception as e:
                log_agent_action("Memory System", "system", f"Long-term memory initialization failed: {e}")
                self.long_term_memory = None
        else:
            self.long_term_memory = None
        
        if RealUserData:
            try:
                self.user_data_manager = RealUserData(user_id='default', data_dir=None)
                log_agent_action("Memory System", "system", "User data manager initialized successfully")
            except Exception as e:
                log_agent_action("Memory System", "system", f"User data manager initialization failed: {e}")
                self.user_data_manager = None
        else:
            self.user_data_manager = None
        
        if RealCapsuleManager:
            try:
                self.capsule_manager = RealCapsuleManager(db_path=None, data_dir=None)
                log_agent_action("Memory System", "system", "Capsule manager initialized successfully")
            except Exception as e:
                log_agent_action("Memory System", "system", f"Capsule manager initialization failed: {e}")
                self.capsule_manager = None
        else:
            self.capsule_manager = None
        
        try:
            from core.memory.archive_scheduler import ArchiveScheduler
            from core.memory.media_manager import MediaStorageManager
            from core.agent.agent_logic import AgentCoreLogic
            from core.agent.curiosity_system import CuriositySystem
            from core.agent.sub_agent_manager import SubAgentManager
            from core.agent.patrol_system import MasterPatrolSystem
            from core.agent.capsule_1_0 import DoubleCapsule
            from queue import Queue
            if self.short_term_memory and self.long_term_memory:
                self.archive_scheduler = ArchiveScheduler(
                    short_term_memory=self.short_term_memory,
                    long_term_memory=self.long_term_memory,
                    archive_days=5
                )
                self.archive_scheduler.start()
                log_agent_action("Memory System", "system", "Archive scheduler initialized successfully (5-day auto archive)")
                
                self.media_manager = MediaStorageManager(user_id)
                log_agent_action("Memory System", "system", "Media storage manager initialized successfully")
                
                self.agent_logic = AgentCoreLogic(user_id, self.memory_handler, self.media_manager)
                log_agent_action("Memory System", "system", "Agent core logic initialized successfully")
                
                self.curiosity_system = CuriositySystem(user_id)
                log_agent_action("Memory System", "system", "Curiosity system initialized successfully")
                
                self.sub_agent_manager = SubAgentManager(max_agents=30)
                log_agent_action("Memory System", "system", "Sub-agent manager initialized successfully")
                
                self.supervisor_queue = Queue()
                log_agent_action("Memory System", "system", "Task queue initialized successfully")
                
                self.patrol_system = MasterPatrolSystem(
                    user_id, self.short_term_memory, self.long_term_memory, self.sub_agent_manager
                )
                log_agent_action("Memory System", "system", "Patrol system initialized successfully")
                
                self.capsule = DoubleCapsule(user_id, self.long_term_memory)
                log_agent_action("Memory System", "system", "Double experience capsule initialized successfully")
                
                from core.agent.self_repair import SelfRepairEngine
                self.self_repair_engine = SelfRepairEngine(
                    user_id, self.long_term_memory, self.capsule
                )
                log_agent_action("Memory System", "system", "Self-repair engine initialized successfully (bound to failure capsule)")
            else:
                self.archive_scheduler = None
        except Exception as e:
            log_agent_action("Memory System", "system", f"Archive scheduler initialization failed: {e}")
            self.archive_scheduler = None
        
        if MemoryHandler:
            try:
                self.memory_handler = MemoryHandler(data_dir=self.data_dir)
                log_agent_action("Memory System", "system", "Memory handler initialized successfully")
            except Exception as e:
                log_agent_action("Memory System", "system", f"Memory handler initialization failed: {e}")
                self.memory_handler = None
        else:
            self.memory_handler = None
        
        if self.temp_database and self.short_term_memory:
            self.temp_database.start_sync_scheduler(self.short_term_memory)
            log_agent_action("Memory System", "system", "Temp database sync scheduler started")
        
        try:
            from core.perception.input_perception import InputPerception
            from core.perception.screen_perception import ScreenMirror
            from core.perception.process_perception import ProcessMonitor
            
            self.input_perception = InputPerception()
            self.screen_mirror = ScreenMirror()
            self.process_monitor = ProcessMonitor()
            log_agent_action("Perception Layer", "system", "Desktop perception layer initialized successfully")
        except Exception as e:
            log_agent_action("Perception Layer", "system", f"Desktop perception layer initialization failed: {e}")
            self.input_perception = None
            self.screen_mirror = None
            self.process_monitor = None
        
        log_agent_action("Storage Pipeline", "system", "Standard pipeline: New info -> Temp DB -> Short-term Memory -> Long-term Memory")
        
    def _call_llm(self, user_id, message):
        """Call LLM to generate response"""
        if not self.llm:
            return "Sorry, LLM service is not initialized, please check configuration."

        system_prompt = "You are an intelligent assistant that can access memory and tools. Please provide help based on the user's message."

        try:
            response = self.llm.generate(
                prompt=message,
                system=system_prompt,
                temperature=0.7,
                max_tokens=4096 
            )
            if response.get("success"):
                return response.get("content", "Sorry, I cannot answer at the moment.")
            else:
                return f"LLM call failed: {response.get('error', 'Unknown error')}"
        except Exception as e:
            log_agent_action("LLM Call Exception", user_id, str(e))
            return f"Processing error: {str(e)}"    
    
    def _handle_message_task(self, user_id, message):
        """Actual logic for handling user messages (integrated with complete memory system)"""
        user_state = self.context_manager.get_state(user_id)
        if user_state.get("current_task") == "Urgent":
            log_agent_action("Context Awareness", user_id, "Urgent task detected, elevating processing priority")

        user_sub_agents = [sa for sa in self.sub_agent_manager.sub_agent_pool.values() if sa["user_id"] == user_id]
        if len(user_sub_agents) >= self.sub_agent_manager.max_sub_agents // 2:
            log_agent_action("Load Balancing", user_id, f"Sub-agent count high ({len(user_sub_agents)}/{self.sub_agent_manager.max_sub_agents//2}), limiting new creation")

        if "create" in message and "subagent" in message.lower():
            import re
            count_match = re.search(r"(\d+)", message)
            create_count = int(count_match.group(1)) if count_match else 1
            if create_count > self.sub_agent_manager.max_sub_agents:
                create_count = self.sub_agent_manager.max_sub_agents
                log_agent_action("Sub-agent Limit", user_id, f"Maximum {create_count} sub-agents allowed")
            for i in range(create_count):
                sub_agent = self.sub_agent_manager.create_sub_agent(user_id)
                log_agent_action("Create Sub-agent", user_id, f"Successfully created sub-agent {i+1}/{create_count}: {sub_agent.agent_id}")

        if "destroy all subagents" in message:
            destroy_count = 0
            for agent_id, agent_info in list(self.sub_agent_manager.sub_agent_pool.items()):
                agent_instance = agent_info["instance"]
                agent_instance.destroy()
                del self.sub_agent_manager.sub_agent_pool[agent_id]
                destroy_count += 1
                log_agent_action("Destroy Sub-agent", user_id, f"Destroyed: {agent_id}")
            log_agent_action("Batch Destroy Complete", user_id, f"Total {destroy_count} sub-agents destroyed")

        message = clean_text(message)
        self.context_manager.add_message(user_id, "user", message)
        
        self._save_user_info_to_memory(user_id, message)
        
        if self.short_term_memory:
            try:
                self.short_term_memory.insert_log({
                    "timestamp": time.time(),
                    "environment": "production",
                    "action": "user_message",
                    "result": message,
                    "success_rate": 1.0,
                    "trace_id": str(uuid.uuid4())
                })
                log_agent_action("Short-term Memory", user_id, f"Saved user message: {message[:50]}...")
            except Exception as e:
                log_agent_action("Short-term Memory", user_id, f"Save failed: {e}")
        
        related_memories = []
        if self.long_term_memory:
            try:
                related_memories = self.long_term_memory.search_memory(user_id, message, top_k=5)
                log_agent_action("Long-term Memory", user_id, f"Retrieved {len(related_memories)} related memories")
            except Exception as e:
                log_agent_action("Long-term Memory", user_id, f"Retrieval failed: {e}")
        
        related_capsules = []
        if self.capsule_manager:
            try:
                capsule_results = self.capsule_manager.get_capsules_by_agent(user_id, limit=3, capsule_type="experience")
                related_capsules = capsule_results if capsule_results else []
                log_agent_action("Capsule System", user_id, f"Retrieved {len(related_capsules)} related capsules")
            except Exception as e:
                log_agent_action("Capsule System", user_id, f"Retrieval failed: {e}")
        
        user_preferences = {}
        if self.user_data_manager:
            try:
                user_preferences = self.user_data_manager.get_user_config(user_id)
                log_agent_action("User Data", user_id, f"Retrieved user preferences: {len(user_preferences)} items")
            except Exception as e:
                log_agent_action("User Data", user_id, f"Retrieval failed: {e}")
        
        memory_result = {"data": {"capsules": related_capsules}, "total": len(related_memories)}
        if self.memory_handler:
            try:
                memory_result = self.memory_handler.search_memory(user_id, message)
                log_agent_action("Memory Handler", user_id, f"Comprehensive retrieval complete")
            except Exception as e:
                log_agent_action("Memory Handler", user_id, f"Retrieval failed: {e}")
        
        reply = self._generate_smart_reply(user_id, message, related_memories, user_preferences)
        return {"success": True, "reply": reply}
    
    def _save_user_info_to_memory(self, user_id, message):
        """
        Intelligently identify and save user key information (standard storage pipeline)
        """
        from core.utils.intent_recognizer import recognize_save_intent, recognize_intent
        from core.utils.sensitive_check import detect_sensitive
        
        if recognize_intent(message):
            log_agent_action("Memory Save", user_id, "Query type question detected, skipping save")
            return
        
        save_intents = recognize_save_intent(message)
        
        if not save_intents:
            return
        
        for intent in save_intents:
            info_type = intent["info_type"]
            info_value = intent["info_value"]
            info_category = intent["info_category"]
            
            is_sensitive = detect_sensitive(info_value)
            
            if self.temp_database:
                try:
                    self.temp_database.insert({
                        "user_id": user_id,
                        "info_type": info_type,
                        "info_value": info_value,
                        "info_category": info_category,
                        "is_sensitive": is_sensitive,
                        "timestamp": time.time()
                    })
                    log_agent_action("Temp Database", user_id, f"Saved to temp database: {info_type}")
                except Exception as e:
                    log_agent_action("Temp Database", user_id, f"Save failed: {e}")
            
            if is_sensitive and self.encrypted_memory:
                try:
                    self.encrypted_memory.save_sensitive_info(
                        user_id=user_id,
                        info_type=info_type,
                        info_value=info_value
                    )
                    log_agent_action("Encrypted Memory", user_id, f"Saved sensitive info: {info_type}")
                except Exception as e:
                    log_agent_action("Encrypted Memory", user_id, f"Save failed: {e}")
            
            if self.short_term_memory:
                try:
                    self.short_term_memory.insert_log({
                        "timestamp": time.time(),
                        "environment": "production",
                        "action": f"save_{info_category}",
                        "result": f"{info_type}: {info_value}",
                        "success_rate": 1.0,
                        "trace_id": str(uuid.uuid4())
                    })
                    log_agent_action("Short-term Memory", user_id, f"Saved: {info_type}")
                except Exception as e:
                    log_agent_action("Short-term Memory", user_id, f"Save failed: {e}")
            
            if self.long_term_memory:
                try:
                    self.long_term_memory.save_memory(
                        user_id=user_id,
                        content=f"{info_type}: {info_value}",
                        memory_type=info_category,
                        metadata={"is_sensitive": is_sensitive}
                    )
                    log_agent_action("Long-term Memory", user_id, f"Saved: {info_type}")
                except Exception as e:
                    log_agent_action("Long-term Memory", user_id, f"Save failed: {e}")
            
            if self.user_data_manager:
                try:
                    self.user_data_manager.set_user_preference(
                        user_id=user_id,
                        key=info_type,
                        value=info_value
                    )
                    log_agent_action("User Data", user_id, f"Saved preference: {info_type}")
                except Exception as e:
                    log_agent_action("User Data", user_id, f"Save failed: {e}")
            
            if self.capsule_manager:
                try:
                    from core.capsules.agent_capsule import ExperienceCapsule
                    capsule = ExperienceCapsule(
                        agent_id=user_id,
                        experience_type=info_category,
                        content=f"{info_type}: {info_value}",
                        metadata={"is_sensitive": is_sensitive}
                    )
                    self.capsule_manager.add_capsule(capsule)
                    log_agent_action("Capsule Save", user_id, f"Saved experience capsule: {info_type}")
                except Exception as e:
                    log_agent_action("Capsule Save", user_id, f"Save failed: {e}")
            
            if self.capsule_manager:
                try:
                    from core.capsules.error_capsule import WorkLogCapsule
                    work_log = WorkLogCapsule(
                        agent_id=user_id,
                        action=f"Save user info - {info_type}",
                        result=f"Successfully saved {info_value}"
                    )
                    log_agent_action("Work Log Capsule", user_id, f"Recorded save operation")
                except Exception as e:
                    log_agent_action("Work Log Capsule", user_id, f"Record failed: {e}")
    
    def _generate_smart_reply(self, user_id, message, related_memories, user_preferences):
        """Directly call LLM to generate response"""
        return self._call_llm(user_id, message)
    
    def _start_worker_threads(self):
        """Start worker thread pool (process task queue)"""
        for i in range(self.max_workers):
            worker = threading.Thread(target=self._worker_loop, args=(i,), daemon=True)
            worker.start()
            self.worker_threads.append(worker)
            log_agent_action("Start Worker Thread", "system", f"Thread {i} started")

    def _worker_loop(self, worker_id):
        """Worker thread loop: process priority tasks"""
        while self.is_running:
            try:
                priority, task = self.task_queue.get(timeout=1)
                task_id = task.get("task_id")
                user_id = task.get("user_id")
                
                log_agent_action("Execute Task", user_id, f"Thread {worker_id} | Priority: {priority} | Task ID: {task_id}")
                result = self._execute_task(task)
                self.task_queue.task_done()
                log_agent_action("Complete Task", user_id, f"Thread {worker_id} | Task ID: {task_id} | Success: {result.get('success', False)}")
            except queue.Empty:
                time.sleep(0.1)
            except Exception as e:
                log_agent_action("Worker Thread Exception", "system", f"Thread {worker_id} | Error: {str(e)}")

    def submit_task(self, user_id, task_type, params, priority="normal"):
        task_id = f"task_{datetime.now().strftime('%Y%m%d%H%M%S')}_{user_id}_{int(time.time()*1000)%1000}"
        priority_num = self.task_priority.get(priority, 2)
        task = {
            "task_id": task_id,
            "user_id": user_id,
            "task_type": task_type,
            "params": params,
            "submit_time": time.time(),
            "priority": priority
        }
        self.task_queue.put((priority_num, task))
        log_agent_action("Submit Task", user_id, f"Task ID: {task_id} | Priority: {priority} | Queue length: {self.task_queue.qsize()}")
        return {"success": True, "task_id": task_id, "priority": priority, "queue_size": self.task_queue.qsize()}

    def _execute_task(self, task):
        task_type = task.get("task_type")
        user_id = task.get("user_id")
        params = task.get("params")
        retry_count = task.get("retry_count", 0)
        
        try:
            if task_type == "message":
                result = self._handle_message_task(user_id, params.get("message"))
            elif task_type == "tool":
                result = self._invoke_tool_task(user_id, params.get("tool_name"), params.get("tool_params"))
            elif task_type == "memory":
                result = self._memory_operation_task(user_id, params.get("op_type"), params.get("memory_params"))
            elif task_type == "capsule":
                result = self._capsule_operation_task(user_id, params.get("op_type"), params.get("capsule_params"))
            else:
                result = {"success": False, "error": f"Unknown task type: {task_type}"}
            return result
        except Exception as e:
            error_msg = str(e)
            if retry_count < self.max_retry:
                log_agent_action("Task Failed Retry", user_id, f"Task ID: {task['task_id']} | Retry count: {retry_count+1}/{self.max_retry} | Error: {error_msg}")
                task["retry_count"] = retry_count + 1
                self.task_queue.put((self.task_priority.get(task["priority"], 2), task))
                return {"success": False, "error": f"Task failed, retrying ({retry_count+1}/{self.max_retry}): {error_msg}"}
            else:
                log_agent_action("Task Final Failure", user_id, f"Task ID: {task['task_id']} | Retry count exhausted | Error: {error_msg}")
                return {"success": False, "error": f"Task failed (retried {self.max_retry} times): {error_msg}"}

    def _invoke_tool_task(self, user_id, tool_name, tool_params):
        result = {"success": False, "error": "Tool call timeout"}
        event = threading.Event()
        
        def invoke():
            nonlocal result
            try:
                res = self.tool_invoker.invoke_tool(user_id, tool_name, **tool_params)
                result = res
            except Exception as e:
                result = {"success": False, "error": str(e)}
            finally:
                event.set()
        
        invoke_thread = threading.Thread(target=invoke, daemon=True)
        invoke_thread.start()
        event.wait(timeout=self.tool_timeout)
        if not event.is_set():
            log_agent_action("Tool Call Timeout", user_id, f"Tool: {tool_name} | Timeout: {self.tool_timeout}s")
            result = {"success": False, "error": f"Tool call timeout (>{self.tool_timeout}s)"}
        return result

    def _memory_operation_task(self, user_id, op_type, memory_params):
        if op_type == "save_short":
            return self.memory_handler.save_short_term_memory(user_id, **memory_params)
        elif op_type == "save_long":
            return self.memory_handler.save_long_term_memory(user_id, **memory_params)
        elif op_type == "search":
            return self.memory_handler.search_memory(user_id, **memory_params)
        elif op_type == "export":
            return self.memory_handler.export_memory(user_id, **memory_params)
        else:
            return {"success": False, "error": f"Unknown memory operation: {op_type}"}

    def _capsule_operation_task(self, user_id, op_type, capsule_params):
        if not self.memory_handler.capsule_manager:
            return {"success": False, "error": "Capsule module not loaded"}
        if op_type == "search":
            return self.memory_handler.capsule_manager.search_capsules(user_id=user_id, **capsule_params)
        elif op_type == "add":
            return self.memory_handler.capsule_manager.add_capsule(user_id=user_id, **capsule_params)
        elif op_type == "update":
            return self.memory_handler.capsule_manager.update_capsule(**capsule_params)
        else:
            return {"success": False, "error": f"Unknown capsule operation: {op_type}"}

    def assemble_and_review_work(self):
        if not hasattr(self, 'supervisor_queue'):
            return
        while not self.supervisor_queue.empty():
            try:
                report = self.supervisor_queue.get()
                agent_id = report.get("agent_id", "unknown")
                task_id = report.get("task_id", "unknown")
                result = report.get("result", "")
                status = report.get("status", "unknown")
                print(f"[Main Agent] Assembling task {task_id} (Sub-agent: {agent_id})")
                if "sensitive" in str(result).lower() or "password" in str(result).lower():
                    print(f"[Main Agent] Review failed: Task {task_id} contains sensitive information")
                    continue
                if status == "done" and ("success" in str(result).lower() or "complete" in str(result).lower()):
                    if self.long_term_memory and hasattr(self.long_term_memory, 'save_memory'):
                        self.long_term_memory.save_memory(
                            user_id=self.user_id,
                            content=f"Task {task_id}: {result}",
                            memory_type="task_result"
                        )
                        print(f"[Main Agent] Task {task_id} archived to long-term memory")
            except Exception as e:
                print(f"[Main Agent] Assembly review failed: {e}")

    def handle_message(self, user_id, message, priority="normal"):
        result = self._handle_message_task(user_id, message)
        return result.get("reply", "I received your message!")
        
    def process_message(self, message, user_id="default"):
        """Unified message processing entry point"""
        print(f"DEBUG: process_message called with {message}")
        return self.handle_message(user_id, message)    

    def invoke_tool(self, user_id, tool_name, tool_params, priority="normal"):
        return self.submit_task(
            user_id=user_id,
            task_type="tool",
            params={"tool_name": tool_name, "tool_params": tool_params},
            priority=priority
        )

    def _init_feishu_service(self):
        try:
            from interfaces.feishu import init_feishu, set_agent, start_feishu_service
            feishu_config = {
                'APP_ID': os.getenv('FEISHU_APP_ID'),
                'APP_SECRET': os.getenv('FEISHU_APP_SECRET'),
                'VERIFICATION_TOKEN': os.getenv('FEISHU_VERIFICATION_TOKEN'),
                'ENCRYPT_KEY': os.getenv('FEISHU_ENCRYPT_KEY')
            }
            required_configs = ['APP_ID', 'APP_SECRET']
            missing_required = [key for key in required_configs if not feishu_config.get(key) or feishu_config.get(key) == 'xxx']
            if missing_required:
                print(f"[Error] Feishu required config missing: {missing_required}, service cannot start")
                return
            optional_configs = ['VERIFICATION_TOKEN', 'ENCRYPT_KEY']
            missing_optional = [key for key in optional_configs if not feishu_config.get(key) or feishu_config.get(key) == 'xxx']
            if missing_optional:
                print(f"[Warning] Feishu optional config missing: {missing_optional}, some features may be limited")
            init_feishu(feishu_config)
            set_agent(self)
            start_feishu_service()
            print("Feishu service initialized successfully")
        except ImportError as e:
            print(f"Failed to import Feishu module: {e}")
        except Exception as e:
            print(f"Feishu service initialization failed: {e}")
    
    def get_perception_data(self):
        try:
            return {
                "mouse": self.input_perception.get_mouse_pos() if self.input_perception else None,
                "keyboard": self.input_perception.get_key_state() if self.input_perception else None,
                "screen": self.screen_mirror.get_frame() if self.screen_mirror else None,
                "process": self.process_monitor.get_running_processes() if self.process_monitor else None
            }
        except Exception as e:
            print(f"[Main Agent] Failed to get perception data: {e}")
            return {"mouse": None, "keyboard": None, "screen": None, "process": None}

    def shutdown(self):
        self.is_running = False
        if self.feishu_enabled:
            try:
                from interfaces.feishu import stop_feishu_service
                stop_feishu_service()
                log_agent_action("Stop Feishu Service", "system", "Feishu service closed")
            except Exception as e:
                print(f"Failed to stop Feishu service: {e}")
        for i, worker in enumerate(self.worker_threads):
            worker.join(timeout=5)
            log_agent_action("Stop Worker Thread", "system", f"Thread {i} stopped")
        self.patrol_system.stop_patrol()
        self.task_queue.join()
        if self.memory_handler:
            try:
                self.memory_handler.close()
                log_agent_action("Close Memory Handler", "system", "Memory handler resources released")
            except Exception as e:
                log_agent_action("Close Memory Handler", "system", f"Close failed: {e}")
        if self.user_data_manager:
            try:
                self.user_data_manager.close()
                log_agent_action("Close User Data Manager", "system", "User data manager resources released")
            except Exception as e:
                log_agent_action("Close User Data Manager", "system", f"Close failed: {e}")
        log_agent_action("Close Main Agent", "system", "All tasks completed, resources cleaned")

    def run(self):
        """Start interaction (command line test)"""
        log_agent_action("Start Agent Interaction", "system", "Entering dialog mode, type 'exit' to quit | Supported priorities: critical/high/normal/low (example: high|help me check weather)")
        while True:
            try:
                user_input = input("You: ")
                if user_input.lower() == "exit":
                    break
                if "|" in user_input:
                    priority, message = user_input.split("|", 1)
                    priority = priority.strip()
                    message = message.strip()
                else:
                    priority = "normal"
                    message = user_input
                result = self.submit_task("default_user", "message", {"message": message}, priority=priority)
                print(f"Agent: Task submitted (ID: {result['task_id']} | Priority: {priority} | Queue length: {result['queue_size']})")
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Agent: Processing exception: {str(e)}")
        self.shutdown()


def log_agent_action(action, user_id, details, success_rate=1.0):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{action}] User: {user_id} | {details} | Success rate: {success_rate}")

class ContextManager:
    def __init__(self, max_history_len=50):
        self.max_history_len = max_history_len
        self.context = {}
    def get_state(self, user_id):
        return self.context.get(user_id, {}).get("state", {"current_task": "normal"})
    def add_message(self, user_id, role, content):
        if user_id not in self.context:
            self.context[user_id] = {"messages": [], "state": {"current_task": "normal"}}
        self.context[user_id]["messages"].append({"role": role, "content": content, "time": time.time()})
        if len(self.context[user_id]["messages"]) > self.max_history_len:
            self.context[user_id]["messages"] = self.context[user_id]["messages"][-self.max_history_len:]

class MemoryHandler:
    def __init__(self, data_dir=None):
        self.short_memory = {}
        self.long_memory = {}
        self.capsule_manager = self._init_capsule_manager()
    def _init_capsule_manager(self):
        class CapsuleManager:
            def search_capsules(self, user_id, **kwargs):
                return {"success": True, "data": [], "total": 0}
            def add_capsule(self, user_id, **kwargs):
                return {"success": True, "capsule_id": f"capsule_{uuid.uuid4().hex[:8]}"}
            def update_capsule(self, **kwargs):
                return {"success": True}
        return CapsuleManager()
    def save_short_term_memory(self, user_id, **kwargs):
        content = kwargs.get("content", "")
        if user_id not in self.short_memory:
            self.short_memory[user_id] = []
        self.short_memory[user_id].append({"content": content, "time": time.time()})
        return {"success": True, "count": len(self.short_memory[user_id])}
    def save_long_term_memory(self, user_id, **kwargs):
        content = kwargs.get("content", "")
        if user_id not in self.long_memory:
            self.long_memory[user_id] = []
        self.long_memory[user_id].append({"content": content, "time": time.time()})
        return {"success": True, "count": len(self.long_memory[user_id])}
    def search_memory(self, user_id, query, **kwargs):
        return {"success": True, "data": {"capsules": []}, "total": 0}
    def export_memory(self, user_id, **kwargs):
        return {"success": True, "short_count": len(self.short_memory.get(user_id, [])), "long_count": len(self.long_memory.get(user_id, []))}

class SubAgentManager:
    def __init__(self, max_sub_agents=30):
        self.max_sub_agents = max_sub_agents
        self.sub_agent_pool = {}
    def create_sub_agent(self, user_id, permissions=None):
        import queue
        import uuid
        class SubAgent:
            def __init__(self, supervisor_queue, tool_manager, long_term_memory, user_id, permissions=None):
                self.agent_id = f"sub_agent_{uuid.uuid4().hex[:8]}"
                self.supervisor_queue = supervisor_queue
                self.tool_manager = tool_manager
                self.ltm = long_term_memory
                self.user_id = user_id
                self.permissions = permissions or {}
                self.log = []
                self.status = "idle"
                self.result = None
                self.error = None
                self.created_at = time.time()
                self.finished_at = None
                print(f"Sub-agent {self.agent_id} created successfully (User: {user_id})")
            def execute(self, task):
                self.status = "running"
                task_desc = task.get("description", "")
                try:
                    result = f"[Simulated] Sub-task '{task_desc}' executed successfully (Sub-agent: {self.agent_id})"
                    self.result = result
                    self.status = "done"
                    self.finished_at = time.time()
                    print(f"Sub-agent {self.agent_id} executed task successfully: {task_desc}")
                except Exception as e:
                    self.error = str(e)
                    self.status = "failed"
                    self.finished_at = time.time()
                    print(f"Sub-agent {self.agent_id} task execution failed: {str(e)}")
                finally:
                    self.destroy()
            def destroy(self):
                self.status = "killed"
                print(f"Sub-agent {self.agent_id} destroyed in real-time")
        mock_queue = queue.Queue()
        class MockToolManager:
            def call_tool(self, *args, **kwargs):
                return f"Simulated tool call result: {args} {kwargs}"
        sub_agent = SubAgent(
            supervisor_queue=mock_queue,
            tool_manager=MockToolManager(),
            long_term_memory="mock_ltm",
            user_id=user_id,
            permissions=permissions or {"allow_llm": True, "allow_network": True}
        )
        self.sub_agent_pool[sub_agent.agent_id] = {
            "user_id": user_id,
            "status": sub_agent.status,
            "instance": sub_agent
        }
        return sub_agent

class ReplyGenerator:
    def __init__(self, style="Butler", max_length=500):
        self.style = style
        self.max_length = max_length
    def generate_reply(self, user_id, content):
        return f"[{self.style} style] {content}"[:self.max_length]

class PatrolSystem:
    def __init__(self, patrol_interval=60):
        self.patrol_interval = patrol_interval
        self.is_running = False
        self.patrol_thread = None
        self.sub_agent_manager = None
        self.memory_handler = None
        self.tool_invoker = None
    def set_sub_agent_manager(self, manager):
        self.sub_agent_manager = manager
    def set_memory_handler(self, handler):
        self.memory_handler = handler
    def set_tool_invoker(self, invoker):
        self.tool_invoker = invoker
    def _patrol_loop(self):
        while self.is_running:
            log_agent_action("Patrol System", "system", f"Checking sub-agent count: {len(self.sub_agent_manager.sub_agent_pool) if self.sub_agent_manager else 0}")
            time.sleep(self.patrol_interval)
    def start_patrol(self):
        self.is_running = True
        self.patrol_thread = threading.Thread(target=self._patrol_loop, daemon=True)
        self.patrol_thread.start()
        log_agent_action("Patrol System", "system", "Patrol started")
    def stop_patrol(self):
        self.is_running = False
        if self.patrol_thread:
            self.patrol_thread.join(timeout=5)
        log_agent_action("Patrol System", "system", "Patrol stopped")

class ToolInvoker:
    def __init__(self, data_dir=None):
        self.data_dir = data_dir
    def invoke_tool(self, user_id, tool_name, **kwargs):
        return {"success": True, "result": f"Tool {tool_name} invoked"}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Agent Core Main Entry")
    parser.add_argument("--feishu", action="store_true", help="Enable Feishu integration")
    parser.add_argument("--interactive", action="store_true", help="Start interactive mode")
    args = parser.parse_args()
    
    agent = AgentCore(feishu_enabled=args.feishu)
    
    if args.interactive:
        agent.run()
    else:
        print("Agent Core initialized. Use --interactive for interactive mode or --feishu for Feishu integration.")


if __name__ == "__main__":
    main()
