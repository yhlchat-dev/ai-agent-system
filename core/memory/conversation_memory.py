# -*- coding: utf-8 -*-
"""
Conversation Short-term Memory Module
================
Core Features:
- Store recent conversations between user and agent (default 7 days)
- Real-time detection and replacement of sensitive information (simplified version)
- Support time-based query, automatic archive to long-term memory
- Crash recovery (based on temp files)
- Thread-safe memory operations

Design Features:
- Independent instance per user, memory isolation
- Automatic background archive check (configurable interval)
- Complete exception handling and logging
- Cross-platform file path support
- Complete type annotations and docstrings
"""

import os
import json
import time
import threading
from datetime import datetime
from collections import deque
from pathlib import Path
from typing import List, Dict, Optional, Any, Deque, Callable

import logging
logger = logging.getLogger(__name__)

DEFAULT_MAX_ITEMS = 10000
DEFAULT_RETENTION_DAYS = 7
DEFAULT_CHECK_INTERVAL = 6 * 3600
TEMP_FILE_DIR = "data"
SENSITIVE_PLACEHOLDER = "[Sensitive information protected]"

try:
    from utils.sensitive_detector import detect_sensitive
except ImportError:
    logger.warning("Sensitive information detection module import failed, sensitive detection will be disabled")
    def detect_sensitive(content: str) -> List[str]:
        """Degraded sensitive detection (always returns empty)"""
        return []

try:
    from utils.security import encrypt_data, decrypt_data
except ImportError:
    logger.warning("Encryption module import failed, sensitive information will only be replaced not encrypted")
    def encrypt_data(data: str) -> str:
        """Degraded encryption (returns original data)"""
        return data
    def decrypt_data(data: str) -> str:
        """Degraded decryption (returns original data)"""
        return data


