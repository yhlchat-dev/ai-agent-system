#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Agent 1.0 生产级最终完整版
集成：专业版SubAgentManager + ContextManager + MemoryHandler + PatrolSystem + ReplyGenerator + 任务调度
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
from core.agent.utils import clean_text, log_agent_action

# ===================== 第三方依赖处理（psutil） =====================
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("[警告] 未安装psutil，系统资源巡查功能将禁用，请执行：pip install psutil")

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

def format_timestamp(timestamp: float) -> str:
    """格式化时间戳为字符串"""
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")

# ===================== 你提供的ReplyGenerator（完整保留） =====================
class ReplyGenerator:
    """回复生成器：管家风格、不话痨、话术规则"""
    def __init__(self, style="管家", max_length=500):
        self.style = style  # 回复风格：管家/简洁/详细
        self.max_length = max_length  # 最大回复长度
        # 话术模板（可根据实际需求扩展）
        self.templates = {
            "greeting": "您好😊，请问有什么可以帮助您的？",
            "finish": "已为您完成任务✅，如果还有其他需求，随时都在～",
            "error": "抱歉😥，处理过程中出现了一点小问题：{error}，我会尽快改进的！",
            "agent_create": "已为您创建{count}个子Agent✅，当前可用子Agent总数为{total}个～",
            "agent_destroy": "已为您销毁{count}个子Agent✅，剩余可用子Agent数量为{total}个～",
            "memory_save": "已为您保存{type}记忆✅，内容：{content}～",
            "patrol_start": "已为您启动巡查系统🔍，巡查间隔为{interval}秒，将持续监控系统状态～",
            "patrol_stop": "已为您停止巡查系统🛑，如有需要可随时再次启动～"
        }
    
    def generate_reply(self, user_id, content, context=None):
        """生成最终回复（应用风格和规则）"""
        # 1. 清理内容
        content = clean_text(content)
        
        # 2. 长度限制（不话痨核心规则）
        if len(content) > self.max_length:
            content = content[:self.max_length] + "..."
            log_agent_action("生成回复", user_id, "内容过长，已截断至最大长度")
        
        # 3. 应用风格
        if self.style == "管家":
            content = self._apply_butler_style(content)
        elif self.style == "简洁":
            content = self._apply_simple_style(content)
        elif self.style == "详细":
            content = self._apply_detail_style(content)
        
        log_agent_action("生成回复", user_id, f"风格：{self.style} | 最终长度：{len(content)}")
        return content
    
    def _apply_butler_style(self, content):
        """应用管家风格：礼貌、贴心、有条理"""
        # 核心规则：开头礼貌，结尾贴心，语气温和
        polite_prefixes = ["您好", "好的", "已为您", "抱歉"]
        polite_suffixes = ["～", "。", "！", "✅", "😊"]
        
        # 开头添加礼貌用语（避免重复）
        if not any(content.startswith(p) for p in polite_prefixes):
            content = f"好的，{content}"
        
        # 结尾添加贴心后缀（避免重复）
        if not any(content.endswith(s) for s in polite_suffixes):
            content = f"{content}～"
        
        # 替换为管家风格的语气词
        content = content.replace("完成", "为您完成").replace("创建", "为您创建").replace("删除", "为您销毁")
        return content
    
    def _apply_simple_style(self, content):
        """应用简洁风格：去掉冗余，只保留核心"""
        # 核心规则：移除所有情感符号和礼貌用语，只保留关键信息
        content = content.replace("好的，", "").replace("～", "").replace("😊", "").replace("✅", "")
        content = content.replace("为您", "").replace("😥", "").replace("🔍", "").replace("🛑", "")
        content = re.sub(r"[✅😥😊🔍🛑～]", "", content)
        return content
    
    def _apply_detail_style(self, content):
        """应用详细风格：补充上下文和说明"""
        # 核心规则：在核心内容基础上，补充简要说明
        content = f"{content}\n（说明：如需要调整格式/内容，可直接告知我～）"
        return content
    
    def get_template(self, template_key, **kwargs):
        """获取话术模板并填充参数"""
        template = self.templates.get(template_key, "")
        try:
            return template.format(**kwargs)
        except KeyError as e:
            log_agent_action("模板填充失败", "system", f"缺失参数：{e} | 模板：{template_key}")
            return template  # 填充失败时返回原始模板
    
    def set_style(self, style):
        """动态切换回复风格"""
        valid_styles = ["管家", "简洁", "详细"]
        if style in valid_styles:
            self.style = style
            log_agent_action("切换回复风格", "system", f"已切换为{style}风格")
            return True
        return False
    
    def set_max_length(self, max_length):
        """调整最大回复长度（控制话痨程度）"""
        if isinstance(max_length, int) and max_length > 0:
            self.max_length = max_length
            log_agent_action("调整回复长度", "system", f"最大回复长度已设为{max_length}字符")
            return True
        return False

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

