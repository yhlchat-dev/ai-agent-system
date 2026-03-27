#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Agent 1.0 Final Production Version - Integrated Professional SubAgentManager
Includes dynamic creation, idle cleanup, quantity limit, lifecycle management and other core features
"""
import time
import queue
import uuid
import threading
from typing import Dict, Optional, Any

class ExampleAgent:
    """Example Sub-Agent Class (can be extended to lobster sub-agent etc. in actual business)"""
    def __init__(self, params: dict):
        self.params = params
        self.status = "idle"
        self.task_result = None
    
    def execute_task(self, task_desc: str) -> dict:
        """Execute task (example logic)"""
        self.status = "running"
        print(f"[ExampleAgent] Executing task: {task_desc} | Params: {self.params}")
        try:
            time.sleep(0.2)
            self.task_result = f"Task completed: {task_desc}"
            self.status = "done"
            return {"success": True, "result": self.task_result}
        except Exception as e:
            self.status = "failed"
            return {"success": False, "error": str(e)}
    
    def get_status(self) -> str:
        """Get Agent status"""
        return self.status

class SubAgentManager:
    def __init__(self, max_agents: int = 30):
        self.max_agents = max_agents
        self.agents = {}
        self.lock = threading.RLock()

    def create_agent(self, agent_type: str, params: dict) -> Optional[str]:
        """Create sub-agent instance, return agent_id, return None if max count exceeded"""
        with self.lock:
            if len(self.agents) >= self.max_agents:
                self._cleanup_idle_agents()
                if len(self.agents) >= self.max_agents:
                    print("[SubAgentManager] Max sub-agent count reached, cannot create new instance")
                    return None

            try:
                if agent_type == 'example':
                    agent_instance = ExampleAgent(params)
                else:
                    raise ValueError(f"Unknown sub-agent type: {agent_type}")
            except Exception as e:
                print(f"[SubAgentManager] Cannot create sub-agent type {agent_type}: {str(e)}")
                return None

            agent_id = f"{agent_type}_{int(time.time())}_{len(self.agents)}"
            self.agents[agent_id] = (agent_instance, time.time(), time.time())
            print(f"[SubAgentManager] Successfully created sub-agent: {agent_id}")
            return agent_id

    def get_agent(self, agent_id: str) -> Optional[ExampleAgent]:
        """Get sub-agent instance, update last active time"""
        with self.lock:
            if agent_id in self.agents:
                instance, created, _ = self.agents[agent_id]
                self.agents[agent_id] = (instance, created, time.time())
                return instance
            return None

    def destroy_agent(self, agent_id: str) -> bool:
        """Destroy specified sub-agent"""
        with self.lock:
            if agent_id in self.agents:
                instance, _, _ = self.agents[agent_id]
                print(f"[SubAgentManager] Destroying sub-agent: {agent_id} | Last status: {instance.get_status()}")
                del self.agents[agent_id]
                return True
            return False

    def _cleanup_idle_agents(self, idle_timeout: int = 300):
        """Cleanup sub-agents idle for more than specified seconds (default 5 minutes)"""
        now = time.time()
        with self.lock:
            to_delete = [
                aid for aid, (_, created, last) in self.agents.items() 
                if now - last > idle_timeout
            ]
            for aid in to_delete:
                print(f"[SubAgentManager] Cleaning up idle sub-agent: {aid} (idle timeout {idle_timeout}s)")
                del self.agents[aid]

    def destroy_all_agents(self):
        """Destroy all sub-agents"""
        with self.lock:
            agent_ids = list(self.agents.keys())
            for aid in agent_ids:
                self.destroy_agent(aid)
            print(f"[SubAgentManager] Batch destruction complete, destroyed {len(agent_ids)} sub-agents")
            return len(agent_ids)

    def get_stats(self) -> dict:
        """Get sub-agent statistics"""
        with self.lock:
            return {
                "total": len(self.agents),
                "max": self.max_agents,
                "agents": list(self.agents.keys())
            }

def log_agent_action(action: str, user_id: str, detail: str):
    """Print Agent operation log (with timestamp)"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    print(f"[{timestamp}] [{user_id}] {action}: {detail}")

class MemoryManager:
    """Memory Manager: Handle short-term/long-term memory"""
    def __init__(self):
        self.short_term_memory = {}
        self.long_term_memory = {}
    
    def add_short_term_memory(self, user_id: str, key: str, value: str):
        """Add short-term memory"""
        if user_id not in self.short_term_memory:
            self.short_term_memory[user_id] = {}
        self.short_term_memory[user_id][key] = value
    
    def get_memory(self, user_id: str, key: str, long_term: bool = False) -> Optional[str]:
        """Get memory"""
        if long_term:
            return self.long_term_memory.get(user_id, {}).get(key, None)
        return self.short_term_memory.get(user_id, {}).get(key, None)