class ConversationItem:
    """
    Single conversation item model
    Stores complete information of a single conversation round, including content, role, timestamp, metadata, etc.
    """

    def __init__(self, content: str, role: str = "user", metadata: Optional[Dict[str, Any]] = None):
        """
        Initialize conversation item
        
        :param content: Conversation content (text)
        :param role: Role identifier, options: 'user', 'agent', 'system'
        :param metadata: Additional metadata dict, e.g. {'session_id': 'xxx', 'app': 'chat'}
        """
        self.id: str = f"conv_{int(time.time() * 1000)}_{os.urandom(4).hex()}"
        self.timestamp: float = time.time()
        self.content: str = content.strip() if isinstance(content, str) else ""
        self.role: str = role.lower() if isinstance(role, str) else "user"
        self.metadata: Dict[str, Any] = metadata.copy() if isinstance(metadata, dict) else {}
        
        self.sensitive: bool = False
        self.sensitive_id: Optional[str] = None
        
        self.tags: List[str] = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict format (for serialization)"""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "content": self.content,
            "role": self.role,
            "metadata": self.metadata,
            "sensitive": self.sensitive,
            "sensitive_id": self.sensitive_id,
            "tags": self.tags
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationItem":
        """Deserialize from dict to instance"""
        required_fields = ["content", "role"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Conversation item missing required field: {field}")
        
        item = cls(
            content=str(data["content"]),
            role=str(data["role"]),
            metadata=data.get("metadata", {})
        )
        
        item.id = str(data.get("id", item.id))
        item.timestamp = float(data.get("timestamp", item.timestamp))
        item.sensitive = bool(data.get("sensitive", False))
        item.sensitive_id = data.get("sensitive_id")
        item.tags = list(data.get("tags", []))
        
        return item

    def __repr__(self) -> str:
        """String representation (for debugging)"""
        return f"<ConversationItem id={self.id[:8]} role={self.role} time={self.timestamp:.0f}>"


class ConversationMemory:
    """
    Conversation Short-term Memory Manager (independent instance per user)
    
    Core Features:
    - Thread-safe memory storage (deque)
    - Real-time sensitive information detection and content replacement
    - Automatic periodic check and archive of expired items
    - Crash recovery (based on temp files)
    - Support multi-dimensional query (time, role, tags)
    """

    def __init__(
        self, 
        user_id: str,
        max_items: int = DEFAULT_MAX_ITEMS,
        retention_days: int = DEFAULT_RETENTION_DAYS,
        check_interval: int = DEFAULT_CHECK_INTERVAL,
        enable_auto_archive: bool = True
    ):
        """
        Initialize conversation memory manager
        
        :param user_id: User unique identifier (for data isolation)
        :param max_items: Maximum items stored in memory
        :param retention_days: Conversation retention days (exceeded items archived)
        :param check_interval: Auto archive check interval (seconds)
        :param enable_auto_archive: Whether to enable auto archive
        :raises ValueError: User ID is empty or parameters invalid
        """
        if not isinstance(user_id, str) or user_id.strip() == "":
            raise ValueError("user_id must be non-empty string")
        if not isinstance(max_items, int) or max_items <= 0:
            raise ValueError("max_items must be positive integer")
        if not isinstance(retention_days, int) or retention_days <= 0:
            raise ValueError("retention_days must be positive integer")
        
        self.user_id: str = user_id.strip()
        self.max_items: int = max_items
        self.retention_days: int = retention_days
        self.check_interval: int = check_interval
        self.enable_auto_archive: bool = enable_auto_archive
        
        self.memory: Deque[ConversationItem] = deque(maxlen=max_items)
        self.lock: threading.RLock = threading.RLock()
        
        self.temp_file: Path = Path(TEMP_FILE_DIR) / self.user_id / "conversation.tmp"
        
        self._stop_event: threading.Event = threading.Event()
        self._check_thread: Optional[threading.Thread] = None
        
        self._load_from_temp()
        if self.enable_auto_archive:
            self._start_check_thread()
        
        logger.info(
            f"Conversation memory manager initialized - "
            f"User: {self.user_id}, "
            f"Max items: {self.max_items}, "
            f"Retention days: {self.retention_days}, "
            f"Current item count: {len(self.memory)}"
        )

    def _start_check_thread(self) -> None:
        """Start background archive check thread"""
        if self._check_thread and self._check_thread.is_alive():
            logger.warning("Archive check thread already running, no need to start again")
            return
        
        self._check_thread = threading.Thread(
            target=self._periodic_check,
            daemon=True,
            name=f"ConvCheck-{self.user_id[:8]}"
        )
        self._check_thread.start()
        logger.debug(f"Archive check thread started - Interval: {self.check_interval/3600:.1f} hours")

    def _periodic_check(self) -> None:
        """Periodic archive check (background thread)"""
        while not self._stop_event.wait(self.check_interval):
            try:
                archived = self.check_and_archive()
                if archived:
                    logger.info(
                        f"Auto archive completed - "
                        f"User: {self.user_id}, "
                        f"Archived item count: {len(archived)}"
                    )
            except Exception as e:
                logger.error(
                    f"Auto archive check exception - "
                    f"User: {self.user_id}, "
                    f"Error: {e}",
                    exc_info=True
                )

    def stop(self, timeout: float = 5.0) -> None:
        """
        Safely stop manager (stop background thread and save data)
        
        :param timeout: Thread stop timeout (seconds)
        """
        self._stop_event.set()
        if self._check_thread and self._check_thread.is_alive():
            self._check_thread.join(timeout=timeout)
            if self._check_thread.is_alive():
                logger.warning(f"Archive check thread stop timeout - User: {self.user_id}")
        
        self._save_to_temp()
        
        logger.info(f"Conversation memory manager stopped - User: {self.user_id}")

    def add(
        self, 
        content: str, 
        role: str = "user", 
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None
    ) -> str:
        """
        Add a conversation record (core method)
        
        :param content: Conversation content
        :param role: Role identifier
        :param metadata: Additional metadata
        :param tags: Classification tag list
        :return: ID of newly added item
        :raises Exception: Exception thrown when add fails (caught and logged)
        """
        try:
            if content is None:
                content = ""
            elif not isinstance(content, str):
                content = str(content)
            
            item = ConversationItem(content, role, metadata)
            if tags and isinstance(tags, list):
                item.tags = [str(tag).strip() for tag in tags if tag and str(tag).strip()]
            
            with self.lock:
                sensitive_items = detect_sensitive(item.content)
                if sensitive_items:
                    logger.warning(
                        f"Sensitive information detected - "
                        f"User: {self.user_id}, "
                        f"Sensitive types: {sensitive_items}, "
                        f"Content: {item.content[:50]}..."
                    )
                    item.content = SENSITIVE_PLACEHOLDER
                    item.sensitive = True
                    item.metadata["sensitive"] = True
                    item.metadata["sensitive_types"] = sensitive_items
                
                self.memory.append(item)
                self._save_to_temp()
                
                logger.debug(
                    f"New conversation record added - "
                    f"User: {self.user_id}, "
                    f"Role: {item.role}, "
                    f"ID: {item.id[:8]}, "
                    f"Sensitive: {item.sensitive}, "
                    f"Total: {len(self.memory)}"
                )
            
            return item.id
        
        except Exception as e:
            logger.error(
                f"Failed to add conversation record - "
                f"User: {self.user_id}, "
                f"Error: {e}",
                exc_info=True
            )
            raise

    def query(
        self,
        days: int = DEFAULT_RETENTION_DAYS,
        roles: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        include_sensitive: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Multi-dimensional query of conversation records
        
        :param days: Days to look back
        :param roles: Filter role list (e.g. ['user', 'agent'])
        :param tags: Filter tag list (matches if contains any tag)
        :param include_sensitive: Whether to include sensitive information items
        :return: List of matching conversation records (reverse chronological order)
        """
        try:
            cutoff = time.time() - days * 86400
            result: List[Dict[str, Any]] = []
            
            with self.lock:
                for item in reversed(self.memory):
                    if item.timestamp < cutoff:
                        continue
                    
                    if roles and item.role not in [r.lower() for r in roles]:
                        continue
                    
                    if tags and not any(tag in item.tags for tag in tags):
                        continue
                    
                    if not include_sensitive and item.sensitive:
                        continue
                    
                    result.append(item.to_dict())
            
            logger.debug(
                f"Conversation query completed - "
                f"User: {self.user_id}, "
                f"Days: {days}, "
                f"Result count: {len(result)}"
            )
            return result
        
        except Exception as e:
            logger.error(
                f"Conversation query failed - "
                f"User: {self.user_id}, "
                f"Error: {e}",
                exc_info=True
            )
            return []

    def get_recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent N conversation records
        
        :param limit: Maximum return count
        :return: List of recent conversation records (chronological order)
        """
        try:
            if not isinstance(limit, int) or limit <= 0:
                limit = 50
            
            with self.lock:
                recent_items = list(self.memory)[-limit:]
                result = [item.to_dict() for item in recent_items]
            
            logger.debug(
                f"Get recent conversations - "
                f"User: {self.user_id}, "
                f"Count: {len(result)}, "
                f"Request limit: {limit}"
            )
            return result
        
        except Exception as e:
            logger.error(
                f"Failed to get recent conversations - "
                f"User: {self.user_id}, "
                f"Error: {e}",
                exc_info=True
            )
            return []

    def mark_sensitive_processed(self, item_id: str) -> bool:
        """
        Mark sensitive item as processed
        
        :param item_id: Item ID
        :return: Whether successfully marked
        """
        try:
            with self.lock:
                for item in self.memory:
                    if item.id == item_id and item.sensitive:
                        item.metadata["sensitive_processed"] = True
                        self._save_to_temp()
                        logger.debug(
                            f"Sensitive item marked as processed - "
                            f"User: {self.user_id}, "
                            f"ID: {item_id[:8]}"
                        )
                        return True
            
            logger.warning(
                f"Sensitive item not found - "
                f"User: {self.user_id}, "
                f"ID: {item_id[:8]}"
            )
            return False
        
        except Exception as e:
            logger.error(
                f"Failed to mark sensitive item - "
                f"User: {self.user_id}, "
                f"ID: {item_id[:8]}, "
                f"Error: {e}",
                exc_info=True
            )
            return False

    def check_and_archive(self, force_before: Optional[float] = None) -> List[ConversationItem]:
        """
        Check and archive expired items
        
        :param force_before: Force archive items earlier than this timestamp (higher priority than retention days)
        :return: List of archived items
        """
        try:
            cutoff = force_before if force_before is not None else (
                time.time() - self.retention_days * 86400
            )
            to_archive: List[ConversationItem] = []
            
            with self.lock:
                while self.memory and self.memory[0].timestamp < cutoff:
                    item = self.memory.popleft()
                    to_archive.append(item)
                
                if to_archive:
                    self._save_to_temp()
            
            if to_archive:
                self._handle_archive(to_archive)
            
            logger.info(
                f"Archive check completed - "
                f"User: {self.user_id}, "
                f"Archived item count: {len(to_archive)}, "
                f"Remaining item count: {len(self.memory)}"
            )
            return to_archive
        
        except Exception as e:
            logger.error(
                f"Archive check failed - "
                f"User: {self.user_id}, "
                f"Error: {e}",
                exc_info=True
            )
            return []

    def _handle_archive(self, items: List[ConversationItem]) -> None:
        """
        Handle archived items (notify UI + auto archive to long-term memory)
        
        :param items: List of items to archive
        """
        try:
            from ui.desktop_panel import desktop_panel
            desktop_panel.show_archive_notification(
                user_id=self.user_id,
                items=[item.to_dict() for item in items]
            )
            logger.debug(f"Archive notification sent - User: {self.user_id}, Item count: {len(items)}")
        except (ImportError, Exception) as e:
            logger.debug(f"No UI panel, executing silent archive - User: {self.user_id}, Error: {e}")
            self._auto_archive(items)

    def _auto_archive(self, items: List[ConversationItem]) -> None:
        """
        Auto archive to long-term memory
        
        :param items: List of items to archive
        """
        if not items:
            return
        
        try:
            from core.memory.long_term_memory import LongTermMemory
            ltm = LongTermMemory(user_id=self.user_id)
            
            jieba_available = False
            try:
                import jieba.analyse
                jieba_available = True
            except ImportError:
                logger.warning("jieba not installed, will skip keyword extraction")
            
            archived_count = 0
            for item in items:
                try:
                    dt = datetime.fromtimestamp(item.timestamp)
                    tags = [dt.strftime("%Y-%m")]
                    
                    role_tag_map = {
                        "user": "User message",
                        "agent": "Agent reply",
                        "system": "System event"
                    }
                    tags.append(role_tag_map.get(item.role, "Unknown role"))
                    
                    if jieba_available and item.content and not item.sensitive:
                        try:
                            keywords = jieba.analyse.extract_tags(item.content, topK=3)
                            tags.extend(keywords)
                        except Exception as e:
                            logger.warning(f"Keyword extraction failed: {e}")
                    
                    ltm.save_conversation(
                        user_id=self.user_id,
                        role=item.role,
                        content=item.content,
                        file_path=None,
                        tags=",".join(tags)
                    )
                    archived_count += 1
                
                except Exception as e:
                    logger.error(
                        f"Single item archive failed - "
                        f"User: {self.user_id}, "
                        f"ID: {item.id[:8]}, "
                        f"Error: {e}"
                    )
            
            logger.info(
                f"Batch archive completed - "
                f"User: {self.user_id}, "
                f"Total items: {len(items)}, "
                f"Success: {archived_count}, "
                f"Failed: {len(items) - archived_count}"
            )
        
        except ImportError as e:
            logger.error(f"Long-term memory module import failed: {e}")
        except Exception as e:
            logger.error(
                f"Auto archive failed - "
                f"User: {self.user_id}, "
                f"Item count: {len(items)}, "
                f"Error: {e}",
                exc_info=True
            )

    def _save_to_temp(self) -> bool:
        """
        Save current memory data to temp file (for crash recovery)
        
        :return: Whether save successful
        """
        try:
            self.temp_file.parent.mkdir(parents=True, exist_ok=True)
            
            with self.lock:
                data = [item.to_dict() for item in self.memory]
            
            temp_path = self.temp_file.with_suffix(".tmp")
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            if temp_path.exists():
                temp_path.replace(self.temp_file)
            
            logger.debug(
                f"Temp file saved successfully - "
                f"User: {self.user_id}, "
                f"Path: {self.temp_file}, "
                f"Item count: {len(data)}"
            )
            return True
        
        except Exception as e:
            logger.error(
                f"Temp file save failed - "
                f"User: {self.user_id}, "
                f"Path: {self.temp_file}, "
                f"Error: {e}",
                exc_info=True
            )
            return False

    def _load_from_temp(self) -> int:
        """
        Load data from temp file (crash recovery)
        
        :return: Number of loaded items
        """
        loaded_count = 0
        if not self.temp_file.exists():
            return loaded_count
        
        try:
            with open(self.temp_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not isinstance(data, list):
                logger.warning(f"Temp file format error - User: {self.user_id}")
                return loaded_count
            
            with self.lock:
                for item_dict in data:
                    try:
                        item = ConversationItem.from_dict(item_dict)
                        self.memory.append(item)
                        loaded_count += 1
                    except Exception as e:
                        logger.warning(f"Item deserialization failed: {e}")
            
            logger.info(
                f"Data restored from temp file - "
                f"User: {self.user_id}, "
                f"Loaded item count: {loaded_count}, "
                f"File path: {self.temp_file}"
            )
        
        except Exception as e:
            logger.error(
                f"Temp file load failed - "
                f"User: {self.user_id}, "
                f"Path: {self.temp_file}, "
                f"Error: {e}",
                exc_info=True
            )
        
        return loaded_count

    def get_status(self) -> Dict[str, Any]:
        """
        Get current manager status (for monitoring/debugging)
        
        :return: Status dict
        """
        with self.lock:
            total_items = len(self.memory)
            role_stats = {}
            sensitive_count = 0
            for item in self.memory:
                role_stats[item.role] = role_stats.get(item.role, 0) + 1
                if item.sensitive:
                    sensitive_count += 1
            
            if total_items > 0:
                earliest = self.memory[0].timestamp
                latest = self.memory[-1].timestamp
            else:
                earliest = latest = 0
        
        return {
            "user_id": self.user_id,
            "total_items": total_items,
            "max_items": self.max_items,
            "retention_days": self.retention_days,
            "role_distribution": role_stats,
            "sensitive_items": sensitive_count,
            "earliest_timestamp": earliest,
            "latest_timestamp": latest,
            "temp_file": str(self.temp_file),
            "temp_file_exists": self.temp_file.exists(),
            "auto_archive_enabled": self.enable_auto_archive,
            "check_thread_alive": self._check_thread.is_alive() if self._check_thread else False
        }

    def clear(self, confirm: bool = False) -> bool:
        """
        Clear all conversation records (use with caution)
        
        :param confirm: Confirm clear (prevent accidental operation)
        :return: Whether successfully cleared
        """
        if not confirm:
            logger.warning(f"Clear operation requires confirmation - User: {self.user_id}")
            return False
        
        try:
            with self.lock:
                self.memory.clear()
            if self.temp_file.exists():
                self.temp_file.unlink()
            
            logger.warning(f"All conversation records cleared - User: {self.user_id}")
            return True
        
        except Exception as e:
            logger.error(
                f"Failed to clear conversation records - "
                f"User: {self.user_id}, "
                f"Error: {e}",
                exc_info=True
            )
            return False

    def __del__(self):
        """Destructor (ensure resource release)"""
        try:
            self.stop()
        except Exception:
            pass

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit (auto stop)"""
        self.stop()
        if exc_type:
            logger.error(
                f"Conversation memory manager abnormal exit - "
                f"User: {self.user_id}, "
                f"Exception: {exc_type.__name__}: {exc_val}"
            )


