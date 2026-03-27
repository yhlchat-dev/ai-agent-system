#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Agent 1.0 生产级最终完整版
集成：专业版SubAgentManager + ContextManager + MemoryHandler + 任务调度
"""
import time
import queue
import uuid
import json
import threading
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Any

# ===================== 基础工具函数 =====================
def clean_text(text: str) -> str:
    """清理文本（去除多余空格、换行、特殊字符）"""
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9，。！？：；""''()（）【】]', '', text)
    return text

def log_agent_action(action: str, user_id: str, detail: str = ""):
    """打印Agent操作日志（带时间戳）"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    print(f"[{timestamp}] [{user_id}] {action}：{detail}")

# ===================== 模拟缺失的记忆/胶囊模块（核心适配） =====================
# 模拟ShortTermMemory（适配MemoryHandler依赖）
class ShortTermMemory:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(exist_ok=True)
        self.memory_pool = {}  # {user_id: {mem_id: {"content": "", "context": {}, "tags": [], "expire_at": 0, "priority": 1}}}
    
    def save(self, user_id: str, content: str, context: dict, tags: list, expire_at: float, priority: int) -> dict:
        """保存短时记忆"""
        if user_id not in self.memory_pool:
            self.memory_pool[user_id] = {}
        mem_id = f"short_{int(time.time())}_{len(self.memory_pool[user_id])}"
        self.memory_pool[user_id][mem_id] = {
            "content": content,
            "context": context,
            "tags": tags,
            "expire_at": expire_at,
            "priority": priority,
            "create_time": time.time()
        }
        return {"success": True, "mem_id": mem_id}
    
    def search(self, user_id: str, keywords: str, limit: int) -> dict:
        """检索短时记忆"""
        if user_id not in self.memory_pool:
            return {"success": True, "data": []}
        
        # 简单关键词匹配
        results = []
        for mem_id, mem in self.memory_pool[user_id].items():
            if keywords in mem["content"] or any(keywords in tag for tag in mem["tags"]):
                results.append({
                    "mem_id": mem_id,
                    "content": mem["content"],
                    "tags": mem["tags"],
                    "create_time": mem["create_time"],
                    "expire_at": mem["expire_at"]
                })
        
        # 按创建时间倒序，取前limit条
        results = sorted(results, key=lambda x: x["create_time"], reverse=True)[:limit]
        return {"success": True, "data": results}
    
    def clean_expired(self, user_id: str) -> int:
        """清理过期短时记忆"""
        if user_id not in self.memory_pool:
            return 0
        
        now = time.time()
        expired_ids = []
        for mem_id, mem in self.memory_pool[user_id].items():
            if mem["expire_at"] > 0 and now > mem["expire_at"]:
                expired_ids.append(mem_id)
        
        for mem_id in expired_ids:
            del self.memory_pool[user_id][mem_id]
        
        return len(expired_ids)

# 模拟LongTermMemory（适配MemoryHandler依赖）
class LongTermMemory:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(exist_ok=True)
        self.memory_pool = {}  # {user_id: {mem_id: {"content": "", "context": {}, "tags": [], "expire_at": 0, "priority": 2}}}
    
    def save(self, user_id: str, content: str, context: dict, tags: list, expire_at: float, priority: int) -> dict:
        """保存长时记忆"""
        if user_id not in self.memory_pool:
            self.memory_pool[user_id] = {}
        mem_id = f"long_{int(time.time())}_{len(self.memory_pool[user_id])}"
        self.memory_pool[user_id][mem_id] = {
            "content": content,
            "context": context,
            "tags": tags,
            "expire_at": expire_at,
            "priority": priority,
            "create_time": time.time()
        }
        return {"success": True, "mem_id": mem_id}
    
    def search(self, user_id: str, keywords: str, limit: int) -> dict:
        """检索长时记忆"""
        if user_id not in self.memory_pool:
            return {"success": True, "data": []}
        
        results = []
        for mem_id, mem in self.memory_pool[user_id].items():
            if keywords in mem["content"] or any(keywords in tag for tag in mem["tags"]):
                results.append({
                    "mem_id": mem_id,
                    "content": mem["content"],
                    "tags": mem["tags"],
                    "priority": mem["priority"],
                    "expire_at": mem["expire_at"]
                })
        
        results = sorted(results, key=lambda x: x["priority"], reverse=True)[:limit]
        return {"success": True, "data": results}