# ===================== MemoryHandler =====================
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
    """示例子Agent类"""
    def __init__(self, params: dict):
        self.params = params
        self.status = "idle"
        self.task_result = None
        self.create_time = format_timestamp(time.time())
    
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

# ===================== SubAgentManager =====================
class SubAgentManager:
    def __init__(self, max_agents: int = 30):
        self.max_agents = max_agents
        self.max_sub_agents = max_agents
        self.agents = {}  # agent_id -> (agent_instance, created_at, last_active)
        self.sub_agent_pool = {}  # 适配巡查系统
        self.lock = threading.RLock()

    def create_agent(self, agent_type: str, params: dict, user_id: str = "default_user") -> Optional[str]:
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
            
            # 适配巡查系统
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
                if agent_id in self.sub_agent_pool:
                    self.sub_agent_pool[agent_id]["status"] = instance.status
                    self.sub_agent_pool[agent_id]["last_active"] = format_timestamp(time.time())
                return instance
            return None

    def destroy_agent(self, agent_id: str) -> bool:
        with self.lock:
            if agent_id in self.agents:
                instance, _, _ = self.agents[agent_id]
                print(f"[SubAgentManager] 销毁子Agent：{agent_id} | 状态：{instance.get_status()}")
                del self.agents[agent_id]
                if agent_id in self.sub_agent_pool:
                    del self.sub_agent_pool[agent_id]
                return True
            return False

    def destroy_sub_agent(self, agent_id: str) -> dict:
        success = self.destroy_agent(agent_id)
        return {"success": success, "msg": f"销毁{'成功' if success else '失败'}"}

    def _cleanup_idle_agents(self, idle_timeout: int = 300):
        now = time.time()
        with self.lock:
            to_delete = [aid for aid, (_, created, last) in self.agents.items() if now - last > idle_timeout]
            for aid in to_delete:
                print(f"[SubAgentManager] 清理空闲子Agent: {aid}")
                del self.agents[aid]
                if aid in self.sub_agent_pool:
                    del self.sub_agent_pool[aid]

    def destroy_all_agents(self) -> int:
        with self.lock:
            agent_ids = list(self.agents.keys())
            for aid in agent_ids:
                self.destroy_agent(aid)
            print(f"[SubAgentManager] 批量销毁完成，共销毁{len(agent_ids)}个")
            return len(agent_ids)

    def get_stats(self) -> dict:
        with self.lock:
            return {
                "total": len(self.agents),
                "max": self.max_agents,
                "agents": list(self.agents.keys())
            }

# ===================== ContextManager =====================
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

# ===================== ToolInvoker =====================
class ToolInvoker:
    """工具调用器：模拟工具调用日志"""
    def __init__(self, data_dir=None):
        self.data_dir = data_dir
        self.supported_tools = ["weatherapi", "summarize_text", "file_operation"]
        self.invoke_log = []  # 适配巡查系统
    
    def invoke_tool(self, user_id: str, tool_name: str, **kwargs) -> dict:
        success = tool_name in self.supported_tools
        log_entry = {
            "user_id": user_id,
            "tool_name": tool_name,
            "success": success,
            "time": format_timestamp(time.time()),
            "params": kwargs
        }
        self.invoke_log.append(log_entry)
        if len(self.invoke_log) > 100:
            self.invoke_log = self.invoke_log[-100:]
        
        if not success:
            return {"success": False, "error": f"不支持的工具：{tool_name}"}
        time.sleep(0.5)
        return {"success": True, "tool_name": tool_name, "result": f"模拟{tool_name}调用结果：{kwargs}"}