def create_conversation_memory(
    user_id: str,
    max_items: int = DEFAULT_MAX_ITEMS,
    retention_days: int = DEFAULT_RETENTION_DAYS
) -> ConversationMemory:
    """
    Quickly create conversation memory manager instance
    
    :param user_id: User ID
    :param max_items: Maximum item count
    :param retention_days: Retention days
    :return: ConversationMemory instance
    """
    return ConversationMemory(
        user_id=user_id,
        max_items=max_items,
        retention_days=retention_days
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    with ConversationMemory("test_user_001") as cm:
        cm.add("Hello, I want to consult about quantum entanglement", role="user")
        cm.add("Quantum entanglement is an important phenomenon in quantum mechanics...", role="agent")
        cm.add("My phone number is 13800138000, need to keep it confidential", role="user")
        
        recent = cm.get_recent(limit=10)
        print(f"\nRecent records: {recent}")
        
        sensitive_query = cm.query(days=1, include_sensitive=True)
        print(f"\nRecords containing sensitive information: {[item['content'] for item in sensitive_query]}")
        
        status = cm.get_status()
        print(f"\nManager status: {status}")
        
        sensitive_items = [item for item in sensitive_query if item['sensitive']]
        if sensitive_items:
            cm.mark_sensitive_processed(sensitive_items[0]['id'])
        
        archive_cutoff = time.time() + 3600
        archived = cm.check_and_archive(force_before=archive_cutoff)
        print(f"\nArchived item count: {len(archived)}")