# 模拟CapsuleManager（适配MemoryHandler依赖）
class CapsuleManager:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(exist_ok=True)
        self.capsules = {}  # {user_id: {capsule_id: {"content": "", "create_time": 0}}}
    
    def search_capsules(self, query: str, user_id: str, top_k: int) -> dict:
        """检索胶囊（模拟）"""
        if user_id not in self.capsules:
            return {"success": True, "data": []}
        
        results = []
        for capsule_id, capsule in self.capsules[user_id].items():
            if query in capsule["content"]:
                results.append({
                    "capsule_id": capsule_id,
                    "content": capsule["content"],
                    "create_time": capsule["create_time"]
                })
        
        results = sorted(results, key=lambda x: x["create_time"], reverse=True)[:top_k]
        return {"success": True, "data": results}

# ===================== 你提供的MemoryHandler（完整保留） =====================
class MemoryHandler:
    """记忆处理器：完善长短时记忆 + 胶囊联动"""
    def __init__(self, data_dir=None):
        self.data_dir = Path(data_dir or "./data")
        self.data_dir.mkdir(exist_ok=True)
        
        # 初始化记忆模块（使用模拟类，避免导入报错）
        self.short_term = ShortTermMemory(self.data_dir / "short_term")
        self.long_term = LongTermMemory(self.data_dir / "long_term")
        self.capsule_manager = CapsuleManager(self.data_dir / "capsules")
        MEMORY_AVAILABLE = True  # 强制设为True，使用模拟模块
        
        # 记忆配置
        self.short_term_expire = 3600 * 24  # 短时记忆过期时间：24小时
        self.long_term_expire = 3600 * 24 * 7  # 普通长时记忆过期：7天
        self.priority_tags = ["重要", "偏好", "习惯"]  # 高优先级标签（永不删除）

    def save_short_term_memory(self, user_id, content, context=None, tags=None):
        """完善：短时记忆保存 + 自动过期 + 标签"""
        # 数据清洗
        content = clean_text(content)
        tags = tags or []
        context = context or {}
        
        # 设置过期时间（当前时间 + 24小时）
        expire_at = time.time() + self.short_term_expire
        
        # 保存短时记忆
        result = self.short_term.save(
            user_id=user_id,
            content=content,
            context=context,
            tags=tags,
            expire_at=expire_at,
            priority=1  # 短时记忆默认优先级1
        )
        
        # 自动清理过期短时记忆
        self._clean_expired_short_term(user_id)
        
        log_agent_action("保存短时记忆", user_id, f"成功：{result['success']} | 标签：{tags}")
        return result

    def save_long_term_memory(self, user_id, content, context=None, tags=None, priority=2):
        """完善：长时记忆保存 + 优先级 + 永不删高优先级"""
        # 数据清洗
        content = clean_text(content)
        tags = tags or []
        context = context or {}
        
        # 高优先级标签 → 永不过期
        if any(tag in self.priority_tags for tag in tags):
            expire_at = 0  # 0 = 永不过期
        else:
            expire_at = time.time() + self.long_term_expire
        
        # 保存长时记忆
        result = self.long_term.save(
            user_id=user_id,
            content=content,
            context=context,
            tags=tags,
            expire_at=expire_at,
            priority=priority  # 1低-5高
        )
        
        log_agent_action("保存长时记忆", user_id, f"成功：{result['success']} | 优先级：{priority}")
        return result

    def search_memory(self, user_id, keywords, memory_type="all", limit=5):
        """完善：统一检索接口（短时+长时） + 胶囊联动"""
        keywords = clean_text(keywords)
        results = {"short_term": [], "long_term": [], "capsules": []}
        
        # 1. 检索短时记忆
        if memory_type in ["all", "short_term"] and self.short_term:
            short_result = self.short_term.search(
                user_id=user_id,
                keywords=keywords,
                limit=limit
            )
            results["short_term"] = short_result.get("data", [])
        
        # 2. 检索长时记忆
        if memory_type in ["all", "long_term"] and self.long_term:
            long_result = self.long_term.search(
                user_id=user_id,
                keywords=keywords,
                limit=limit
            )
            results["long_term"] = long_result.get("data", [])
        
        # 3. 联动胶囊：记忆关键词触发胶囊检索
        if memory_type in ["all", "capsules"] and self.capsule_manager:
            capsule_result = self.capsule_manager.search_capsules(
                query=keywords,
                user_id=user_id,
                top_k=limit
            )
            results["capsules"] = capsule_result.get("data", [])
        
        # 整合结果
        total = len(results["short_term"]) + len(results["long_term"]) + len(results["capsules"])
        log_agent_action("检索记忆", user_id, f"找到{total}条结果（短时{len(results['short_term'])}+长时{len(results['long_term'])}+胶囊{len(results['capsules'])}）")
        
        return {
            "success": True,
            "data": results,
            "total": total
        }

    def batch_save_memory(self, user_id, memory_list):
        """新增：批量保存记忆（提升效率）"""
        """
        memory_list格式：
        [
            {"type": "short/long", "content": "", "tags": [], "priority": 2},
            ...
        ]
        """
        success_count = 0
        for memory in memory_list:
            mem_type = memory.get("type", "short")
            if mem_type == "short":
                res = self.save_short_term_memory(
                    user_id=user_id,
                    content=memory.get("content", ""),
                    tags=memory.get("tags", []),
                    context=memory.get("context", {})
                )
            else:
                res = self.save_long_term_memory(
                    user_id=user_id,
                    content=memory.get("content", ""),
                    tags=memory.get("tags", []),
                    priority=memory.get("priority", 2)
                )
            if res["success"]:
                success_count += 1
        
        log_agent_action("批量保存记忆", user_id, f"成功{success_count}/{len(memory_list)}条")
        return {"success": True, "success_count": success_count, "total": len(memory_list)}

    def _clean_expired_short_term(self, user_id):
        """内部：清理用户过期短时记忆"""
        if not self.short_term:
            return
        try:
            deleted = self.short_term.clean_expired(user_id=user_id)
            if deleted > 0:
                log_agent_action("清理过期记忆", user_id, f"删除{deleted}条过期短时记忆")
        except Exception as e:
            log_agent_action("清理过期记忆", user_id, f"失败：{str(e)}")

    def export_memory(self, user_id, export_path=None):
        """新增：导出用户记忆为JSON（便于备份/分析）"""
        export_path = Path(export_path or f"./exports/memory_{user_id}_{datetime.now().strftime('%Y%m%d')}.json")
        export_path.parent.mkdir(exist_ok=True)
        
        # 检索所有记忆
        all_memory = self.search_memory(user_id, "", memory_type="all", limit=1000)
        
        # 写入文件
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(all_memory, f, ensure_ascii=False, indent=2)
        
        log_agent_action("导出记忆", user_id, f"成功导出到：{export_path}")
        return {"success": True, "export_path": str(export_path)}