# ===================== PatrolSystem =====================
class PatrolSystem:
    """巡查系统：完善多维度巡查 + 异常分级 + 自动修复"""
    def __init__(self, patrol_interval=60):
        self.patrol_interval = patrol_interval
        self.patrol_thread = None
        self.is_running = False
        self.error_levels = {
            "warning": "警告（不影响核心功能）",
            "error": "错误（功能异常）",
            "critical": "紧急（系统不可用）"
        }
        self.patrol_history = []
        self.sub_agent_manager = None
        self.memory_handler = None
        self.tool_invoker = None

    def set_sub_agent_manager(self, manager):
        self.sub_agent_manager = manager

    def set_memory_handler(self, handler):
        self.memory_handler = handler

    def set_tool_invoker(self, invoker):
        self.tool_invoker = invoker

    def start_patrol(self, user_id=None):
        if self.is_running:
            log_agent_action("启动巡查", user_id or "system", "巡查已在运行")
            return {"success": False, "error": "巡查已启动"}
        
        self.is_running = True
        self.patrol_thread = threading.Thread(target=self._patrol_loop, args=(user_id,), daemon=True)
        self.patrol_thread.start()
        log_agent_action("启动巡查", user_id or "system", f"巡查间隔：{self.patrol_interval}秒 | 异常分级：警告/错误/紧急")
        return {"success": True}

    def stop_patrol(self):
        self.is_running = False
        if self.patrol_thread and self.patrol_thread.is_alive():
            self.patrol_thread.join(timeout=5)
        log_agent_action("停止巡查", "system", "巡查已终止")
        return {"success": True}

    def manual_patrol(self, user_id=None):
        log_agent_action("手动巡查", user_id or "system", "开始执行手动巡查")
        report = self._do_patrol(user_id, manual=True)
        log_agent_action("手动巡查", user_id or "system", f"巡查完成 | 异常数：{len(report['exceptions'])}")
        return report

    def _patrol_loop(self, user_id):
        while self.is_running:
            try:
                report = self._do_patrol(user_id)
                self.patrol_history.append(report)
                if len(self.patrol_history) > 100:
                    self.patrol_history = self.patrol_history[-100:]
                time.sleep(self.patrol_interval)
            except Exception as e:
                log_agent_action("巡查异常", user_id or "system", f"错误：{str(e)}")
                time.sleep(self.patrol_interval)

    def _do_patrol(self, user_id=None, manual=False):
        patrol_time = format_timestamp(time.time())
        report = {
            "patrol_time": patrol_time,
            "type": "manual" if manual else "auto",
            "check_items": [],
            "exceptions": [],
            "fix_actions": []
        }

        if self.sub_agent_manager:
            sub_agent_report = self._check_sub_agents(user_id or "default_user")
            report["check_items"].append({"name": "子Agent状态", "status": sub_agent_report["status"]})
            report["exceptions"].extend(sub_agent_report["exceptions"])
            report["fix_actions"].extend(sub_agent_report["fix_actions"])

        if self.memory_handler:
            memory_report = self._check_memory_health(user_id or "default_user")
            report["check_items"].append({"name": "记忆库健康度", "status": memory_report["status"]})
            report["exceptions"].extend(memory_report["exceptions"])
            report["fix_actions"].extend(memory_report["fix_actions"])

        if self.tool_invoker:
            tool_report = self._check_tool_invoke()
            report["check_items"].append({"name": "工具调用状态", "status": tool_report["status"]})
            report["exceptions"].extend(tool_report["exceptions"])
            report["fix_actions"].extend(tool_report["fix_actions"])

        if PSUTIL_AVAILABLE:
            system_report = self._check_system_resources()
            report["check_items"].append({"name": "系统资源", "status": system_report["status"]})
            report["exceptions"].extend(system_report["exceptions"])
            report["fix_actions"].extend(system_report["fix_actions"])
        else:
            report["check_items"].append({"name": "系统资源", "status": "disabled", "msg": "psutil未安装，禁用系统资源巡查"})

        log_agent_action(
            "执行巡查", user_id or "system",
            f"时间：{patrol_time} | 异常：{len(report['exceptions'])} | 修复：{len(report['fix_actions'])}"
        )

        return report

    def _check_sub_agents(self, user_id):
        result = {"status": "normal", "exceptions": [], "fix_actions": []}
        try:
            sub_agents = self.sub_agent_manager.sub_agent_pool
            if not sub_agents:
                return result
            
            for sa_id, sa_info in sub_agents.items():
                create_ts = self._parse_timestamp(sa_info["create_time"])
                if sa_info["status"] == "running" and (time.time() - create_ts > 3600):
                    exc = {
                        "level": "critical",
                        "msg": f"子Agent {sa_id} 运行超时（>1小时），可能卡死",
                        "user_id": sa_info["user_id"],
                        "time": format_timestamp(time.time())
                    }
                    result["exceptions"].append(exc)
                    result["status"] = "exception"
                    
                    fix_res = self.sub_agent_manager.destroy_sub_agent(sa_id)
                    if fix_res["success"]:
                        result["fix_actions"].append(f"已销毁卡死的子Agent {sa_id}")
            
            user_sub_agents = [sa for sa in sub_agents.values() if sa["user_id"] == user_id]
            if len(user_sub_agents) >= self.sub_agent_manager.max_sub_agents:
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
        result = {"status": "normal", "exceptions": [], "fix_actions": []}
        try:
            if hasattr(self.memory_handler, "_clean_expired_short_term"):
                self.memory_handler._clean_expired_short_term(user_id)
                result["fix_actions"].append(f"已清理用户 {user_id} 过期短时记忆")
            
            memory_path = self.memory_handler.data_dir / "long_term" / user_id
            if memory_path.exists():
                try:
                    total_size = sum(f.stat().st_size for f in memory_path.rglob('*') if f.is_file())
                    if total_size > 1024 * 1024 * 100:
                        exc = {
                            "level": "warning",
                            "msg": f"用户 {user_id} 记忆库占用过大（{total_size/(1024*1024):.2f}MB > 100MB）",
                            "user_id": user_id,
                            "time": format_timestamp(time.time())
                        }
                        result["exceptions"].append(exc)
                        result["status"] = "warning"
                except:
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
        result = {"status": "normal", "exceptions": [], "fix_actions": []}
        try:
            if hasattr(self.tool_invoker, "invoke_log") and self.tool_invoker.invoke_log:
                recent_logs = self.tool_invoker.invoke_log[-10:]
                fail_count = sum(1 for log in recent_logs if not log["success"])
                
                if fail_count >= 5:
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
        result = {"status": "normal", "exceptions": [], "fix_actions": []}
        try:
            if not PSUTIL_AVAILABLE:
                return result
            
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

    def _parse_timestamp(self, timestamp_str):
        try:
            dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            return dt.timestamp()
        except:
            return time.time()

    def get_patrol_report(self, last_n=10):
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
        self.priority = priority
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
        self.tool_invoker = ToolInvoker()
        self.patrol_system = PatrolSystem(patrol_interval=60)
        self.reply_generator = ReplyGenerator(style="管家", max_length=500)  # 新增回复生成器
        
        # 巡查系统依赖注入
        self.patrol_system.set_sub_agent_manager(self.sub_agent_mgr)
        self.patrol_system.set_memory_handler(self.memory_handler)
        self.patrol_system.set_tool_invoker(self.tool_invoker)
    
    def start(self):
        """启动调度器"""
        self.running = True
        for i in range(self.thread_count):
            t = threading.Thread(target=self._worker, args=(i,))
            self.worker_threads.append(t)
            t.start()
            log_agent_action("启动工作线程", "system", f"线程{i}已启动")
        
        # 自动启动巡查系统
        self.patrol_system.start_patrol()
    
    def stop(self):
        """停止调度器"""
        self.running = False
        for t in self.worker_threads:
            t.join()
        self.patrol_system.stop_patrol()
        log_agent_action("停止调度器", "system", "所有工作线程已停止")
    
    def submit_task(self, task: Task):
        """提交任务"""
        self.task_queue.put((task.priority, task))
        log_agent_action("提交任务", task.user_id, 
                        f"任务ID：{task.task_id} | 优先级：{task.priority} | 队列长度：{self.task_queue.qsize()}")
    
    def _worker(self, thread_id: int):
        """工作线程：处理任务（核心修改：使用回复生成器）"""
        while self.running:
            try:
                if not self.task_queue.empty():
                    priority, task = self.task_queue.get(timeout=1)
                    task.status = "running"
                    log_agent_action("执行任务", task.user_id, 
                                    f"线程{thread_id} | 优先级：{priority} | 任务ID：{task.task_id}")
                    
                    # 处理任务
                    result = InstructionProcessor.handle_instruction(
                        task, self.sub_agent_mgr, self.context_mgr, self.memory_handler,
                        self.tool_invoker, self.patrol_system, self.reply_generator  # 传入回复生成器
                    )
                    
                    # 使用回复生成器处理最终回复
                    final_reply = self.reply_generator.generate_reply(
                        user_id=task.user_id,
                        content=result["message"],
                        context=self.context_mgr.get_state(task.user_id)
                    )
                    
                    # 记录到上下文
                    self.context_mgr.add_message(task.user_id, "agent", final_reply)
                    
                    task.status = "done" if result["success"] else "failed"
                    log_agent_action("完成任务", task.user_id, 
                                    f"线程{thread_id} | 任务ID：{task.task_id} | 成功：{result['success']}")
                else:
                    time.sleep(0.1)
            except queue.Empty:
                continue
            except Exception as e:
                # 使用错误模板生成回复
                error_reply = self.reply_generator.get_template("error", error=str(e))
                error_reply = self.reply_generator.generate_reply("system", error_reply)
                log_agent_action("任务执行异常", "system", f"线程{thread_id}：{error_reply}")

