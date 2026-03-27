#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Agent 1.0 生产级最终完整版
集成：专业版SubAgentManager + ContextManager + MemoryHandler + PatrolSystem + 任务调度
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

# ===================== 第三方依赖处理（psutil） =====================
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("[警告] 未安装psutil，系统资源巡查功能将禁用，请执行：pip install psutil")

# ===================== 基础工具函数（补充缺失依赖） =====================
def clean_text(text: str) -> str:
    """清理文本（去除多余空格、换行、特殊字符）"""
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9，。！？：；""''()（）【】]', '', text)
    return text

def log_agent_action(action: str, user_id: str, detail: str = ""):
    """打印Agent操作日志（带时间戳）"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    print(f"[{timestamp}] [{user_id}] {action}：{detail}")

def format_timestamp(timestamp: float) -> str:
    """格式化时间戳为字符串（补充PatrolSystem依赖）"""
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")

# ===================== 模拟缺失的记忆/胶囊模块 =====================
class ShortTermMemory:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(exist_ok=True)
        self.memory_pool = {}  # {user_id: {mem_id: {"content": "", "context": {}, "tags": [], "expire_at": 0, "priority": 1}}}
    
    def save(self, user_id: str, content: str, context: dict, tags: list, expire_at: float, priority: int) -> dict:
        mem_id = f"short_{int(time.time())}_{len(self.memory_pool.get(user_id, {}))}"
        if user_id not in self.memory_pool:
            self.memory_pool[user_id] = {}
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
        if user_id not in self.memory_pool:
            return {"success": True, "data": []}
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
        results = sorted(results, key=lambda x: x["create_time"], reverse=True)[:limit]
        return {"success": True, "data": results}
    
    def clean_expired(self, user_id: str) -> int:
        if user_id not in self.memory_pool:
            return 0
        now = time.time()
        expired_ids = [mem_id for mem_id, mem in self.memory_pool[user_id].items() if mem["expire_at"] > 0 and now > mem["expire_at"]]
        for mem_id in expired_ids:
            del self.memory_pool[user_id][mem_id]
        return len(expired_ids)

class LongTermMemory:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(exist_ok=True)
        self.memory_pool = {}  # {user_id: {mem_id: {"content": "", "context": {}, "tags": [], "expire_at": 0, "priority": 2}}}
    
    def save(self, user_id: str, content: str, context: dict, tags: list, expire_at: float, priority: int) -> dict:
        mem_id = f"long_{int(time.time())}_{len(self.memory_pool.get(user_id, {}))}"
        if user_id not in self.memory_pool:
            self.memory_pool[user_id] = {}
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

class CapsuleManager:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(exist_ok=True)
        self.capsules = {}  # {user_id: {capsule_id: {"content": "", "create_time": 0}}}
    
    def search_capsules(self, query: str, user_id: str, top_k: int) -> dict:
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

# ===================== MemoryHandler（完整保留） =====================
class MemoryHandler:
    """记忆处理器：完善长短时记忆 + 胶囊联动"""
    def __init__(self, data_dir=None):
        self.data_dir = Path(data_dir or "./data")
        self.data_dir.mkdir(exist_ok=True)
        
        # 初始化记忆模块
        self.short_term = ShortTermMemory(self.data_dir / "short_term")
        self.long_term = LongTermMemory(self.data_dir / "long_term")
        self.capsule_manager = CapsuleManager(self.data_dir / "capsules")
        
        # 记忆配置
        self.short_term_expire = 3600 * 24  # 短时记忆过期时间：24小时
        self.long_term_expire = 3600 * 24 * 7  # 普通长时记忆过期：7天
        self.priority_tags = ["重要", "偏好", "习惯"]  # 高优先级标签（永不删除）

    def save_short_term_memory(self, user_id, content, context=None, tags=None):
        content = clean_text(content)
        tags = tags or []
        context = context or {}
        expire_at = time.time() + self.short_term_expire
        
        result = self.short_term.save(
            user_id=user_id,
            content=content,
            context=context,
            tags=tags,
            expire_at=expire_at,
            priority=1
        )
        
        self._clean_expired_short_term(user_id)
        log_agent_action("保存短时记忆", user_id, f"成功：{result['success']} | 标签：{tags}")
        return result

    def save_long_term_memory(self, user_id, content, context=None, tags=None, priority=2):
        content = clean_text(content)
        tags = tags or []
        context = context or {}
        
        if any(tag in self.priority_tags for tag in tags):
            expire_at = 0
        else:
            expire_at = time.time() + self.long_term_expire
        
        result = self.long_term.save(
            user_id=user_id,
            content=content,
            context=context,
            tags=tags,
            expire_at=expire_at,
            priority=priority
        )
        
        log_agent_action("保存长时记忆", user_id, f"成功：{result['success']} | 优先级：{priority}")
        return result

    def search_memory(self, user_id, keywords, memory_type="all", limit=5):
        keywords = clean_text(keywords)
        results = {"short_term": [], "long_term": [], "capsules": []}
        
        if memory_type in ["all", "short_term"] and self.short_term:
            short_result = self.short_term.search(user_id=user_id, keywords=keywords, limit=limit)
            results["short_term"] = short_result.get("data", [])
        
        if memory_type in ["all", "long_term"] and self.long_term:
            long_result = self.long_term.search(user_id=user_id, keywords=keywords, limit=limit)
            results["long_term"] = long_result.get("data", [])
        
        if memory_type in ["all", "capsules"] and self.capsule_manager:
            capsule_result = self.capsule_manager.search_capsules(query=keywords, user_id=user_id, top_k=limit)
            results["capsules"] = capsule_result.get("data", [])
        
        total = len(results["short_term"]) + len(results["long_term"]) + len(results["capsules"])
        log_agent_action("检索记忆", user_id, f"找到{total}条结果（短时{len(results['short_term'])}+长时{len(results['long_term'])}+胶囊{len(results['capsules'])}）")
        
        return {
            "success": True,
            "data": results,
            "total": total
        }

    def batch_save_memory(self, user_id, memory_list):
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
        if not self.short_term:
            return
        try:
            deleted = self.short_term.clean_expired(user_id=user_id)
            if deleted > 0:
                log_agent_action("清理过期记忆", user_id, f"删除{deleted}条过期短时记忆")
        except Exception as e:
            log_agent_action("清理过期记忆", user_id, f"失败：{str(e)}")

    def export_memory(self, user_id, export_path=None):
        export_path = Path(export_path or f"./exports/memory_{user_id}_{datetime.now().strftime('%Y%m%d')}.json")
        export_path.parent.mkdir(exist_ok=True)
        
        all_memory = self.search_memory(user_id, "", memory_type="all", limit=1000)
        
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
        self.create_time = format_timestamp(time.time())  # 适配巡查系统
    
    def execute_task(self, task_desc: str) -> dict:
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
        return self.status

# ===================== 专业版SubAgentManager（适配巡查系统） =====================
class SubAgentManager:
    def __init__(self, max_agents: int = 30):
        self.max_agents = max_agents
        self.max_sub_agents = max_agents  # 适配巡查系统的属性名
        self.agents = {}  # agent_id -> (agent_instance, created_at, last_active)
        self.sub_agent_pool = {}  # 适配巡查系统：{sa_id: {"user_id": "", "status": "", "create_time": ""}}
        self.lock = threading.RLock()

    def create_agent(self, agent_type: str, params: dict, user_id: str = "default_user") -> Optional[str]:
        """创建子Agent实例（适配user_id参数）"""
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
            
            # 适配巡查系统的sub_agent_pool
            self.sub_agent_pool[agent_id] = {
                "user_id": user_id,
                "status": agent_instance.status,
                "create_time": agent_instance.create_time,
                "last_active": format_timestamp(time.time())
            }
            
            print(f"[SubAgentManager] 成功创建子Agent：{agent_id}")
            return agent_id

    def get_agent(self, agent_id: str) -> Optional[ExampleAgent]:
        with self.lock:
            if agent_id in self.agents:
                instance, created, _ = self.agents[agent_id]
                self.agents[agent_id] = (instance, created, time.time())
                # 更新巡查系统的状态
                if agent_id in self.sub_agent_pool:
                    self.sub_agent_pool[agent_id]["status"] = instance.status
                    self.sub_agent_pool[agent_id]["last_active"] = format_timestamp(time.time())
                return instance
            return None

    def destroy_agent(self, agent_id: str) -> bool:
        """销毁指定子Agent"""
        with self.lock:
            if agent_id in self.agents:
                instance, _, _ = self.agents[agent_id]
                print(f"[SubAgentManager] 销毁子Agent：{agent_id} | 状态：{instance.get_status()}")
                del self.agents[agent_id]
                # 同步更新sub_agent_pool
                if agent_id in self.sub_agent_pool:
                    del self.sub_agent_pool[agent_id]
                return True
            return False

    def destroy_sub_agent(self, agent_id: str) -> dict:
        """适配巡查系统的销毁方法（返回dict格式）"""
        success = self.destroy_agent(agent_id)
        return {"success": success, "msg": f"销毁{'成功' if success else '失败'}"}

    def _cleanup_idle_agents(self, idle_timeout: int = 300):
        """清理空闲超过5分钟的子Agent"""
        now = time.time()
        with self.lock:
            to_delete = [aid for aid, (_, created, last) in self.agents.items() if now - last > idle_timeout]
            for aid in to_delete:
                print(f"[SubAgentManager] 清理空闲子Agent: {aid}")
                del self.agents[aid]
                if aid in self.sub_agent_pool:
                    del self.sub_agent_pool[aid]

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
        self.max_history_len = max_history_len
        self.context_pool = {}  # {user_id: {"history": [], "state": {}, "create_time": ""}}
    
    def init_context(self, user_id):
        if user_id not in self.context_pool:
            self.context_pool[user_id] = {
                "history": [],
                "state": {},
                "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            log_agent_action("初始化上下文", user_id, f"最大历史长度：{self.max_history_len}")
        return self.context_pool[user_id]
    
    def add_message(self, user_id, role, content):
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
        context = self.init_context(user_id)
        return context["history"][-limit:]
    
    def set_state(self, user_id, key, value):
        context = self.init_context(user_id)
        context["state"][key] = value
        log_agent_action("设置会话状态", user_id, f"{key} = {value}")
        return context["state"]
    
    def get_state(self, user_id, key=None):
        context = self.init_context(user_id)
        if key:
            return context["state"].get(key)
        return context["state"]
    
    def clear_context(self, user_id):
        if user_id in self.context_pool:
            del self.context_pool[user_id]
            log_agent_action("清空上下文", user_id)
        return True
    
    def export_context(self, user_id):
        context = self.init_context(user_id)
        return json.dumps(context, ensure_ascii=False, indent=2)

# ===================== ToolInvoker（适配巡查系统） =====================
class ToolInvoker:
    """工具调用器：模拟工具调用日志（适配巡查系统）"""
    def __init__(self, data_dir=None):
        self.data_dir = data_dir
        self.supported_tools = ["weatherapi", "summarize_text", "file_operation"]
        self.invoke_log = []  # 适配巡查系统：工具调用日志
    
    def invoke_tool(self, user_id: str, tool_name: str, **kwargs) -> dict:
        """调用工具（记录日志）"""
        success = tool_name in self.supported_tools
        log_entry = {
            "user_id": user_id,
            "tool_name": tool_name,
            "success": success,
            "time": format_timestamp(time.time()),
            "params": kwargs
        }
        self.invoke_log.append(log_entry)
        # 只保留最近100条日志
        if len(self.invoke_log) > 100:
            self.invoke_log = self.invoke_log[-100:]
        
        if not success:
            return {"success": False, "error": f"不支持的工具：{tool_name}"}
        time.sleep(0.5)
        return {"success": True, "tool_name": tool_name, "result": f"模拟{tool_name}调用结果：{kwargs}"}

# ===================== 你提供的PatrolSystem（完整保留+适配） =====================
class PatrolSystem:
    """巡查系统：完善多维度巡查 + 异常分级 + 自动修复"""
    def __init__(self, patrol_interval=60):
        # 基础配置
        self.patrol_interval = patrol_interval  # 巡查间隔（秒）
        self.patrol_thread = None
        self.is_running = False
        
        # 异常分级配置
        self.error_levels = {
            "warning": "警告（不影响核心功能）",
            "error": "错误（功能异常）",
            "critical": "紧急（系统不可用）"
        }
        
        # 巡查历史（用于生成报告）
        self.patrol_history = []
        
        # 依赖注入（后续通过setter赋值）
        self.sub_agent_manager = None
        self.memory_handler = None
        self.tool_invoker = None

    # ========== 依赖注入（解耦） ==========
    def set_sub_agent_manager(self, manager):
        self.sub_agent_manager = manager

    def set_memory_handler(self, handler):
        self.memory_handler = handler

    def set_tool_invoker(self, invoker):
        self.tool_invoker = invoker

    # ========== 巡查启停 ==========
    def start_patrol(self, user_id=None):
        """启动巡查线程"""
        if self.is_running:
            log_agent_action("启动巡查", user_id or "system", "巡查已在运行")
            return {"success": False, "error": "巡查已启动"}
        
        self.is_running = True
        self.patrol_thread = threading.Thread(target=self._patrol_loop, args=(user_id,), daemon=True)
        self.patrol_thread.start()
        log_agent_action("启动巡查", user_id or "system", f"巡查间隔：{self.patrol_interval}秒 | 异常分级：警告/错误/紧急")
        return {"success": True}

    def stop_patrol(self):
        """停止巡查线程"""
        self.is_running = False
        if self.patrol_thread and self.patrol_thread.is_alive():
            self.patrol_thread.join(timeout=5)
        log_agent_action("停止巡查", "system", "巡查已终止")
        return {"success": True}

    def manual_patrol(self, user_id=None):
        """手动触发一次巡查（用于调试/紧急检查）"""
        log_agent_action("手动巡查", user_id or "system", "开始执行手动巡查")
        report = self._do_patrol(user_id, manual=True)
        log_agent_action("手动巡查", user_id or "system", f"巡查完成 | 异常数：{len(report['exceptions'])}")
        return report

    # ========== 核心巡查逻辑 ==========
    def _patrol_loop(self, user_id):
        """巡查循环（后台线程）"""
        while self.is_running:
            try:
                # 执行巡查
                report = self._do_patrol(user_id)
                # 保存巡查报告
                self.patrol_history.append(report)
                # 只保留最近100条巡查记录
                if len(self.patrol_history) > 100:
                    self.patrol_history = self.patrol_history[-100:]
                # 等待下一次巡查
                time.sleep(self.patrol_interval)
            except Exception as e:
                log_agent_action("巡查异常", user_id or "system", f"错误：{str(e)}")
                time.sleep(self.patrol_interval)

    def _do_patrol(self, user_id=None, manual=False):
        """完善：多维度巡查 + 异常分级 + 自动修复"""
        patrol_time = format_timestamp(time.time())
        report = {
            "patrol_time": patrol_time,
            "type": "manual" if manual else "auto",
            "check_items": [],
            "exceptions": [],
            "fix_actions": []
        }

        # 1. 巡查子Agent状态
        if self.sub_agent_manager:
            sub_agent_report = self._check_sub_agents(user_id or "default_user")
            report["check_items"].append({"name": "子Agent状态", "status": sub_agent_report["status"]})
            report["exceptions"].extend(sub_agent_report["exceptions"])
            report["fix_actions"].extend(sub_agent_report["fix_actions"])

        # 2. 巡查记忆库健康度
        if self.memory_handler:
            memory_report = self._check_memory_health(user_id or "default_user")
            report["check_items"].append({"name": "记忆库健康度", "status": memory_report["status"]})
            report["exceptions"].extend(memory_report["exceptions"])
            report["fix_actions"].extend(memory_report["fix_actions"])

        # 3. 巡查工具调用异常
        if self.tool_invoker:
            tool_report = self._check_tool_invoke()
            report["check_items"].append({"name": "工具调用状态", "status": tool_report["status"]})
            report["exceptions"].extend(tool_report["exceptions"])
            report["fix_actions"].extend(tool_report["fix_actions"])

        # 4. 巡查系统资源（CPU/内存/磁盘）- 适配psutil可用性
        if PSUTIL_AVAILABLE:
            system_report = self._check_system_resources()
            report["check_items"].append({"name": "系统资源", "status": system_report["status"]})
            report["exceptions"].extend(system_report["exceptions"])
            report["fix_actions"].extend(system_report["fix_actions"])
        else:
            report["check_items"].append({"name": "系统资源", "status": "disabled", "msg": "psutil未安装，禁用系统资源巡查"})

        # 日志记录
        log_agent_action(
            "执行巡查", user_id or "system",
            f"时间：{patrol_time} | 异常：{len(report['exceptions'])} | 修复：{len(report['fix_actions'])}"
        )

        return report

    # ========== 各维度巡查实现 ==========
    def _check_sub_agents(self, user_id):
        """巡查子Agent：卡死/超时/数量超限"""
        result = {"status": "normal", "exceptions": [], "fix_actions": []}
        
        try:
            # 获取所有子Agent
            sub_agents = self.sub_agent_manager.sub_agent_pool
            if not sub_agents:
                return result
            
            # 检查每个子Agent
            for sa_id, sa_info in sub_agents.items():
                # 1. 状态检查（卡死）
                create_ts = self._parse_timestamp(sa_info["create_time"])
                if sa_info["status"] == "running" and (time.time() - create_ts > 3600):
                    # 异常：运行超过1小时 → 紧急
                    exc = {
                        "level": "critical",
                        "msg": f"子Agent {sa_id} 运行超时（>1小时），可能卡死",
                        "user_id": sa_info["user_id"],
                        "time": format_timestamp(time.time())
                    }
                    result["exceptions"].append(exc)
                    result["status"] = "exception"
                    
                    # 自动修复：销毁卡死的子Agent
                    fix_res = self.sub_agent_manager.destroy_sub_agent(sa_id)
                    if fix_res["success"]:
                        result["fix_actions"].append(f"已销毁卡死的子Agent {sa_id}")
            
            # 2. 数量超限检查
            user_sub_agents = [sa for sa in sub_agents.values() if sa["user_id"] == user_id]
            if len(user_sub_agents) >= self.sub_agent_manager.max_sub_agents:
                # 异常：数量超限 → 警告
                exc = {
                    "level": "warning",
                    "msg": f"用户 {user_id} 子Agent数量超限（{len(user_sub_agents)}/{self.sub_agent_manager.max_sub_agents}）",
                    "user_id": user_id,
                    "time": format_timestamp(time.time())
                }
                result["exceptions"].append(exc)
                if result["status"] == "normal":
                    result["status"] = "warning"

        except Exception as e:
            result["status"] = "error"
            result["exceptions"].append({
                "level": "error",
                "msg": f"子Agent巡查失败：{str(e)}",
                "user_id": user_id,
                "time": format_timestamp(time.time())
            })
        
        return result

    def _check_memory_health(self, user_id):
        """巡查记忆库：过期数据/存储占用过大"""
        result = {"status": "normal", "exceptions": [], "fix_actions": []}
        
        try:
            # 1. 清理过期短时记忆（自动修复）
            if hasattr(self.memory_handler, "_clean_expired_short_term"):
                self.memory_handler._clean_expired_short_term(user_id)
                result["fix_actions"].append(f"已清理用户 {user_id} 过期短时记忆")
            
            # 2. 检查存储占用（示例：超过100MB警告）
            memory_path = self.memory_handler.data_dir / "long_term" / user_id
            if memory_path.exists():
                try:
                    total_size = sum(f.stat().st_size for f in memory_path.rglob('*') if f.is_file())
                    if total_size > 1024 * 1024 * 100:  # 100MB
                        exc = {
                            "level": "warning",
                            "msg": f"用户 {user_id} 记忆库占用过大（{total_size/(1024*1024):.2f}MB > 100MB）",
                            "user_id": user_id,
                            "time": format_timestamp(time.time())
                        }
                        result["exceptions"].append(exc)
                        result["status"] = "warning"
                except:
                    # 路径不存在或权限问题，跳过
                    pass

        except Exception as e:
            result["status"] = "error"
            result["exceptions"].append({
                "level": "error",
                "msg": f"记忆库巡查失败：{str(e)}",
                "user_id": user_id,
                "time": format_timestamp(time.time())
            })
        
        return result

    def _check_tool_invoke(self):
        """巡查工具调用：频繁失败/超时"""
        result = {"status": "normal", "exceptions": [], "fix_actions": []}
        
        try:
            # 示例：检查工具调用失败率（实际需对接工具调用日志）
            if hasattr(self.tool_invoker, "invoke_log") and self.tool_invoker.invoke_log:
                # 最近10次调用失败数
                recent_logs = self.tool_invoker.invoke_log[-10:]
                fail_count = sum(1 for log in recent_logs if not log["success"])
                
                if fail_count >= 5:  # 失败率≥50% → 错误
                    exc = {
                        "level": "error",
                        "msg": f"工具调用失败率过高（{fail_count}/10）",
                        "user_id": "system",
                        "time": format_timestamp(time.time())
                    }
                    result["exceptions"].append(exc)
                    result["status"] = "error"

        except Exception as e:
            result["exceptions"].append({
                "level": "error",
                "msg": f"工具调用巡查失败：{str(e)}",
                "user_id": "system",
                "time": format_timestamp(time.time())
            })
        
        return result

    def _check_system_resources(self):
        """巡查系统资源：CPU/内存/磁盘（适配psutil可用性）"""
        result = {"status": "normal", "exceptions": [], "fix_actions": []}
        
        try:
            if not PSUTIL_AVAILABLE:
                return result
            
            # 1. CPU使用率（>80%警告，>95%紧急）
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > 95:
                exc = {
                    "level": "critical",
                    "msg": f"CPU使用率过高（{cpu_percent}% > 95%）",
                    "user_id": "system",
                    "time": format_timestamp(time.time())
                }
                result["exceptions"].append(exc)
                result["status"] = "exception"
            elif cpu_percent > 80:
                exc = {
                    "level": "warning",
                    "msg": f"CPU使用率偏高（{cpu_percent}% > 80%）",
                    "user_id": "system",
                    "time": format_timestamp(time.time())
                }
                result["exceptions"].append(exc)
                result["status"] = "warning"

            # 2. 内存使用率（>85%警告）
            mem_percent = psutil.virtual_memory().percent
            if mem_percent > 85:
                exc = {
                    "level": "warning",
                    "msg": f"内存使用率偏高（{mem_percent}% > 85%）",
                    "user_id": "system",
                    "time": format_timestamp(time.time())
                }
                result["exceptions"].append(exc)
                if result["status"] == "normal":
                    result["status"] = "warning"

            # 3. 磁盘使用率（>90%紧急）
            disk_percent = psutil.disk_usage('/').percent
            if disk_percent > 90:
                exc = {
                    "level": "critical",
                    "msg": f"磁盘使用率过高（{disk_percent}% > 90%）",
                    "user_id": "system",
                    "time": format_timestamp(time.time())
                }
                result["exceptions"].append(exc)
                result["status"] = "exception"

        except Exception as e:
            result["exceptions"].append({
                "level": "error",
                "msg": f"系统资源巡查失败：{str(e)}",
                "user_id": "system",
                "time": format_timestamp(time.time())
            })
        
        return result

    # ========== 辅助方法 ==========
    def _parse_timestamp(self, timestamp_str):
        """解析时间字符串为时间戳"""
        try:
            dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            return dt.timestamp()
        except:
            return time.time()

    def get_patrol_report(self, last_n=10):
        """获取最近N次巡查报告"""
        return {
            "success": True,
            "total": len(self.patrol_history),
            "reports": self.patrol_history[-last_n:]
        }

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
        self.memory_handler = MemoryHandler(data_dir="./data")
        self.tool_invoker = ToolInvoker()  # 新增工具调用器
        self.patrol_system = PatrolSystem(patrol_interval=60)  # 集成巡查系统
        
        # 巡查系统依赖注入
        self.patrol_system.set_sub_agent_manager(self.sub_agent_mgr)
        self.patrol_system.set_memory_handler(self.memory_handler)
        self.patrol_system.set_tool_invoker(self.tool_invoker)
    
    def start(self):
        """启动调度器（自动启动巡查系统）"""
        self.running = True
        for i in range(self.thread_count):
            t = threading.Thread(target=self._worker, args=(i,))
            self.worker_threads.append(t)
            t.start()
            log_agent_action("启动工作线程", "system", f"线程{i}已启动")
        
        # 自动启动巡查系统
        self.patrol_system.start_patrol()
    
    def stop(self):
        """停止调度器（停止巡查系统）"""
        self.running = False
        for t in self.worker_threads:
            t.join()
        # 停止巡查系统
        self.patrol_system.stop_patrol()
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
                        task, self.sub_agent_mgr, self.context_mgr, self.memory_handler,
                        self.tool_invoker, self.patrol_system
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

# ===================== 指令处理器（集成巡查系统） =====================
class InstructionProcessor:
    """指令处理器：支持子Agent/上下文/记忆/巡查管理"""
    @classmethod
    def handle_instruction(cls, task: Task, sub_agent_mgr: SubAgentManager, 
                          context_mgr: ContextManager, memory_handler: MemoryHandler,
                          tool_invoker: ToolInvoker, patrol_system: PatrolSystem) -> dict:
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
                        params={"user_id": user_id, "task_index": i+1},
                        user_id=user_id
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
                        params={"task_desc": task_desc},
                        user_id=user_id
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
            
            # ========== 3. 记忆相关指令 ==========
            elif "保存短时记忆" in content:
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
            
            # ========== 4. 工具调用指令 ==========
            elif "调用工具" in content:
                # 格式：调用工具 weatherapi city=北京 date=2026-03-23
                tool_match = re.search(r"调用工具 (\w+) (.*)", content)
                if tool_match:
                    tool_name = tool_match.group(1)
                    params_str = tool_match.group(2)
                    # 解析参数（如 city=北京 → {"city": "北京"}）
                    params = {}
                    for param in params_str.split():
                        if "=" in param:
                            k, v = param.split("=", 1)
                            params[k] = v
                    # 调用工具
                    result = tool_invoker.invoke_tool(user_id, tool_name, **params)
                    return {
                        "success": result["success"],
                        "message": f"工具调用{'成功' if result['success'] else '失败'}：{result.get('result', result.get('error', ''))}"
                    }
                else:
                    return {"success": False, "message": "格式错误，示例：调用工具 weatherapi city=北京"}
            
            # ========== 5. 巡查系统指令（核心新增） ==========
            elif "启动巡查" in content:
                result = patrol_system.start_patrol(user_id)
                return {
                    "success": result["success"],
                    "message": f"巡查系统{'启动成功' if result['success'] else '启动失败'}：{result.get('error', '')}"
                }
            
            elif "停止巡查" in content:
                result = patrol_system.stop_patrol()
                return {
                    "success": result["success"],
                    "message": f"巡查系统{'停止成功' if result['success'] else '停止失败'}"
                }
            
            elif "手动巡查" in content:
                report = patrol_system.manual_patrol(user_id)
                # 格式化巡查报告
                exceptions_str = "\n".join([f"- [{exc['level']}] {exc['msg']}" for exc in report["exceptions"]])
                fixes_str = "\n".join([f"- {fix}" for fix in report["fix_actions"]])
                report_str = f"""