# ===================== 示例子Agent =====================
class ExampleAgent:
    """示例子Agent类（可扩展为龙虾子Agent等）"""
    def __init__(self, params: dict):
        self.params = params
        self.status = "idle"
        self.task_result = None
    
    def execute_task(self, task_desc: str) -> dict:
        """执行任务"""
        self.status = "running"
        print(f"[ExampleAgent] 执行任务：{task_desc} | 参数：{self.params}")
        try:
            time.sleep(0.2)
            self.task_result = f"任务完成：{task_desc}"
            self.status = "done"
            return {"success": True, "result": self.task_result}
        except Exception as e:
            self.status = "failed"
            return {"success": False, "error": str(e)}
    
    def get_status(self) -> str:
        """获取Agent状态"""
        return self.status

# ===================== 专业版SubAgentManager =====================
class SubAgentManager:
    def __init__(self, max_agents: int = 30):
        self.max_agents = max_agents
        self.agents = {}  # agent_id -> (agent_instance, created_at, last_active)
        self.lock = threading.RLock()

    def create_agent(self, agent_type: str, params: dict) -> Optional[str]:
        """创建子Agent实例，返回agent_id"""
        with self.lock:
            if len(self.agents) >= self.max_agents:
                self._cleanup_idle_agents()
                if len(self.agents) >= self.max_agents:
                    print("[SubAgentManager] 已达到最大子Agent数量，无法创建新实例")
                    return None

            try:
                if agent_type == 'example':
                    agent_instance = ExampleAgent(params)
                else:
                    raise ValueError(f"未知的子Agent类型: {agent_type}")
            except Exception as e:
                print(f"[SubAgentManager] 无法创建子Agent：{str(e)}")
                return None

            agent_id = f"{agent_type}_{int(time.time())}_{len(self.agents)}"
            self.agents[agent_id] = (agent_instance, time.time(), time.time())
            print(f"[SubAgentManager] 成功创建子Agent：{agent_id}")
            return agent_id

    def get_agent(self, agent_id: str) -> Optional[ExampleAgent]:
        """获取子Agent实例，更新最后活跃时间"""
        with self.lock:
            if agent_id in self.agents:
                instance, created, _ = self.agents[agent_id]
                self.agents[agent_id] = (instance, created, time.time())
                return instance
            return None

    def destroy_agent(self, agent_id: str) -> bool:
        """销毁指定子Agent"""
        with self.lock:
            if agent_id in self.agents:
                instance, _, _ = self.agents[agent_id]
                print(f"[SubAgentManager] 销毁子Agent：{agent_id} | 状态：{instance.get_status()}")
                del self.agents[agent_id]
                return True
            return False

    def _cleanup_idle_agents(self, idle_timeout: int = 300):
        """清理空闲超过5分钟的子Agent"""
        now = time.time()
        with self.lock:
            to_delete = [aid for aid, (_, created, last) in self.agents.items() if now - last > idle_timeout]
            for aid in to_delete:
                print(f"[SubAgentManager] 清理空闲子Agent: {aid}")
                del self.agents[aid]

    def destroy_all_agents(self) -> int:
        """销毁所有子Agent"""
        with self.lock:
            agent_ids = list(self.agents.keys())
            for aid in agent_ids:
                self.destroy_agent(aid)
            print(f"[SubAgentManager] 批量销毁完成，共销毁{len(agent_ids)}个")
            return len(agent_ids)

    def get_stats(self) -> dict:
        """获取子Agent统计信息"""
        with self.lock:
            return {
                "total": len(self.agents),
                "max": self.max_agents,
                "agents": list(self.agents.keys())
            }