# ===================== 指令处理器（核心修改：集成回复生成器） =====================
class InstructionProcessor:
    """指令处理器：支持回复生成器"""
    @classmethod
    def handle_instruction(cls, task: Task, sub_agent_mgr: SubAgentManager, 
                          context_mgr: ContextManager, memory_handler: MemoryHandler,
                          tool_invoker: ToolInvoker, patrol_system: PatrolSystem,
                          reply_generator: ReplyGenerator) -> dict:
        """处理指令主逻辑（新增回复生成器参数）"""
        content = task.content.strip()
        user_id = task.user_id
        
        try:
            # ========== 0. 回复风格配置指令（新增） ==========
            if "设置回复风格" in content:
                style_match = re.search(r"设置回复风格 (\w+)", content)
                if style_match:
                    style = style_match.group(1)
                    success = reply_generator.set_style(style)
                    if success:
                        message = f"已为您将回复风格设置为{style}风格✅～"
                    else:
                        message = f"抱歉😥，不支持的回复风格：{style}，支持的风格有：管家/简洁/详细～"
                    return {"success": True, "message": message}
            
            elif "设置回复长度" in content:
                len_match = re.search(r"设置回复长度 (\d+)", content)
                if len_match:
                    max_len = int(len_match.group(1))
                    success = reply_generator.set_max_length(max_len)
                    if success:
                        message = f"已为您将最大回复长度设置为{max_len}字符✅～"
                    else:
                        message = f"抱歉😥，回复长度必须为正整数～"
                    return {"success": True, "message": message}
            
            # ========== 1. 子Agent相关指令（使用模板） ==========
            elif "创建" in content and "子agent" in content:
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
                
                # 使用模板生成回复
                stats = sub_agent_mgr.get_stats()
                message = reply_generator.get_template(
                    "agent_create",
                    count=success_count,
                    total=stats["total"]
                )
                return {"success": True, "message": message}
            
            elif "销毁" in content and "子agent" in content:
                if "所有" in content:
                    destroy_count = sub_agent_mgr.destroy_all_agents()
                    memory_handler.save_long_term_memory(
                        user_id=user_id,
                        content=f"销毁了{destroy_count}个子Agent",
                        tags=["子Agent", "销毁"],
                        priority=3
                    )
                    context_mgr.set_state(user_id, "last_destroy_count", destroy_count)
                    
                    # 使用模板
                    stats = sub_agent_mgr.get_stats()
                    message = reply_generator.get_template(
                        "agent_destroy",
                        count=destroy_count,
                        total=stats["total"]
                    )
                    return {"success": True, "message": message}
                else:
                    stats = sub_agent_mgr.get_stats()
                    if stats["total"] > 0:
                        first_agent_id = stats["agents"][0]
                        sub_agent_mgr.destroy_agent(first_agent_id)
                        stats = sub_agent_mgr.get_stats()
                        message = reply_generator.get_template(
                            "agent_destroy",
                            count=1,
                            total=stats["total"]
                        )
                        return {"success": True, "message": message}
                    else:
                        message = "抱歉😥，当前无可用子Agent可销毁～"
                        return {"success": False, "message": message}
            
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
                memory_handler.save_long_term_memory(
                    user_id=user_id,
                    content=f"拆分{len(tasks)}个任务，成功执行{success_tasks}个",
                    tags=["任务拆分", "子Agent"],
                    priority=3
                )
                message = f"已为您拆分{len(tasks)}个任务，成功执行{success_tasks}个，失败{len(tasks)-success_tasks}个～"
                return {"success": True, "message": message}
            
            elif "查看子agent" in content:
                stats = sub_agent_mgr.get_stats()
                message = f"当前子Agent统计信息：总数{stats['total']}/{stats['max']}，ID列表：{stats['agents']}～"
                return {"success": True, "message": message}
            
            # ========== 2. 上下文相关指令 ==========
            elif "查看历史" in content:
                limit = 5
                if "条" in content:
                    limit_match = re.search(r"(\d+)条", content)
                    if limit_match:
                        limit = int(limit_match.group(1))
                history = context_mgr.get_history(user_id, limit)
                history_str = "\n".join([f"[{h['timestamp']}] {h['role']}：{h['content']}" for h in history])
                message = f"最近{limit}条对话历史：\n{history_str}"
                return {"success": True, "message": message}
            
            elif "清空上下文" in content:
                context_mgr.clear_context(user_id)
                message = "已为您清空所有会话上下文和历史记录✅～"
                return {"success": True, "message": message}
            
            elif "导出上下文" in content:
                context_json = context_mgr.export_context(user_id)
                message = f"已为您导出上下文，内容：\n{context_json}"
                return {"success": True, "message": message}
            
            # ========== 3. 记忆相关指令（使用模板） ==========
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
                
                # 使用模板
                message = reply_generator.get_template(
                    "memory_save",
                    type="短时",
                    content=mem_content[:20] + "..." if len(mem_content) > 20 else mem_content
                )
                return {"success": result["success"], "message": message}
            
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
                
                # 使用模板
                message = reply_generator.get_template(
                    "memory_save",
                    type="长时",
                    content=mem_content[:20] + "..." if len(mem_content) > 20 else mem_content
                )
                return {"success": result["success"], "message": message}
            
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
                
                return {"success": result["success"], "message": result_str}
            
            elif "批量保存记忆" in content:
                try:
                    mem_list_str = re.search(r"\[(.*)\]", content, re.DOTALL).group(1)
                    mem_list = json.loads(f"[{mem_list_str}]")
                    result = memory_handler.batch_save_memory(user_id, mem_list)
                    message = f"已为您批量保存记忆，成功{result['success_count']}/{result['total']}条✅～"
                    return {"success": result["success"], "message": message}
                except Exception as e:
                    message = reply_generator.get_template("error", error=str(e))
                    return {"success": False, "message": message}
            
            elif "导出记忆" in content:
                result = memory_handler.export_memory(user_id)
                message = f"已为您导出记忆到：{result.get('export_path', '')}✅～"
                return {"success": result["success"], "message": message}
            
            # ========== 4. 工具调用指令 ==========
            elif "调用工具" in content:
                tool_match = re.search(r"调用工具 (\w+) (.*)", content)
                if tool_match:
                    tool_name = tool_match.group(1)
                    params_str = tool_match.group(2)
                    params = {}
                    for param in params_str.split():
                        if "=" in param:
                            k, v = param.split("=", 1)
                            params[k] = v
                    result = tool_invoker.invoke_tool(user_id, tool_name, **params)
                    message = f"工具调用{'成功' if result['success'] else '失败'}：{result.get('result', result.get('error', ''))}～"
                    return {"success": result["success"], "message": message}
                else:
                    message = "格式错误😥，示例：调用工具 weatherapi city=北京～"
                    return {"success": False, "message": message}
            
            # ========== 5. 巡查系统指令（使用模板） ==========
            elif "启动巡查" in content:
                result = patrol_system.start_patrol(user_id)
                if result["success"]:
                    message = reply_generator.get_template(
                        "patrol_start",
                        interval=patrol_system.patrol_interval
                    )
                else:
                    message = reply_generator.get_template("error", error=result["error"])
                return {"success": result["success"], "message": message}
            
            elif "停止巡查" in content:
                result = patrol_system.stop_patrol()
                if result["success"]:
                    message = reply_generator.get_template("patrol_stop")
                else:
                    message = reply_generator.get_template("error", error="停止巡查失败")
                return {"success": result["success"], "message": message}
            
            elif "手动巡查" in content:
                report = patrol_system.manual_patrol(user_id)
                exceptions_str = "\n".join([f"- [{exc['level']}] {exc['msg']}" for exc in report["exceptions"]])
                fixes_str = "\n".join([f"- {fix}" for fix in report["fix_actions"]])
                report_str = f"""
巡查报告（{report['type']}）
时间：{report['patrol_time']}
检查项：{[f"{item['name']}（{item['status']}）" for item in report['check_items']]}
异常数：{len(report['exceptions'])}
{exceptions_str if exceptions_str else '- 无异常'}
自动修复：{len(report['fix_actions'])}
{fixes_str if fixes_str else '- 无修复动作'}
                """.strip()
                return {"success": True, "message": report_str}
            
            elif "查看巡查报告" in content:
                limit_match = re.search(r"最近(\d+)次", content)
                last_n = int(limit_match.group(1)) if limit_match else 5
                report = patrol_system.get_patrol_report(last_n=last_n)
                reports_str = "\n\n".join([
                    f"【巡查时间：{r['patrol_time']}】\n异常数：{len(r['exceptions'])} | 修复数：{len(r['fix_actions'])}"
                    for r in report["reports"]
                ])
                message = f"最近{last_n}次巡查报告（总计{report['total']}次）：\n{reports_str}"
                return {"success": True, "message": message}
            
            # ========== 6. 通用指令 ==========
            elif "你好" in content or "您好" in content:
                message = reply_generator.get_template("greeting")
                return {"success": True, "message": message}
            
            elif "完成" in content or "结束" in content:
                message = reply_generator.get_template("finish")
                return {"success": True, "message": message}
            
            else:
                memory_handler.save_short_term_memory(
                    user_id=user_id,
                    content=f"通用指令：{content}",
                    tags=["通用指令"]
                )
                message = f"已为您处理指令：{content}"
                return {"success": True, "message": message}
        
        except Exception as e:
            log_agent_action("指令处理失败", user_id, f"错误：{str(e)}")
            message = reply_generator.get_template("error", error=str(e))
            return {"success": False, "message": message}