Patrol report ({report['type']})
Time: {report['patrol_time']}
Check items: {[f"{item['name']} (status: {item['status']})" for item in report['check_items']]}
Exception count: {len(report['exceptions'])}
{exceptions_str if exceptions_str else '- No exceptions'}
Auto-fixes: {len(report['fix_actions'])}
{fixes_str if fixes_str else '- No fix actions'}
                """.strip()
                return {
                    "success": True,
                    "message": report_str
                }
            
            elif "查看巡查报告" in content:
                # 格式：查看巡查报告 最近5次
                limit_match = re.search(r"最近(\d+)次", content)
                last_n = int(limit_match.group(1)) if limit_match else 5
                report = patrol_system.get_patrol_report(last_n=last_n)
                # 格式化报告列表
                reports_str = "\n\n".join([
                    f"【巡查时间：{r['patrol_time']}】\n异常数：{len(r['exceptions'])} | 修复数：{len(r['fix_actions'])}"
                    for r in report["reports"]
                ])
                return {
                    "success": True,
                    "message": f"最近{last_n}次巡查报告（总计{report['total']}次）：\n{reports_str}"
                }
            
            # ========== 6. 通用指令 ==========
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
    """主Agent：整合子Agent+上下文+记忆+工具+巡查+调度"""
    def __init__(self):
        # 核心模块初始化
        self.sub_agent_mgr = SubAgentManager(max_agents=30)
        self.context_mgr = ContextManager(max_history_len=50)
        self.memory_handler = MemoryHandler(data_dir="./data")
        self.tool_invoker = ToolInvoker()
        self.patrol_system = PatrolSystem(patrol_interval=60)
        self.task_scheduler = TaskScheduler(thread_count=5)
        
        # 巡查系统依赖注入
        self.patrol_system.set_sub_agent_manager(self.sub_agent_mgr)
        self.patrol_system.set_memory_handler(self.memory_handler)
        self.patrol_system.set_tool_invoker(self.tool_invoker)
    
    def start(self):
        """启动主Agent"""
        self.task_scheduler.start()
        log_agent_action("初始化主Agent", "system", 
                        f"调度系统启动 | 工作线程数：5 | 任务优先级：紧急>高>普通>低")
        print("== Agent 1.0 启动成功 ==")
        print(f"子Agent数量上限：{self.sub_agent_mgr.max_agents}")
        print(f"上下文模块：最大历史记录数50条，支持状态维护/导出")
        print(f"记忆模块：长短时分离（短时24h过期，长时7天过期）+ 胶囊联动")
        print(f"巡查系统：自动巡查（60秒间隔），多维度监控+异常分级+自动修复")
        print(f"工具模块：支持weatherapi/summarize_text/file_operation调用")
        print("--------------------------")
        log_agent_action("启动Agent交互", "system", 
                        "进入对话模式，输入'exit'退出 | 支持优先级：critical/high/normal/low")
    
    def stop(self):
        """停止主Agent"""
        self.task_scheduler.stop()
        self.sub_agent_mgr.destroy_all_agents()
        self.patrol_system.stop_patrol()  # 确保巡查系统停止
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

# ===================== 交互入口 =====================
if __name__ == "__main__":
    # 安装psutil提示
    if not PSUTIL_AVAILABLE:
        print("\n【重要提示】请安装psutil以启用系统资源巡查：pip install psutil\n")
    
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