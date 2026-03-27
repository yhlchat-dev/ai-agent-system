#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Task Engine: Process user input, identify intent, split subtasks, integrate patrol and capsule retrieval.
Supports direct dispatch of instant messaging commands (currently only Feishu).

Core Function Modules:
1. Custom storage management (save/search category data)
2. Basic tool command processing (process/window/screenshot/weather/feishu)
3. Sensitive information detection and memory saving
4. User preference extraction and learning
5. Patrol and capsule retrieval integration
6. Intent matching and subtask scheduling
"""

import json
import time
import re
import os
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple, Union

try:
    import jieba.posseg as pseg
except ImportError:
    pseg = None

from core.memory.long_term_memory import LongTermMemory
from core.memory.short_term_memory import ShortTermMemory
from core.cognition.curiosity_core import CuriosityCore
from core.task.task_scheduler import TaskScheduler
from core.cognition.patrol_manager import PatrolManager
from core.user.user_data import UserData
from utils.tool_manager import ToolManager
from utils.sensitive_detector import detect_sensitive
from infra.config import DATA_DIR

LOG_LEVEL = logging.INFO
LOG_FORMAT = "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s"

CUSTOM_STORAGE_LIMIT = 5
CUSTOM_STORAGE_BASE_DIR = "custom_storage"
CONTENT_MAX_LENGTH = 2000

SENSITIVE_AUTO_SAVE_LEVELS = ["low"]
SENSITIVE_CONFIRM_LEVELS = ["medium", "high"]

INTENT_MATCH_MIN_SCORE = 1
PREDEFINED_INTENTS = {
    "organize_news": {
        "keywords": ["news", "information", "report"],
        "subtasks": [
            {"func": "_task_news_fetch", "args": ["keywords"]},
            {"func": "_task_ai_summarize", "args": ["${previous_result}"]},
            {"func": "_task_generate_file", "args": ["${previous_result}", "news_brief.txt"]}
        ]
    },
    "summarize_info": {
        "keywords": ["summarize", "summary", "abstract"],
        "subtasks": [
            {"func": "_task_ai_summarize", "args": ["${user_input}"]}
        ]
    },
    "write_script": {
        "keywords": ["write script", "generate code", "write program"],
        "subtasks": []
    },
    "search_info": {
        "keywords": ["search", "lookup", "find"],
        "subtasks": []
    }
}

SAVE_PATTERNS = [
    r"save\s*(?:screenshot|process|list|data)?\s*(?:to|into)?\s*\[([^\]]+)\]",
    r"save to\s*\[([^\]]+)\]",
    r"archive to\s*\[([^\]]+)\]"
]

SEARCH_PATTERNS = [
    r"(?:find|search|query|show|list)\s*(?:.*?)(?:category|record|data|screenshot|process)?\s*(?:to|in|belongs)?\s*\[([^\]]+)\]",
    r"(?:find|search|query)\s+(?:[\"\'']?([^\"\'\n]+?)[\"\'']?\s+)?category\s*[:：]\s*([^\s\n]+)",
    r"(?:find|search|query)\s+[\"\'']?([^\"\'\n]+?)[\"\'']?\s*$",
    r"list all(?:storage|categories)"
]

PREFERENCE_PATTERNS = [
    (r'I like (.*)', 1),
    (r'I love (.*)', 1),
    (r'my favorite is (.*)', 1),
    (r'I (?:usually )?like (.*)', 1),
    (r'(.*) is my favorite', 0),
    (r'I (?:everyday | often)(.*)', 1),
]

GREETINGS = ['hello', 'hi', 'hey', 'greetings']
WEATHER_KEYWORDS = ["weather", "temperature", "forecast"]
COMMON_CITIES = [
    "Beijing", "Shanghai", "Guangzhou", "Shenzhen", "Hangzhou", "Nanjing", 
    "Chengdu", "Chongqing", "Wuhan", "Xi'an", "Suzhou", "Tianjin", 
    "Changsha", "Zhengzhou", "Qingdao", "Xiamen", "Ningbo", "Wuxi"
]

logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
logger = logging.getLogger("TaskEngine")

def _task_news_fetch(keywords: str) -> str:
    """Built-in task: fetch news"""
    logger.info(f"Executing news fetch task, keywords: {keywords}")
    return f"Fetched news about {keywords}"

def _task_ai_summarize(text: str) -> str:
    """Built-in task: AI summarize text"""
    logger.info(f"Executing AI summarize task, text length: {len(text[:30])}")
    return f"Summary: {text}"

def _task_generate_file(content: str, filename: str) -> str:
    """Built-in task: generate file"""
    logger.info(f"Executing file generation task, filename: {filename}")
    return f"File {filename} has been generated"

class TaskEngine:
    """
    Task Engine Core Class
    
    Main Responsibilities:
    1. Parse user input, match corresponding processing logic
    2. Integrate modules (memory, patrol, capsule, scheduler)
    3. Process various commands and return structured results
    """
    
    def __init__(self, tool_manager: ToolManager, user_id: str = 'default', data_dir: Optional[Path] = None) -> None:
        """
        Initialize Task Engine
        
        :param tool_manager: Tool manager instance
        :param user_id: Default user ID
        :param data_dir: Data storage directory
        """
        self.tm = tool_manager
        self.current_user = self._validate_user_id(user_id)
        self.data_dir = self._init_data_dir(data_dir)
        
        self.ltm = self._init_module(LongTermMemory, user_id=self.current_user)
        self.stm = self._init_module(ShortTermMemory, user_id=self.current_user)
        self.curiosity = self._init_module(CuriosityCore, data_dir=self.data_dir)
        self.scheduler = self._init_module(
            TaskScheduler, logger=None, start_scheduler=False
        )
        self.patrol_manager = self._init_module(
            PatrolManager, self.tm, user_id=self.current_user
        )
        self.ud = self._init_module(UserData, user_id=self.current_user)
        
        self.intent_map = PREDEFINED_INTENTS
        
        logger.info(f"TaskEngine initialized - user ID: {self.current_user}, data directory: {self.data_dir}")

    def _validate_user_id(self, user_id: str) -> str:
        """Validate and normalize user ID"""
        if not isinstance(user_id, str) or not user_id.strip():
            logger.warning(f"Invalid user ID, using default: {user_id}")
            return "default"
        return user_id.strip()

    def _init_data_dir(self, data_dir: Optional[Path]) -> Path:
        """Initialize data directory"""
        if data_dir is None:
            data_dir = DATA_DIR
        data_dir = Path(data_dir)
        data_dir.mkdir(exist_ok=True, parents=True)
        return data_dir

    def _init_module(self, module_class: Any, *args, **kwargs) -> Optional[Any]:
        """Safely initialize module (with fault tolerance)"""
        try:
            if module_class:
                instance = module_class(*args, **kwargs)
                logger.debug(f"Module initialized successfully: {module_class.__name__}")
                return instance
        except Exception as e:
            logger.error(f"Module initialization failed: {module_class.__name__} - {e}", exc_info=True)
        return None

    def _get_context(self, user_id: str) -> Dict[str, Any]:
        """Get user context (recent conversations + preferences)"""
        context = {"recent_chats": [], "preferences": []}
        
        if self.stm:
            try:
                recent = self.stm.get_recent_logs(limit=5)
                context["recent_chats"] = recent if isinstance(recent, list) else []
            except Exception as e:
                logger.error(f"Failed to get recent conversations - {e}", exc_info=True)
        
        if self.ltm:
            try:
                prefs = self.ltm.search_memory(user_id, query="habit", top_k=3)
                context["preferences"] = prefs if isinstance(prefs, list) else []
            except Exception as e:
                logger.error(f"Failed to get user preferences - {e}", exc_info=True)
        
        return context

    def _match_intent(self, user_input: str) -> tuple[Optional[str], int]:
        """Match intent based on keywords"""
        if not isinstance(user_input, str):
            return None, 0
        
        max_score = 0
        matched_intent = None
        
        for intent, config in self.intent_map.items():
            intent_score = 0
            for kw in config.get("keywords", []):
                if kw in user_input.lower():
                    intent_score += user_input.lower().count(kw)
            
            if intent_score > max_score:
                max_score = intent_score
                matched_intent = intent
        
        return matched_intent, max_score

    def _extract_preference(self, user_input: str) -> Optional[str]:
        """Extract stable preference expressions from user input"""
        if not isinstance(user_input, str) or not pseg:
            return None
        
        for pattern, group_idx in PREFERENCE_PATTERNS:
            match = re.search(pattern, user_input, re.IGNORECASE)
            if match:
                phrase = match.group(group_idx).strip()
                if not phrase:
                    continue
                
                try:
                    words = [
                        word for word, flag in pseg.cut(phrase) 
                        if (flag.startswith('n') or flag.startswith('v')) and len(word) > 1
                    ]
                    if words:
                        logger.info(f"Extracted user preference: {phrase}")
                        return phrase
                except Exception as e:
                    logger.error(f"Preference word segmentation failed - {e}", exc_info=True)
        
        return None

    def _handle_save_command(self, user_input: str) -> Optional[Dict[str, Any]]:
        """Handle save command"""
        for pattern in SAVE_PATTERNS:
            match = re.search(pattern, user_input, re.IGNORECASE)
            if match:
                category = match.group(1).strip()
                if not category:
                    return self._create_error_result("Category name cannot be empty")
                
                return self._execute_save_operation(user_input, category)
        
        return None

    def _execute_save_operation(self, user_input: str, category: str) -> Dict[str, Any]:
        """Execute save operation"""
        content_to_save = None
        attachment_path = None
        
        if "screenshot" in user_input.lower() or ("save" in user_input.lower() and "image" in user_input.lower()):
            logger.info(f"Executing screenshot save - category: {category}")
            snap_res = self.tm.call_tool("take_screenshot")
            if not snap_res.get("success"):
                return self._create_error_result(f"Screenshot failed: {snap_res.get('error', 'unknown error')}")
            
            attachment_path = snap_res["result"]
            content_to_save = f"User manually saved screenshot, category: {category}"
        
        elif "process" in user_input.lower():
            logger.info(f"Executing process list save - category: {category}")
            proc_res = self.tm.call_tool("list_processes")
            if not proc_res.get("success"):
                return self._create_error_result(f"Failed to get processes: {proc_res.get('error', 'unknown error')}")
            
            data = proc_res.get("result", {})
            if isinstance(data, dict) and 'result' in data:
                data = data['result']
            
            content_to_save = json.dumps(
                data, ensure_ascii=False, indent=2
            )[:CONTENT_MAX_LENGTH]
        
        else:
            content_match = re.search(r"content[:：]\s*(.+)", user_input)
            if content_match:
                content_to_save = content_match.group(1).strip()
            else:
                content_to_save = re.sub("|".join(SAVE_PATTERNS), "", user_input, flags=re.IGNORECASE).strip()
                if not content_to_save:
                    content_to_save = f"User custom storage to [{category}]"
        
        return self._save_to_custom_storage(category, content_to_save, attachment_path)

    def _save_to_custom_storage(self, category: str, content: str, attachment: Optional[str] = None) -> Dict[str, Any]:
        """Save data to custom storage"""
        if "save_custom_data" not in self.tm.tools:
            return self._create_error_result("Save function not enabled, please check tool manager")
        
        tags = [category, "custom_save", datetime.now().strftime("%Y-%m-%d")]
        save_params = {
            "category": category,
            "content": content,
            "tags": tags
        }
        
        if attachment:
            save_params["attachment"] = attachment
        
        try:
            result = self.tm.call_tool("save_custom_data", **save_params)
            if result.get("success"):
                msg = f"Data successfully stored permanently to **[{category}]** category!\nTags: {', '.join(tags)}"
                if attachment:
                    msg += "\nAttachment moved to permanent directory."
                return self._create_success_result(msg)
            else:
                return self._create_error_result(f"Storage failed: {result.get('error', 'unknown error')}")
        
        except Exception as e:
            logger.error(f"Failed to save to custom storage - {e}", exc_info=True)
            return self._create_error_result(f"Save exception: {str(e)}")

    def _handle_search_command(self, user_input: str) -> Optional[Dict[str, Any]]:
        """Handle search command"""
        if re.search(r"list all(?:storage|categories)", user_input, re.IGNORECASE):
            return self._list_all_categories()
        
        for i, pattern in enumerate(SEARCH_PATTERNS[:-1]):
            match = re.search(pattern, user_input, re.IGNORECASE)
            if match:
                logger.info(f"Matched search pattern {i+1}: {pattern}")
                return self._execute_search_operation(match, i)
        
        return None

    def _list_all_categories(self) -> Dict[str, Any]:
        """List all custom storage categories"""
        if hasattr(self.tm, 'data_dir'):
            base_dir = Path(self.tm.data_dir) / CUSTOM_STORAGE_BASE_DIR
        else:
            base_dir = self.data_dir / CUSTOM_STORAGE_BASE_DIR
        
        if not base_dir.exists():
            return self._create_success_result("No custom storage categories yet.")
        
        try:
            categories = [d.name for d in base_dir.iterdir() if d.is_dir()]
            if not categories:
                return self._create_success_result("Storage directory exists but has no categories yet.")
            
            reply = "Current storage categories:\n" + "\n".join([f"  - {cat}" for cat in categories])
            reply += "\nTip: You can say 'find records in [category name]'."
            return self._create_success_result(reply)
        
        except Exception as e:
            logger.error(f"Failed to list categories - {e}", exc_info=True)
            return self._create_error_result(f"Failed to get category list: {str(e)}")

    def _execute_search_operation(self, match: re.Match, pattern_idx: int) -> Dict[str, Any]:
        """Execute search operation"""
        if "search_custom_storage" not in self.tm.tools:
            return self._create_error_result("Search function not enabled, please check tool manager")
        
        search_category = None
        search_query = None
        
        if pattern_idx == 0:
            search_category = match.group(1).strip()
        elif pattern_idx == 1:
            kw_group = match.group(1)
            search_category = match.group(2).strip()
            if kw_group and kw_group.strip():
                search_query = kw_group.strip()
        elif pattern_idx == 2:
            search_query = match.group(1).strip()
        
        try:
            tool_result = self.tm.call_tool(
                "search_custom_storage",
                category=search_category,
                query=search_query,
                limit=CUSTOM_STORAGE_LIMIT
            )
            
            return self._process_search_result(tool_result, search_category, search_query)
        
        except Exception as e:
            logger.error(f"Search operation failed - {e}", exc_info=True)
            return self._create_error_result(f"System internal error: {str(e)}\n(See backend log for details)")

    def _process_search_result(
        self, 
        tool_result: Dict[str, Any],
        category: Optional[str],
        query: Optional[str]
    ) -> Dict[str, Any]:
        """Process search result and format output"""
        if not tool_result.get("success"):
            err_msg = tool_result.get("error", "unknown error")
            logger.error(f"Search tool execution failed: {err_msg}")
            return self._create_error_result(f"Search failed: {err_msg}")
        
        raw_data = tool_result.get("result", [])
        items = self._clean_search_items(raw_data)
        total = tool_result.get("total_found", len(items))
        
        if not items:
            msg = self._build_no_result_message(category, query)
            return self._create_success_result(msg)
        
        formatted_msg = self._format_search_results(items, total)
        return self._create_success_result(formatted_msg)

    def _clean_search_items(self, raw_data: Any) -> List[Dict[str, Any]]:
        """Clean search result data"""
        items = []
        
        if isinstance(raw_data, list):
            items = raw_data
        elif isinstance(raw_data, dict):
            for key in ["items", "data", "records", "result"]:
                if key in raw_data and isinstance(raw_data[key], list):
                    items = raw_data[key]
                    break
        
        clean_items = []
        for item in items:
            if isinstance(item, dict):
                clean_items.append(item)
            elif isinstance(item, str):
                try:
                    parsed = json.loads(item)
                    if isinstance(parsed, dict):
                        clean_items.append(parsed)
                    else:
                        clean_items.append({
                            "content": item, 
                            "category": "unknown", 
                            "timestamp": datetime.now().isoformat()
                        })
                except:
                    clean_items.append({
                        "content": item, 
                        "category": "unknown", 
                        "timestamp": datetime.now().isoformat()
                    })
        
        return clean_items

    def _build_no_result_message(self, category: Optional[str], query: Optional[str]) -> str:
        """Build no result message"""
        msg = "No records found in "
        if category:
            msg += f"[{category}] "
        else:
            msg += "all categories "
        
        if query:
            msg += f"containing '{query}'."
            msg += f"\nTip: Please check if the keyword is correct."
        else:
            msg += "."
            msg += f"\nTip: This category has no data yet, try saving some content!"
        
        return msg

    def _format_search_results(self, items: List[Dict[str, Any]], total: int) -> str:
        """Format search results"""
        lines = [f"Found {total} related records, showing latest {len(items)}:", ""]
        
        for idx, item in enumerate(items, 1):
            timestamp = item.get('timestamp', datetime.now().isoformat())
            time_str = timestamp.split('T')[0] if 'T' in timestamp else (
                timestamp[:10] if len(timestamp) >= 10 else timestamp
            )
            
            cat_name = item.get('category', 'unknown')
            lines.append(f"**{idx}. [{cat_name}] ({time_str})**")
            
            if item.get('has_attachment') or item.get('attachment'):
                lines.append(f"   Type: Screenshot/File")
                att_path = item.get('attachment', '')
                fname = os.path.basename(att_path) if att_path else 'unknown file'
                lines.append(f"   File: {fname}")
                
                ocr_text = item.get('ocr_text', '')
                if ocr_text:
                    preview = ocr_text[:50] + "..." if len(ocr_text) > 50 else ocr_text
                    lines.append(f"   Recognized text: {preview}")
            else:
                content = item.get('content', item.get('content_preview', 'no content'))
                lines.append(f"   Content: {content}")
            
            tags = item.get('tags', [])
            if isinstance(tags, list):
                lines.append(f"   Tags: {', '.join(tags)}")
            elif isinstance(tags, str):
                lines.append(f"   Tags: {tags}")
            
            lines.append("")
        
        lines.append("Tip: To view original image, open the above path in local file manager.")
        return "\n".join(lines)

    def _handle_basic_commands(self, user_input: str) -> Optional[Dict[str, Any]]:
        """Handle basic tool commands"""
        if user_input.lower() == "process list":
            return self._handle_process_list()
        
        if user_input.lower() == "window list":
            return self._handle_window_list()
        
        if user_input.lower() == "screenshot":
            return self._handle_screenshot()
        
        if user_input.lower().startswith("feishu") or user_input.lower().startswith("send to feishu"):
            return self._handle_feishu_message(user_input)
        
        if any(kw in user_input.lower() for kw in WEATHER_KEYWORDS):
            return self._handle_weather_query(user_input)
        
        if any(g in user_input.lower() for g in GREETINGS):
            return self._create_success_result("Hello! How can I help you?")
        
        return None

    def _handle_process_list(self) -> Dict[str, Any]:
        """Handle process list command"""
        result = self.tm.call_tool("list_processes")
        logger.debug(f"Process list tool returned: {result}")
        
        if not result.get("success"):
            return self._create_error_result("Failed to get processes")
        
        processes = result.get("result", [])
        if isinstance(processes, dict) and 'result' in processes:
            processes = processes['result']
        
        if not isinstance(processes, list):
            return self._create_error_result(f"Process data format abnormal, type: {type(processes)}")
        
        top_processes = processes[:20]
        lines = ["Current process list (top 20):"]
        for p in top_processes:
            if isinstance(p, dict):
                lines.append(f"  {p.get('pid', 'N/A')}: {p.get('name', 'Unknown')}")
            else:
                lines.append(f"  {str(p)}")
        
        return self._create_success_result("\n".join(lines))

    def _handle_window_list(self) -> Dict[str, Any]:
        """Handle window list command"""
        result = self.tm.call_tool("list_windows")
        if result.get("success"):
            return self._create_success_result(result.get("result", "Window list retrieved successfully"))
        else:
            return self._create_error_result(f"Failed to get window list: {result.get('error', 'unknown error')}")

    def _handle_screenshot(self) -> Dict[str, Any]:
        """Handle screenshot command"""
        result = self.tm.call_tool("take_screenshot")
        if result.get("success"):
            img_path = result.get("result")
            msg = (
                f"Screenshot completed!\nTemporary path: {img_path}\n\n"
                "Note: This file is in a temporary directory and may be lost after restart.\n"
                "Suggestion: Reply 'save to [project name]' to store it permanently."
            )
            return self._create_success_result(msg, data={"image_path": img_path})
        else:
            return self._create_error_result(f"Screenshot failed: {result.get('error', 'unknown error')}")

    def _handle_feishu_message(self, user_input: str) -> Dict[str, Any]:
        """Handle Feishu message sending"""
        if user_input.lower().startswith("send to feishu"):
            message = user_input[14:].strip()
        else:
            message = user_input[6:].strip()
        
        if not message:
            return self._create_error_result("Please provide the message content to send")
        
        try:
            from interfaces.feishu import send_feishu_message
            YOUR_OPEN_ID = "ou_a8a11eb332f69f1d541abf9de4895128"
            result = send_feishu_message(YOUR_OPEN_ID, message)
            
            if result.get("success"):
                return self._create_success_result("Message sent")
            else:
                return self._create_error_result(f"Send failed: {result.get('error', 'unknown error')}")
        
        except ImportError:
            return self._create_error_result("Feishu interface not installed")
        except Exception as e:
            logger.error(f"Feishu message send failed - {e}", exc_info=True)
            return self._create_error_result(f"Send exception: {str(e)}")

    def _handle_weather_query(self, user_input: str) -> Dict[str, Any]:
        """Handle weather query"""
        city = None
        for c in COMMON_CITIES:
            if c.lower() in user_input.lower():
                city = c
                break
        
        if not city:
            match = re.search(r'weather\s+([a-zA-Z]+)', user_input, re.IGNORECASE)
            if match:
                city = match.group(1)
            else:
                city = "Beijing"
        
        result = self.tm.call_tool("weatherapi", city=city)
        if result.get("success"):
            return self._create_success_result(result.get("result", "Weather query successful"))
        else:
            return self._create_error_result(f"Weather query failed: {result.get('error', 'unknown error')}")

    def _handle_sensitive_info(self, user_input: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Handle sensitive information detection and saving"""
        if not self.ltm:
            return None
        
        sensitive_items = detect_sensitive(user_input)
        if not sensitive_items:
            return None
        
        item = sensitive_items[0]
        logger.info(f"Detected sensitive info - type: {item['type']}, content: {item['masked']}, level: {item['level']}")
        
        if self.ud and self.ud.is_auto_save(item['type']):
            self.ltm.save_habit(
                user_id,
                f"sensitive_{item['type']}",
                item['masked']
            )
            return self._create_result("auto_saved", f"Your {item['type']} information has been automatically saved.")
        
        if item['level'] in SENSITIVE_CONFIRM_LEVELS:
            self.ltm.save_pending(user_id, item)
            if item['level'] == 'high':
                msg = f"Detected {item['type']} information ({item['masked']}), this is highly sensitive. Save to long-term memory?"
            else:
                msg = f"I noticed you mentioned {item['type']} {item['masked']}, would you like me to save it?"
            
            return self._create_result("ask_confirm", msg)
        
        return None

    def _handle_preference_extraction(self, user_input: str, user_id: str) -> None:
        """Extract and save user preference"""
        if not self.ltm:
            return
        
        pref = self._extract_preference(user_input)
        if pref:
            try:
                self.ltm.add_preference_mention(user_id, pref)
            except Exception as e:
                logger.error(f"Failed to save user preference - {e}", exc_info=True)

    def _handle_pending_confirmation(self, user_input: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Handle pending sensitive information confirmation"""
        if not self.ltm:
            return None
        
        pending = self.ltm.get_pending(user_id)
        if not pending:
            return None
        
        affirm_keywords = ['yes', 'ok', 'sure', 'save', 'yeah', 'yep']
        if any(kw in user_input.lower() for kw in affirm_keywords):
            self.ltm.save_habit(
                user_id,
                f"sensitive_{pending['type']}",
                pending['masked']
            )
            if self.ud:
                count = self.ud.increment_auto_save_count(pending['type'])
                logger.info(f"Sensitive info confirmed save - type: {pending['type']}, count: {count}")
            
            self.ltm.clear_pending(user_id)
            return self._create_result("confirmed", f"Okay, saved your {pending['type']} information.")
        else:
            self.ltm.clear_pending(user_id)
        
        return None

    def _execute_patrol(self, user_input: str, user_id: str) -> Dict[str, Any]:
        """Execute patrol operation"""
        patrol_report = {}
        if self.patrol_manager:
            try:
                patrol_report = self.patrol_manager.patrol(
                    user_input, context={"user_id": user_id}
                )
                patrol_summary = patrol_report.get('summary', '')
                logger.info(f"Patrol completed - summary: {patrol_summary}")
            except Exception as e:
                logger.error(f"Patrol execution failed - {e}", exc_info=True)
        
        return patrol_report

    def _search_capsules(self, user_input: str, user_id: str) -> List[Dict[str, Any]]:
        """Search experience capsules"""
        capsules = []
        if self.tm:
            try:
                capsule_result = self.tm.call_tool(
                    "capsule_search",
                    query=user_input,
                    user_id=user_id,
                    top_k=3
                )
                if capsule_result.get("success") and capsule_result.get("result", {}).get("data"):
                    capsules = capsule_result["result"]["data"]
                    logger.info(f"Capsule search completed - found {len(capsules)} related capsules")
            except Exception as e:
                logger.error(f"Capsule search failed - {e}", exc_info=True)
        
        return capsules

    def _handle_intent_and_schedule(self, user_input: str, user_id: str, context_str: str) -> Dict[str, Any]:
        """Handle intent matching and task scheduling"""
        context_dict = self._get_context(user_id)
        
        intent, score = self._match_intent(user_input)
        logger.info(f"Intent match result - intent: {intent}, score: {score}")
        
        final_context_str = self._build_final_context(context_dict, context_str)
        
        if not intent or score < INTENT_MATCH_MIN_SCORE:
            return self._handle_curiosity_explore(user_input, final_context_str, context_dict)
        
        return self._schedule_intent_tasks(intent, user_input, user_id)

    def _build_final_context(self, context_dict: Dict[str, Any], context_str: str) -> str:
        """Build complete context string"""
        chat_context = ""
        if context_dict.get("recent_chats"):
            chat_lines = []
            for chat in context_dict["recent_chats"][-10:]:
                if isinstance(chat, dict):
                    role = chat.get('role', '')
                    content = chat.get('content', '')
                    if role and content:
                        chat_lines.append(f"{role}: {content}")
            
            if chat_lines:
                chat_context = "Recent conversations:\n" + "\n".join(chat_lines) + "\n\n"
        
        return f"{chat_context}{context_str}" if context_str else chat_context

    def _handle_curiosity_explore(self, user_input: str, context: str, context_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Call curiosity core for exploration"""
        if self.curiosity:
            try:
                full_input = f"{context}{user_input}" if context else user_input
                logger.info(f"Calling curiosity core - input length: {len(full_input)}")
                explore_result = self.curiosity.explore(full_input, context=context_dict)
                return self._create_result("explored", explore_result)
            except Exception as e:
                logger.error(f"Curiosity core call failed - {e}", exc_info=True)
                return self._create_error_result(f"Exploration failed: {str(e)}")
        else:
            if context:
                msg = f"Based on recent conversations:\n{context}\nRegarding your question '{user_input}', I don't have specific instructions yet, but I remember you discussed related topics before."
            else:
                msg = "Cannot understand command, and no curiosity module available"
            
            return self._create_result("unknown", msg)

    def _schedule_intent_tasks(self, intent: str, user_input: str, user_id: str) -> Dict[str, Any]:
        """Schedule matched intent tasks"""
        subtasks = self.intent_map[intent].get("subtasks", [])
        if not subtasks:
            return self._create_result("intent_recognized", "", {"intent": intent})
        
        if not self.scheduler:
            return self._create_error_result("Scheduler not initialized, cannot execute subtasks")
        
        job_ids = []
        for subtask in subtasks:
            job_id = self._add_subtask_to_scheduler(subtask)
            if job_id:
                job_ids.append(job_id)
        
        if self.ltm and job_ids:
            self._save_task_to_memory(user_id, user_input, intent, job_ids)
        
        msg = f"Task split into {len(job_ids)} subtasks and added to queue"
        return self._create_result(
            "scheduled", 
            msg, 
            {"intent": intent, "job_ids": job_ids}
        )

    def _add_subtask_to_scheduler(self, subtask: Dict[str, Any]) -> Optional[str]:
        """Add subtask to scheduler"""
        try:
            func_name = subtask.get("func")
            args = subtask.get("args", [])
            
            func = globals().get(func_name) if isinstance(func_name, str) else func_name
            if not func:
                logger.warning(f"Subtask function does not exist: {func_name}")
                return None
            
            resolved_args = []
            for arg in args:
                if isinstance(arg, str) and arg.startswith("${") and arg.endswith("}"):
                    resolved_args.append(arg)
                else:
                    resolved_args.append(arg)
            
            job_id = f"task_{int(time.time())}_{id(func)}"
            self.scheduler.add_job(
                func=func,
                args=tuple(resolved_args),
                job_id=job_id,
                trigger='date',
                run_date=None
            )
            
            logger.info(f"Subtask added - ID: {job_id}, function: {func_name}")
            return job_id
        
        except Exception as e:
            logger.error(f"Failed to add subtask - {e}", exc_info=True)
            return None

    def _save_task_to_memory(self, user_id: str, input_str: str, intent: str, job_ids: List[str]) -> None:
        """Save task info to long-term memory"""
        try:
            self.ltm.save_habit(
                user_id,
                "task",
                json.dumps({
                    "input": input_str,
                    "intent": intent,
                    "jobs": job_ids
                }, ensure_ascii=False)
            )
        except Exception as e:
            logger.error(f"Failed to save task to memory - {e}", exc_info=True)

    def _create_result(self, status: str, message: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create structured result"""
        result = {
            "status": status,
            "message": message
        }
        if data:
            result.update(data)
        return result

    def _create_success_result(self, message: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create success result"""
        return self._create_result("success", message, data)

    def _create_error_result(self, message: str) -> Dict[str, Any]:
        """Create error result"""
        return self._create_result("error", message)

    def process_task(
        self, 
        user_input: str, 
        user_id: Optional[str] = None, 
        context: str = ""
    ) -> Dict[str, Any]:
        """
        Process user task command (core entry point)
        
        :param user_input: User input string
        :param user_id: User ID
        :param context: Historical conversation context
        :return: Structured processing result
        """
        user_id = self._validate_user_id(user_id or self.current_user)
        user_input = str(user_input).strip() if user_input else ""
        context = str(context).strip() if context else ""
        
        logger.info(f"Starting task processing - user ID: {user_id}, input: {user_input[:50]}...")
        
        enhanced_input = self._build_enhanced_input(user_input, context)
        
        save_result = self._handle_save_command(user_input)
        if save_result:
            return save_result
        
        search_result = self._handle_search_command(user_input)
        if search_result:
            return search_result
        
        basic_result = self._handle_basic_commands(user_input)
        if basic_result:
            return basic_result
        
        pending_result = self._handle_pending_confirmation(user_input, user_id)
        if pending_result:
            return pending_result
        
        sensitive_result = self._handle_sensitive_info(user_input, user_id)
        if sensitive_result:
            return sensitive_result
        
        self._handle_preference_extraction(user_input, user_id)
        
        patrol_report = self._execute_patrol(user_input, user_id)
        
        capsules = self._search_capsules(user_input, user_id)
        
        final_result = self._handle_intent_and_schedule(user_input, user_id, enhanced_input)
        
        final_result['patrol'] = patrol_report
        final_result['capsules'] = capsules
        
        logger.info(f"Task processing completed - user ID: {user_id}, status: {final_result.get('status')}")
        return final_result

    def _build_enhanced_input(self, user_input: str, context: str) -> str:
        """Build enhanced input (merge context)"""
        if not context:
            return user_input
        
        enhanced_input = (
            f"[Recent conversation context]:\n{context}\n\n[User current command]:\n{user_input}"
        )
        logger.debug(f"Built enhanced input - context lines: {len(context.split(chr(10)))}")
        return enhanced_input

    def close(self) -> None:
        """Close resources"""
        logger.info("Closing TaskEngine resources")
        pass

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
        if exc_type:
            logger.error(f"TaskEngine exited with exception - {exc_type}: {exc_val}", exc_info=True)

if __name__ == "__main__":
    pass