class ToolInvoker:
    """Tool Invoker: Simulate calling external tools"""
    def __init__(self, data_dir=None):
        self.data_dir = data_dir
        self.supported_tools = ["weatherapi", "summarize_text", "file_operation"]
    
    def invoke_tool(self, user_id: str, tool_name: str, **kwargs) -> dict:
        """Invoke tool"""
        if tool_name not in self.supported_tools:
            return {"success": False, "error": f"Unsupported tool: {tool_name}"}
        time.sleep(0.5)
        return {"success": True, "tool_name": tool_name, "result": f"Simulated {tool_name} call result: {kwargs}"}

class Task:
    """Task Class: Encapsulate task information"""
    def __init__(self, task_id: str, user_id: str, content: str, priority: int = 2):
        self.task_id = task_id
        self.user_id = user_id
        self.content = content
        self.priority = priority
        self.create_time = time.time()
        self.status = "pending"

class TaskScheduler:
    """Task Scheduler: Priority-based multi-threaded scheduling"""
    def __init__(self, thread_count: int = 5):
        self.task_queue = queue.PriorityQueue()
        self.thread_count = thread_count
        self.worker_threads = []
        self.running = False
        self.sub_agent_mgr = SubAgentManager(max_agents=30)
    
    def start(self):
        """Start scheduler"""
        self.running = True
        for i in range(self.thread_count):
            t = threading.Thread(target=self._worker, args=(i,))
            self.worker_threads.append(t)
            t.start()
            log_agent_action("Start worker thread", "system", f"Thread {i} started")
    
    def stop(self):
        """Stop scheduler"""
        self.running = False
        for t in self.worker_threads:
            t.join()
        log_agent_action("Stop scheduler", "system", "All worker threads stopped")
    
    def submit_task(self, task: Task):
        """Submit task (sorted by priority)"""
        self.task_queue.put((task.priority, task))
        log_agent_action("Submit task", task.user_id, 
                        f"Task ID: {task.task_id} | Priority: {task.priority} | Queue length: {self.task_queue.qsize()}")
    
    def _worker(self, thread_id: int):
        """Worker thread: Process tasks"""
        while self.running:
            try:
                if not self.task_queue.empty():
                    priority, task = self.task_queue.get(timeout=1)
                    task.status = "running"
                    log_agent_action("Execute task", task.user_id, 
                                    f"Thread {thread_id} | Priority: {priority} | Task ID: {task.task_id}")
                    
                    result = InstructionProcessor.handle_instruction(
                        task, self.sub_agent_mgr
                    )
                    
                    task.status = "done" if result["success"] else "failed"
                    log_agent_action("Complete task", task.user_id, 
                                    f"Thread {thread_id} | Task ID: {task.task_id} | Success: {result['success']}")
                else:
                    time.sleep(0.1)
            except queue.Empty:
                continue
            except Exception as e:
                log_agent_action("Task execution error", "system", f"Thread {thread_id}: {str(e)}")

class InstructionProcessor:
    """Instruction Processor: Parse and execute user instructions"""
    @classmethod
    def handle_instruction(cls, task: Task, sub_agent_mgr: SubAgentManager) -> dict:
        """Handle instruction main logic"""
        content = task.content.strip()
        user_id = task.user_id
        
        try:
            if "create" in content and "sub-agent" in content:
                import re
                num_match = re.search(r"(\d+)", content)
                num = int(num_match.group(1)) if num_match else 1
                
                success_count = 0
                for i in range(num):
                    agent_id = sub_agent_mgr.create_agent(
                        agent_type="example",
                        params={"user_id": user_id, "task_index": i+1}
                    )
                    if agent_id:
                        success_count += 1
                
                return {
                    "success": True,
                    "message": f"Successfully created {success_count} sub-agents (requested {num})",
                    "count": success_count
                }
            
            elif "destroy" in content and "sub-agent" in content:
                if "all" in content:
                    destroy_count = sub_agent_mgr.destroy_all_agents()
                    return {"success": True, "message": f"Destroyed {destroy_count} sub-agents"}
                else:
                    stats = sub_agent_mgr.get_stats()
                    if stats["total"] > 0:
                        first_agent_id = stats["agents"][0]
                        sub_agent_mgr.destroy_agent(first_agent_id)
                        return {"success": True, "message": f"Destroyed sub-agent: {first_agent_id}"}
                    else:
                        return {"success": False, "message": "No available sub-agents to destroy"}
            
            elif "split" in content and "task" in content:
                tasks = [t.strip() for t in content.split(":")[1].split(",") if t.strip()]
                results = []
                
                for task_desc in tasks:
                    agent_id = sub_agent_mgr.create_agent(
                        agent_type="example",
                        params={"task_desc": task_desc}
                    )
                    if agent_id:
                        agent = sub_agent_mgr.get_agent(agent_id)
                        task_result = agent.execute_task(task_desc)
                        results.append(task_result)
                        sub_agent_mgr.destroy_agent(agent_id)
                
                success_tasks = len([r for r in results if r["success"]])
                return {
                    "success": True,
                    "message": f"Split {len(tasks)} tasks, successfully executed {success_tasks}",
                    "results": results
                }
            
            elif "view" in content and "sub-agent" in content:
                stats = sub_agent_mgr.get_stats()
                return {
                    "success": True,
                    "message": f"Sub-agent stats: Total {stats['total']}/{stats['max']}, ID list: {stats['agents']}"
                }
            
            else:
                return {
                    "success": True,
                    "message": f"Processed instruction: {content}",
                    "stats": sub_agent_mgr.get_stats()
                }
        
        except Exception as e:
            log_agent_action("Instruction processing failed", user_id, f"Error: {str(e)}")
            return {"success": False, "error": str(e)}