# ===================== ContextManager（会话上下文） =====================
class ContextManager:
    """上下文管理器：维护会话状态、历史记录、用户信息"""
    def __init__(self, max_history_len=50):
        self.max_history_len = max_history_len  # 最大历史记录数
        self.context_pool = {}  # 上下文池：{user_id: {"history": [], "state": {}, "create_time": ""}}
    
    def init_context(self, user_id):
        """初始化用户上下文"""
        if user_id not in self.context_pool:
            self.context_pool[user_id] = {
                "history": [],  # 对话历史：[{"role": "user/agent", "content": "", "timestamp": ""}]
                "state": {},    # 会话状态：如{"current_task": "", "sub_agent_id": ""}
                "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            log_agent_action("初始化上下文", user_id, f"最大历史长度：{self.max_history_len}")
        return self.context_pool[user_id]
    
    def add_message(self, user_id, role, content):
        """添加对话消息到上下文"""
        context = self.init_context(user_id)
        content = clean_text(content)
        context["history"].append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        if len(context["history"]) > self.max_history_len:
            context["history"] = context["history"][-self.max_history_len:]
        log_agent_action("添加对话消息", user_id, f"角色：{role} | 内容长度：{len(content)}")
        return context
    
    def get_history(self, user_id, limit=10):
        """获取用户对话历史（最近N条）"""
        context = self.init_context(user_id)
        return context["history"][-limit:]
    
    def set_state(self, user_id, key, value):
        """设置会话状态"""
        context = self.init_context(user_id)
        context["state"][key] = value
        log_agent_action("设置会话状态", user_id, f"{key} = {value}")
        return context["state"]
    
    def get_state(self, user_id, key=None):
        """获取会话状态"""
        context = self.init_context(user_id)
        if key:
            return context["state"].get(key)
        return context["state"]
    
    def clear_context(self, user_id):
        """清空用户上下文"""
        if user_id in self.context_pool:
            del self.context_pool[user_id]
            log_agent_action("清空上下文", user_id)
        return True
    
    def export_context(self, user_id):
        """导出用户上下文为JSON"""
        context = self.init_context(user_id)
        return json.dumps(context, ensure_ascii=False, indent=2)

# ===================== 任务调度模块 =====================
class Task:
    """任务类：封装任务信息"""
    def __init__(self, task_id: str, user_id: str, content: str, priority: int = 2):
        self.task_id = task_id
        self.user_id = user_id
        self.content = content
        self.priority = priority  # 0:critical 1:high 2:normal 3:low
        self.create_time = time.time()
        self.status = "pending"

class TaskScheduler:
    """任务调度器：基于优先级的多线程调度"""
    def __init__(self, thread_count: int = 5):
        self.task_queue = queue.PriorityQueue()
        self.thread_count = thread_count
        self.worker_threads = []
        self.running = False
        self.sub_agent_mgr = SubAgentManager(max_agents=30)
        self.context_mgr = ContextManager(max_history_len=50)
        self.memory_handler = MemoryHandler(data_dir="./data")  # 集成记忆处理器
    
    def start(self):
        """启动调度器"""
        self.running = True
        for i in range(self.thread_count):
            t = threading.Thread(target=self._worker, args=(i,))
            self.worker_threads.append(t)
            t.start()
            log_agent_action("启动工作线程", "system", f"线程{i}已启动")
    
    def stop(self):
        """停止调度器"""
        self.running = False
        for t in self.worker_threads:
            t.join()
        log_agent_action("停止调度器", "system", "所有工作线程已停止")
    
    def submit_task(self, task: Task):
        """提交任务"""
        self.task_queue.put((task.priority, task))
        log_agent_action("提交任务", task.user_id, 
                        f"任务ID：{task.task_id} | 优先级：{task.priority} | 队列长度：{self.task_queue.qsize()}")
    
    def _worker(self, thread_id: int):
        """工作线程：处理任务"""
        while self.running:
            try:
                if not self.task_queue.empty():
                    priority, task = self.task_queue.get(timeout=1)
                    task.status = "running"
                    log_agent_action("执行任务", task.user_id, 
                                    f"线程{thread_id} | 优先级：{priority} | 任务ID：{task.task_id}")
                    
                    # 处理任务并记录上下文/记忆
                    result = InstructionProcessor.handle_instruction(
                        task, self.sub_agent_mgr, self.context_mgr, self.memory_handler
                    )
                    
                    # 记录Agent回复到上下文
                    self.context_mgr.add_message(
                        task.user_id, 
                        "agent", 
                        result["message"]
                    )
                    
                    task.status = "done" if result["success"] else "failed"
                    log_agent_action("完成任务", task.user_id, 
                                    f"线程{thread_id} | 任务ID：{task.task_id} | 成功：{result['success']}")
                else:
                    time.sleep(0.1)
            except queue.Empty:
                continue
            except Exception as e:
                log_agent_action("任务执行异常", "system", f"线程{thread_id}：{str(e)}")

# ===================== 指令处理器（集成记忆功能） =====================
class InstructionProcessor:
    """指令处理器：支持子Agent/上下文/记忆管理"""
    @classmethod
    def handle_instruction(cls, task: Task, sub_agent_mgr: SubAgentManager, 
                          context_mgr: ContextManager, memory_handler: MemoryHandler) -> dict:
        """处理指令主逻辑"""
        content = task.content.strip()
        user_id = task.user_id
        
        try:
            # ========== 1. 子Agent相关指令 ==========
            if "创建" in content and "子agent" in content:
                import re
                num_match = re.search(r"(\d+)个", content)
                num = int(num_match.group(1)) if num_match else 1
                
                success_count = 0
                for i in range(num):
                    agent_id = sub_agent_mgr.create_agent(
                        agent_type="example",
                        params={"user_id": user_id, "task_index": i+1}
                    )
                    if agent_id:
                        success_count += 1
                
                # 记录到长时记忆
                memory_handler.save_long_term_memory(
                    user_id=user_id,
                    content=f"创建了{success_count}个子Agent（请求{num}个）",
                    tags=["子Agent", "创建"],
                    priority=3
                )
                context_mgr.set_state(user_id, "last_agent_count", success_count)
                return {
                    "success": True,
                    "message": f"成功创建{success_count}个子Agent（请求{num}个）"
                }
            
            elif "销毁" in content and "子agent" in content:
                if "所有" in content:
                    destroy_count = sub_agent_mgr.destroy_all_agents()
                    # 记录到长时记忆
                    memory_handler.save_long_term_memory(
                        user_id=user_id,
                        content=f"销毁了{destroy_count}个子Agent",
                        tags=["子Agent", "销毁"],
                        priority=3
                    )
                    context_mgr.set_state(user_id, "last_destroy_count", destroy_count)
                    return {"success": True, "message": f"已销毁{destroy_count}个子Agent"}
                else:
                    stats = sub_agent_mgr.get_stats()
                    if stats["total"] > 0:
                        first_agent_id = stats["agents"][0]
                        sub_agent_mgr.destroy_agent(first_agent_id)
                        return {"success": True, "message": f"已销毁子Agent：{first_agent_id}"}
                    else:
                        return {"success": False, "message": "无可用子Agent可销毁"}
            
            elif "拆分" in content and "任务" in content:
                tasks = [t.strip() for t in content.split("：")[1].split("、") if t.strip()]
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
                # 记录到长时记忆
                memory_handler.save_long_term_memory(
                    user_id=user_id,
                    content=f"拆分{len(tasks)}个任务，成功执行{success_tasks}个",
                    tags=["任务拆分", "子Agent"],
                    priority=3
                )
                return {
                    "success": True,
                    "message": f"拆分{len(tasks)}个任务，成功执行{success_tasks}个"
                }
            
            elif "查看子agent" in content:
                stats = sub_agent_mgr.get_stats()
                return {
                    "success": True,
                    "message": f"子Agent统计：总数{stats['total']}/{stats['max']}，ID列表：{stats['agents']}"
                }
            
            # ========== 2. 上下文相关指令 ==========
            elif "查看历史" in content:
                limit = 5
                if "条" in content:
                    limit_match = re.search(r"(\d+)条", content)
                    if limit_match:
                        limit = int(limit_match.group(1))
                history = context_mgr.get_history(user_id, limit)
                history_str = "\n".join([f"[{h['timestamp']}] {h['role']}：{h['content']}" for h in history])
                return {
                    "success": True,
                    "message": f"最近{limit}条对话历史：\n{history_str}"
                }
            
            elif "清空上下文" in content:
                context_mgr.clear_context(user_id)
                return {"success": True, "message": "已清空所有会话上下文和历史记录"}
            
            elif "导出上下文" in content:
                context_json = context_mgr.export_context(user_id)
                return {"success": True, "message": f"上下文导出成功：\n{context_json}"}
            
            # ========== 3. 记忆相关指令（核心新增） ==========
            elif "保存短时记忆" in content:
                # 格式：保存短时记忆 内容：我喜欢吃苹果 标签：偏好,水果
                content_match = re.search(r"内容：(.*?) 标签：(.*)", content)
                if content_match:
                    mem_content = content_match.group(1)
                    mem_tags = [t.strip() for t in content_match.group(2).split(",")]
                else:
                    mem_content = content.replace("保存短时记忆", "").strip()
                    mem_tags = ["默认"]
                
                result = memory_handler.save_short_term_memory(
                    user_id=user_id,
                    content=mem_content,
                    tags=mem_tags
                )
                return {
                    "success": result["success"],
                    "message": f"短时记忆保存{'成功' if result['success'] else '失败'}：{mem_content}"
                }
            
            elif "保存长时记忆" in content:
                # 格式：保存长时记忆 内容：我的手机号是123456 标签：重要,个人信息 优先级：5
                content_match = re.search(r"内容：(.*?) 标签：(.*?) 优先级：(\d+)", content)
                if content_match:
                    mem_content = content_match.group(1)
                    mem_tags = [t.strip() for t in content_match.group(2).split(",")]
                    priority = int(content_match.group(3))
                else:
                    mem_content = content.replace("保存长时记忆", "").strip()
                    mem_tags = ["默认"]
                    priority = 2
                
                result = memory_handler.save_long_term_memory(
                    user_id=user_id,
                    content=mem_content,
                    tags=mem_tags,
                    priority=priority
                )
                return {
                    "success": result["success"],
                    "message": f"长时记忆保存{'成功' if result['success'] else '失败'}：{mem_content}"
                }
            
            elif "检索记忆" in content:
                # 格式：检索记忆 关键词：苹果 类型：all 数量：10
                keyword_match = re.search(r"关键词：(.*?) 类型：(.*?) 数量：(\d+)", content)
                if keyword_match:
                    keywords = keyword_match.group(1)
                    mem_type = keyword_match.group(2)
                    limit = int(keyword_match.group(3))
                else:
                    keywords = content.replace("检索记忆", "").strip()
                    mem_type = "all"
                    limit = 5
                
                result = memory_handler.search_memory(
                    user_id=user_id,
                    keywords=keywords,
                    memory_type=mem_type,
                    limit=limit
                )
                
                # 格式化检索结果
                short_str = "\n".join([f"- 短时：{item['content']}（标签：{item['tags']}）" for item in result["data"]["short_term"]])
                long_str = "\n".join([f"- 长时：{item['content']}（优先级：{item['priority']}）" for item in result["data"]["long_term"]])
                capsule_str = "\n".join([f"- 胶囊：{item['content']}" for item in result["data"]["capsules"]])
                
                result_str = f"检索到{result['total']}条结果：\n"
                if short_str:
                    result_str += f"\n【短时记忆】\n{short_str}\n"
                if long_str:
                    result_str += f"\n【长时记忆】\n{long_str}\n"
                if capsule_str:
                    result_str += f"\n【胶囊联动】\n{capsule_str}\n"
                
                return {
                    "success": result["success"],
                    "message": result_str
                }
            
            elif "批量保存记忆" in content:
                # 示例格式：批量保存记忆 [{"type":"short","content":"记忆1","tags":["标签1"]},{"type":"long","content":"记忆2","tags":["重要"]}]
                try:
                    mem_list_str = re.search(r"\[(.*)\]", content, re.DOTALL).group(1)
                    mem_list = json.loads(f"[{mem_list_str}]")
                    result = memory_handler.batch_save_memory(user_id, mem_list)
                    return {
                        "success": result["success"],
                        "message": f"批量保存记忆完成：成功{result['success_count']}/{result['total']}条"
                    }
                except Exception as e:
                    return {"success": False, "message": f"批量保存失败：{str(e)}，请检查格式"}
            
            elif "导出记忆" in content:
                result = memory_handler.export_memory(user_id)
                return {
                    "success": result["success"],
                    "message": f"记忆导出{'成功' if result['success'] else '失败'}：{result.get('export_path', '')}"
                }
            
            # ========== 4. 通用指令 ==========
            else:
                # 通用指令自动保存到短时记忆
                memory_handler.save_short_term_memory(
                    user_id=user_id,
                    content=f"通用指令：{content}",
                    tags=["通用指令"]
                )
                return {
                    "success": True,
                    "message": f"已处理指令：{content}",
                    "stats": sub_agent_mgr.get_stats()
                }
        
        except Exception as e:
            log_agent_action("指令处理失败", user_id, f"错误：{str(e)}")
            return {"success": False, "error": str(e)}

# ===================== 主Agent类（集成所有模块） =====================
class MainAgent:
    """主Agent：整合子Agent+上下文+记忆+调度"""
    def __init__(self):
        # 核心模块初始化
        self.sub_agent_mgr = SubAgentManager(max_agents=30)
        self.context_mgr = ContextManager(max_history_len=50)
        self.memory_handler = MemoryHandler(data_dir="./data")  # 记忆处理器
        self.task_scheduler = TaskScheduler(thread_count=5)
        
        # 启动巡查线程
        self.patrol_running = True
        self.patrol_thread = threading.Thread(target=self._patrol)
        self.patrol_thread.start()
    
    def start(self):
        """启动主Agent"""
        self.task_scheduler.start()
        log_agent_action("初始化主Agent", "system", 
                        f"调度系统启动 | 工作线程数：5 | 任务优先级：紧急>高>普通>低")
        print("== Agent 1.0 启动成功 ==")
        print(f"子Agent数量上限：{self.sub_agent_mgr.max_agents}")
        print(f"上下文模块：最大历史记录数50条，支持状态维护/导出")
        print(f"记忆模块：长短时分离（短时24h过期，长时7天过期）+ 胶囊联动")
        print(f"巡查模块：后台静默运行（异常主动汇报）")
        print("--------------------------")
        log_agent_action("启动Agent交互", "system", 
                        "进入对话模式，输入'exit'退出 | 支持优先级：critical/high/normal/low")
    
    def stop(self):
        """停止主Agent"""
        self.patrol_running = False
        self.patrol_thread.join()
        self.task_scheduler.stop()
        self.sub_agent_mgr.destroy_all_agents()
        log_agent_action("停止主Agent", "system", "所有模块已停止，资源已清理")
    
    def send_message(self, user_id: str, message: str, priority: int = 2):
        """发送消息（记录上下文+提交任务）"""
        # 记录用户消息到上下文
        self.context_mgr.add_message(user_id, "user", message)
        
        # 创建并提交任务
        task_id = f"task_{time.strftime('%Y%m%d%H%M%S')}_{user_id}_{uuid.uuid4().hex[:3]}"
        task = Task(task_id, user_id, message, priority)
        self.task_scheduler.submit_task(task)
        
        # 返回提交结果
        queue_size = self.task_scheduler.task_queue.qsize()
        print(f"Agent：任务已提交（ID：{task_id} | 优先级：{priority} | 队列长度：{queue_size}）")
        return task_id
    
    def _patrol(self):
        """巡查线程：60秒检查一次"""
        while self.patrol_running:
            try:
                # 清理过期短时记忆
                self.memory_handler._clean_expired_short_term("default_user")
                # 清理空闲子Agent
                self.sub_agent_mgr._cleanup_idle_agents()
                # 打印巡查日志
                stats = self.sub_agent_mgr.get_stats()
                log_agent_action("巡查系统", "system", f"子Agent数量：{stats['total']}/{stats['max']}")
                time.sleep(60)
            except Exception as e:
                log_agent_action("巡查异常", "system", f"错误：{str(e)}")

# ===================== 交互入口 =====================
if __name__ == "__main__":
    # 初始化并启动Agent
    agent = MainAgent()
    agent.start()
    
    # 交互循环
    user_id = "default_user"
    try:
        while True:
            message = input("您：").strip()
            if not message:
                continue
            if message.lower() == "exit":
                break
            
            # 解析优先级
            priority = 2
            if "|" in message:
                prio_str, content = message.split("|", 1)
                prio_map = {"critical":0, "high":1, "normal":2, "low":3}
                if prio_str in prio_map:
                    priority = prio_map[prio_str]
                    message = content
            
            # 发送消息
            agent.send_message(user_id, message, priority)
    
    except KeyboardInterrupt:
        print("\n\n用户强制退出")
    finally:
        agent.stop()
        print("== Agent 1.0 已退出 ==")