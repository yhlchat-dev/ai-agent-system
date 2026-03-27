#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
修正版 MainAgent：整合完整版 SubAgent + 修复初始化问题
"""
import time
import uuid
import queue
from queue import Queue
from threading import Lock

# 导入核心依赖
from sub_agent.sub_agent import SubAgent  # 导入完整版SubAgent
from core.agent.utils import log_agent_action, clean_text
from core.agent.reply_generator import ReplyGenerator  # 回复生成器
from core.agent.task_scheduler import TaskScheduler, Task  # 任务调度
from core.agent.memory_handler import MemoryHandler  # 记忆模块
from core.agent.sub_agent_manager import SubAgentManager  # 兼容旧管理器（可选）
from core.agent.patrol_system import PatrolSystem  # 巡查系统
from core.agent.tool_invoker import ToolInvoker  # 工具调用器
from core.agent.context_manager import ContextManager  # 上下文管理器

class MainAgent:
    """主Agent：整合完整版SubAgent + 所有核心模块"""
    def __init__(self, reply_style="管家", reply_max_length=500):
        # ========== 1. 先初始化基础依赖（避免顺序错误） ==========
        self.data_dir = "./data"
        self.user_id = "default_user"
        
        # 核心模块初始化（按依赖顺序）
        self.context_mgr = ContextManager(max_history_len=50)  # 上下文
        self.memory_handler = MemoryHandler(data_dir=self.data_dir)  # 记忆模块
        self.tool_invoker = ToolInvoker(data_dir=self.data_dir)  # 工具调用器
        self.sub_agent_mgr = SubAgentManager(max_agents=30)  # 兼容旧管理器（可选保留）
        self.patrol_system = PatrolSystem(patrol_interval=60)  # 巡查系统
        self.reply_generator = ReplyGenerator(style=reply_style, max_length=reply_max_length)  # 回复生成器
        
        # ========== 2. 初始化完整版SubAgent的核心依赖 ==========
        self.supervisor_queue = Queue()  # 子Agent汇报队列（线程安全）
        self.tool_manager = self._init_tool_manager()  # 对齐SubAgent的工具管理器
        self.long_term_memory = self.memory_handler  # 现在memory_handler已初始化，不会报错
        
        # ========== 3. 任务调度器初始化 ==========
        self.task_scheduler = TaskScheduler(thread_count=5)
        # 巡查系统依赖注入
        self.patrol_system.set_sub_agent_manager(self.sub_agent_mgr)
        self.patrol_system.set_memory_handler(self.memory_handler)
        self.patrol_system.set_tool_invoker(self.tool_invoker)
        self.task_scheduler.reply_generator = self.reply_generator  # 同步回复生成器
    
    def _init_tool_manager(self):
        """初始化工具管理器（对齐完整版SubAgent的调用逻辑）"""
        class IntegratedToolManager:
            def __init__(self, tool_invoker):
                self.tool_invoker = tool_invoker  # 关联主系统的ToolInvoker
            
            def call_tool(self, tool_name, **kwargs):
                """适配SubAgent的调用格式，转发到主系统的ToolInvoker"""
                user_id = kwargs.get("user_id", "default_user")
                # 调用主系统的工具，并返回统一格式
                result = self.tool_invoker.invoke_tool(user_id, tool_name, **kwargs)
                if result["success"]:
                    return result["result"]
                else:
                    return f"工具调用失败：{result['error']}"
        
        # 传入主系统的ToolInvoker，实现工具逻辑统一
        return IntegratedToolManager(self.tool_invoker)
    
    def create_full_sub_agent(self, user_id, permissions=None):
        """创建带权限控制的完整版子Agent（核心方法）"""
        # 默认权限配置（可根据需求调整）
        default_permissions = {
            "allow_llm": True,       # 允许调用大模型
            "allow_network": True,   # 允许联网
            "allow_communication": True,  # 允许和主Agent通信
            "allow_memory_access": True    # 允许访问记忆库
        }
        permissions = permissions or default_permissions
        
        try:
            # 创建完整版SubAgent实例
            sub_agent = SubAgent(
                supervisor_queue=self.supervisor_queue,
                tool_manager=self.tool_manager,
                long_term_memory=self.long_term_memory,
                user_id=user_id,
                permissions=permissions
            )
            log_agent_action("创建完整版子Agent", user_id, f"ID：{sub_agent.agent_id} | 权限：{permissions}")
            # 记录到记忆模块
            self.memory_handler.save_short_term_memory(
                user_id=user_id,
                content=f"创建子Agent {sub_agent.agent_id}，权限：{permissions}",
                tags=["子Agent", "创建", "完整版"]
            )
            return sub_agent
        except RuntimeError as e:
            # 使用回复生成器的错误模板
            error_msg = self.reply_generator.get_template("error", error=str(e))
            log_agent_action("创建子Agent失败", user_id, error_msg)
            # 记录失败日志到记忆
            self.memory_handler.save_short_term_memory(
                user_id=user_id,
                content=f"创建子Agent失败：{str(e)}",
                tags=["子Agent", "创建失败"]
            )
            return None
    
    def run_sub_agent_task(self, sub_agent, task_desc):
        """执行子Agent任务（完善异常处理）"""
        if not sub_agent:
            error_msg = self.reply_generator.generate_reply(sub_agent.user_id if sub_agent else "system", 
                                                           "子Agent创建失败，无法执行任务～")
            return {"success": False, "message": error_msg}
        
        try:
            # 生成唯一任务ID
            task_id = str(uuid.uuid4().hex[:6])
            # 执行子Agent任务（自动销毁）
            sub_agent.execute({"description": task_desc, "task_id": task_id})
            
            # 获取子Agent的汇报结果（处理超时）
            try:
                report = self.supervisor_queue.get(timeout=10)  # 超时时间延长到10秒
            except queue.Empty:
                raise TimeoutError(f"子Agent {sub_agent.agent_id} 执行超时（10秒）")
            
            # 使用回复生成器处理最终回复
            content = f"子Agent {sub_agent.agent_id} 执行任务完成：{report['result']}"
            final_reply = self.reply_generator.generate_reply(
                user_id=sub_agent.user_id,
                content=content,
                context=self.context_mgr.get_state(sub_agent.user_id)
            )
            
            # 记录任务结果到记忆
            self.memory_handler.save_short_term_memory(
                user_id=sub_agent.user_id,
                content=f"子Agent {sub_agent.agent_id} 执行任务：{task_desc}，结果：{report['result']}",
                tags=["子Agent", "任务执行", report['status']]
            )
            
            return {"success": True, "message": final_reply}
        
        except TimeoutError as e:
            error_msg = self.reply_generator.get_template("error", error=str(e))
            log_agent_action("子Agent任务超时", sub_agent.user_id, error_msg)
            return {"success": False, "message": error_msg}
        except Exception as e:
            error_msg = self.reply_generator.get_template("error", error=str(e))
            log_agent_action("子Agent任务执行失败", sub_agent.user_id, error_msg)
            # 记录失败结果到记忆
            self.memory_handler.save_short_term_memory(
                user_id=sub_agent.user_id,
                content=f"子Agent {sub_agent.agent_id} 执行任务失败：{task_desc}，错误：{str(e)}",
                tags=["子Agent", "任务执行", "失败"]
            )
            return {"success": False, "message": error_msg}
    
    # ========== 保留原有核心方法 ==========
    def start(self):
        """启动主Agent"""
        self.task_scheduler.start()
        log_agent_action("初始化主Agent", "system", 
                        f"调度系统启动 | 工作线程数：5 | 子Agent最大数量：30")
        print("== Agent 1.0 启动成功（整合完整版SubAgent）==")
        print(f"回复模块：当前风格={self.reply_generator.style} | 最大长度={self.reply_generator.max_length}字符")
        print(f"子Agent模块：支持权限控制（LLM/联网/记忆访问）+ 自动销毁 + 配置驱动")
        print("--------------------------")
    
    def stop(self):
        """停止主Agent"""
        self.task_scheduler.stop()
        # 强制销毁所有完整版子Agent
        SubAgent.force_destroy_all()
        # 销毁旧版子Agent（可选）
        self.sub_agent_mgr.destroy_all_agents()
        self.patrol_system.stop_patrol()
        log_agent_action("停止主Agent", "system", "所有模块已停止，子Agent已全部销毁")
    
    def send_message(self, user_id: str, message: str, priority: int = 2):
        """发送消息（兼容原有交互逻辑）"""
        self.context_mgr.add_message(user_id, "user", message)
        
        task_id = f"task_{time.strftime('%Y%m%d%H%M%S')}_{user_id}_{uuid.uuid4().hex[:3]}"
        task = Task(task_id, user_id, message, priority)
        self.task_scheduler.submit_task(task)
        
        queue_size = self.task_scheduler.task_queue.qsize()
        print(f"Agent：任务已提交（ID：{task_id} | 优先级：{priority} | 队列长度：{queue_size}）")
        return task_id