class MainAgent:
    """Main Agent: Integrate all modules"""
    def __init__(self):
        self.sub_agent_mgr = SubAgentManager(max_agents=30)
        self.task_scheduler = TaskScheduler(thread_count=5)
        self.memory_mgr = MemoryManager()
        self.tool_invoker = ToolInvoker()
        
        self.patrol_running = True
        self.patrol_thread = threading.Thread(target=self._patrol)
        self.patrol_thread.start()
    
    def start(self):
        """Start main Agent"""
        self.task_scheduler.start()
        log_agent_action("Initialize main Agent", "system", 
                        f"Scheduler started | Worker threads: 5 | Task priority: critical>high>normal>low")
        print("== Agent 1.0 Started Successfully ==")
        print(f"Sub-agent max count: {self.sub_agent_mgr.max_agents}")
        print(f"Patrol module: Running silently in background (reports anomalies proactively)")
        print(f"Memory module: Short-term/long-term memory initialized")
        print(f"Sub-agent management: Supports dynamic creation, idle cleanup (5 min timeout)")
        print("--------------------------")
        log_agent_action("Start Agent interaction", "system", 
                        "Entering conversation mode, type 'exit' to quit | Supports priority: critical/high/normal/low (example: high|help me check weather)")
    
    def stop(self):
        """Stop main Agent"""
        self.patrol_running = False
        self.patrol_thread.join()
        self.task_scheduler.stop()
        self.sub_agent_mgr.destroy_all_agents()
        log_agent_action("Stop main Agent", "system", "All modules stopped, resources cleaned")
    
    def send_message(self, user_id: str, message: str, priority: int = 2):
        """Send message (create task and submit)"""
        task_id = f"task_{time.strftime('%Y%m%d%H%M%S')}_{user_id}_{uuid.uuid4().hex[:3]}"
        task = Task(task_id, user_id, message, priority)
        self.task_scheduler.submit_task(task)
        
        queue_size = self.task_scheduler.task_queue.qsize()
        print(f"Agent: Task submitted (ID: {task_id} | Priority: {priority} | Queue length: {queue_size})")
        return task_id
    
    def _patrol(self):
        """Patrol thread: Check sub-agent status every 60 seconds"""
        while self.patrol_running:
            try:
                self.sub_agent_mgr._cleanup_idle_agents()
                stats = self.sub_agent_mgr.get_stats()
                log_agent_action("Patrol system", "system", f"Check sub-agent count: {stats['total']}/{stats['max']}")
                time.sleep(60)
            except Exception as e:
                log_agent_action("Patrol error", "system", f"Error: {str(e)}")

if __name__ == "__main__":
    agent = MainAgent()
    agent.start()
    
    user_id = "default_user"
    try:
        while True:
            message = input("You: ").strip()
            if not message:
                continue
            if message.lower() == "exit":
                break
            
            priority = 2
            if "|" in message:
                prio_str, content = message.split("|", 1)
                prio_map = {"critical":0, "high":1, "normal":2, "low":3}
                if prio_str in prio_map:
                    priority = prio_map[prio_str]
                    message = content
            
            agent.send_message(user_id, message, priority)
    
    except KeyboardInterrupt:
        print("\n\nUser forced exit")
    finally:
        agent.stop()
        print("== Agent 1.0 Exited ==")
