#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Agent 1.0 生产级最终版
集成：专业版SubAgentManager + 会话上下文管理 + 任务调度 + 多线程巡查
"""
import time
import queue
import uuid
import json
import threading
from datetime import datetime
from typing import Dict, Optional, Any

# ===================== 缺失依赖补充（必须） =====================
def clean_text(text: str) -> str:
    """清理文本（去除多余空格、换行）"""
    import re
    # 去除多余空格、换行、制表符
    text = re.sub(r'\s+', ' ', text).strip()
    # 去除特殊字符（可选，根据业务调整）
    text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9，。！？：；""''()（）【】]', '', text)
    return text

def log_agent_action(action: str, user_id: str, detail: str = ""):
    """打印Agent操作日志（带时间戳）"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    print(f"[{timestamp}] [{user_id}] {action}：{detail}")

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

# ===================== 你提供的ContextManager（完整保留） =====================
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
        # 清理文本（使用补充的clean_text函数）
        content = clean_text(content)
        # 添加新消息
        context["history"].append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        # 截断历史记录（防止过长）
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
        self.context_mgr = ContextManager(max_history_len=50)  # 集成上下文管理器
    
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
                    
                    # 处理任务并记录上下文
                    result = InstructionProcessor.handle_instruction(
                        task, self.sub_agent_mgr, self.context_mgr
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

# ===================== 指令处理器（集成上下文） =====================
class InstructionProcessor:
    """指令处理器：支持上下文管理"""
    @classmethod
    def handle_instruction(cls, task: Task, sub_agent_mgr: SubAgentManager, context_mgr: ContextManager) -> dict:
        """处理指令主逻辑"""
        content = task.content.strip()
        user_id = task.user_id
        
        try:
            # 1. 创建子Agent
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
                
                # 记录会话状态
                context_mgr.set_state(user_id, "last_agent_count", success_count)
                return {
                    "success": True,
                    "message": f"成功创建{success_count}个子Agent（请求{num}个）"
                }
            
            # 2. 销毁子Agent
            elif "销毁" in content and "子agent" in content:
                if "所有" in content:
                    destroy_count = sub_agent_mgr.destroy_all_agents()
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
            
            # 3. 拆分任务
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
                return {
                    "success": True,
                    "message": f"拆分{len(tasks)}个任务，成功执行{success_tasks}个"
                }
            
            # 4. 上下文相关指令
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
            
            # 5. 查看子Agent统计
            elif "查看子agent" in content:
                stats = sub_agent_mgr.get_stats()
                return {
                    "success": True,
                    "message": f"子Agent统计：总数{stats['total']}/{stats['max']}，ID列表：{stats['agents']}"
                }
            
            # 6. 通用指令
            else:
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
    """主Agent：整合子Agent管理+上下文+调度"""
    def __init__(self):
        # 核心模块初始化
        self.sub_agent_mgr = SubAgentManager(max_agents=30)
        self.context_mgr = ContextManager(max_history_len=50)
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
        print(f"巡查模块：后台静默运行（异常主动汇报）")
        print(f"上下文模块：最大历史记录数50条，支持状态维护/导出")
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
                self.sub_agent_mgr._cleanup_idle_agents()
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