# ===================== 主Agent类（集成回复生成器） =====================
class MainAgent:
    """主Agent：整合所有模块"""
    def __init__(self, reply_style="管家", reply_max_length=500):
        # 核心模块初始化
        self.sub_agent_mgr = SubAgentManager(max_agents=30)
        self.context_mgr = ContextManager(max_history_len=50)
        self.memory_handler = MemoryHandler(data_dir="./data")
        self.tool_invoker = ToolInvoker()
        self.patrol_system = PatrolSystem(patrol_interval=60)
        self.reply_generator = ReplyGenerator(style=reply_style, max_length=reply_max_length)  # 初始化生成器
        self.task_scheduler = TaskScheduler(thread_count=5)
        
        # 依赖注入
        self.patrol_system.set_sub_agent_manager(self.sub_agent_mgr)
        self.patrol_system.set_memory_handler(self.memory_handler)
        self.patrol_system.set_tool_invoker(self.tool_invoker)
        self.task_scheduler.reply_generator = self.reply_generator  # 同步生成器
    
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
        print(f"回复模块：当前风格={self.reply_generator.style} | 最大长度={self.reply_generator.max_length}字符")
        print("--------------------------")
        log_agent_action("启动Agent交互", "system", 
                        "进入对话模式，输入'exit'退出 | 支持优先级：critical/high/normal/low")
    
    def stop(self):
        """停止主Agent"""
        self.task_scheduler.stop()
        self.sub_agent_mgr.destroy_all_agents()
        self.patrol_system.stop_patrol()
        log_agent_action("停止主Agent", "system", "所有模块已停止，资源已清理")
    
    def send_message(self, user_id: str, message: str, priority: int = 2):
        """发送消息"""
        self.context_mgr.add_message(user_id, "user", message)
        
        task_id = f"task_{time.strftime('%Y%m%d%H%M%S')}_{user_id}_{uuid.uuid4().hex[:3]}"
        task = Task(task_id, user_id, message, priority)
        self.task_scheduler.submit_task(task)
        
        queue_size = self.task_scheduler.task_queue.qsize()
        print(f"Agent：任务已提交（ID：{task_id} | 优先级：{priority} | 队列长度：{queue_size}）")
        return task_id

# ===================== 交互入口 =====================
if __name__ == "__main__":
    if not PSUTIL_AVAILABLE:
        print("\n【重要提示】请安装psutil以启用系统资源巡查：pip install psutil\n")
    
    # 初始化并启动Agent（可指定回复风格）
    agent = MainAgent(reply_style="管家", reply_max_length=500)
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