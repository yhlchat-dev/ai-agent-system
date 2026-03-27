#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Task Scheduler Module: Idle task queue management and scheduled task dispatching.
"""

import threading
import time
from typing import List, Callable, Optional
from threading import Timer

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.memory import MemoryJobStore

from infra.config import (
    BASE_DIR,
    DATA_DIR,
    ENCRYPT_KEY,
    COMPRESS_INTERVAL_HOURS,
    ARCHIVE_INTERVAL_DAYS,
)

from infra.config import BASE_DIR, DATA_DIR, ENCRYPT_KEY
from core.base.base import LogItem

try:
    import jieba
    import jieba.analyse
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False
    print("[TaskScheduler] Warning: jieba not installed, tag extraction will use simple space splitting.")


def extract_tags(text: str, max_tags: int = 3) -> str:
    """
    Extract up to max_tags keywords from text, return comma-separated string.
    If jieba is available, use TF-IDF extraction; otherwise split by space and take first max_tags words.
    """
    if not text:
        return ""
    if JIEBA_AVAILABLE:
        try:
            words = jieba.analyse.extract_tags(text, topK=max_tags)
            return ','.join(words)
        except Exception:
            pass
    words = text.split()
    seen = set()
    unique_words = []
    for w in words:
        if w not in seen:
            seen.add(w)
            unique_words.append(w)
    return ','.join(unique_words[:max_tags])


class TaskScheduler:
    """Task Scheduler: Manage idle task queue and scheduled tasks"""

    def __init__(self, logger, stm: Optional = None, ltm: Optional = None, start_scheduler: bool = True) -> None:
        """
        :param logger: Logger instance for logging
        :param stm: ShortTermMemory instance (optional)
        :param ltm: LongTermMemory instance (optional)
        :param start_scheduler: Whether to start APScheduler immediately
        """
        self.logger = logger
        self.compress_interval = COMPRESS_INTERVAL_HOURS * 3600
        self.stm = stm
        self.ltm = ltm
        self._start_compress_timer()

        self.idle_tasks: List[Callable] = [
            self._memory_summarize,
            self._log_compression,
            self._behavior_modeling,
            self._task_planning
        ]
        self._idle_lock = threading.Lock()
        self._is_executing = False

        jobstore = {'default': MemoryJobStore()}
        self.scheduler = BackgroundScheduler(jobstores=jobstore)
        self._setup_scheduled_jobs()
        if start_scheduler:
            self.scheduler.start()
            
    def _start_compress_timer(self):
        """Start timer for scheduled log compression"""
        timer = Timer(self.compress_interval, self._compress_logs_task)
        timer.daemon = True
        timer.start()        
            
    def _compress_logs_task(self):
        """Execute log compression and restart timer"""
        try:
            self.logger.compress_logs()
            print(f"[TaskScheduler] Log compression completed at: {time.ctime()}")
        except Exception as e:
            print(f"[TaskScheduler] Log compression failed: {e}")
        finally:
            self._start_compress_timer()        
            
    def _promote_preferences_job(self) -> None:
        if not self.ltm:
            return
        print("Executing preference promotion check...")
        try:
            promoted = self.ltm.check_and_promote_preferences(self.ltm.user_id, user_data=self.ud)
            if promoted:
                print(f"Preference promotion successful: {promoted}")
            else:
                print("No preferences promoted")
        except Exception as e:
            print(f"Preference promotion task failed: {e}")

    def _setup_scheduled_jobs(self) -> None:
        """Setup scheduled tasks: log compression, memory archive, short-term memory transfer (if stm and ltm exist)"""
        self.scheduler.add_job(
            self._log_compression,
            'interval',
            hours=COMPRESS_INTERVAL_HOURS,
            id='log_compression',
            replace_existing=True
        )
        self.scheduler.add_job(
            self._archive_memory,
            'interval',
            days=ARCHIVE_INTERVAL_DAYS,
            id='memory_archive',
            replace_existing=True
        )
        
        if self.ltm:
            self.scheduler.add_job(
                self._promote_preferences_job,
                'interval',
                hours=1,
                id='promote_preferences',
                replace_existing=True
            )

        if self.stm and self.ltm:
            self.scheduler.add_job(
                self._archive_short_term_job,
                'interval',
                seconds=30,
                id='short_term_archive',
                replace_existing=True
            )

    def _memory_summarize(self) -> None:
        """Memory summarization task"""
        print("  Executing idle task: memory_summarize")
        self.logger.log(LogItem(
            timestamp=time.time(),
            environment="idle",
            action="memory_summarize",
            result="success",
            success_rate=1.0
        ))

    def _log_compression(self) -> None:
        """Log compression task (calls logger's compress_logs)"""
        print("  Executing idle task: log_compression_start")
        self.logger.log(LogItem(
            timestamp=time.time(),
            environment="idle",
            action="log_compression_start",
            result="success",
            success_rate=1.0
        ))
        self.logger.compress_logs()
        print("  Executing idle task: log_compression_end")
        self.logger.log(LogItem(
            timestamp=time.time(),
            environment="idle",
            action="log_compression_end",
            result="success",
            success_rate=1.0
        ))

    def _behavior_modeling(self) -> None:
        """Behavior modeling task"""
        print("  Executing idle task: behavior_modeling")
        self.logger.log(LogItem(
            timestamp=time.time(),
            environment="idle",
            action="behavior_modeling",
            result="success",
            success_rate=1.0
        ))

    def _task_planning(self) -> None:
        """Task planning task"""
        print("  Executing idle task: task_planning")
        self.logger.log(LogItem(
            timestamp=time.time(),
            environment="idle",
            action="task_planning",
            result="success",
            success_rate=1.0
        ))

    def _archive_memory(self) -> None:
        """Memory archive task (calls logger's archive_memory)"""
        print("  Executing idle task: memory_archive")
        self.logger.log(LogItem(
            timestamp=time.time(),
            environment="scheduled",
            action="memory_archive",
            result="success",
            success_rate=1.0
        ))
        self.logger.archive_memory()

    def _archive_short_term_job(self) -> None:
        """Execute hourly, transfer old records from short-term memory to long-term memory"""
        self.logger.log(LogItem(
            timestamp=time.time(),
            environment="scheduled",
            action="short_term_archive_start",
            result="processing",
            success_rate=1.0
        ))

        try:
            count = self.ltm.archive_short_term(self.stm)
            print(f"[TaskScheduler] Short-term memory archive completed, processed {count} records")
            self.logger.log(LogItem(
                timestamp=time.time(),
                environment="scheduled",
                action="short_term_archive_end",
                result="success",
                success_rate=1.0
            ))
        except Exception as e:
            print(f"[TaskScheduler] Short-term memory archive task failed: {e}")
            self.logger.log(LogItem(
                timestamp=time.time(),
                environment="scheduled",
                action="short_term_archive_error",
                result=f"error: {e}",
                success_rate=0.0
            ))

    def execute_idle_tasks(self) -> None:
        """
        Execute all idle tasks by priority (non-blocking, runs in separate thread)
        """
        if self._is_executing:
            return
        with self._idle_lock:
            self._is_executing = True

        def run() -> None:
            try:
                for task in self.idle_tasks:
                    task()
                    time.sleep(1)
            finally:
                self._is_executing = False

        threading.Thread(target=run, daemon=True).start()

    def shutdown(self) -> None:
        """Shutdown scheduler and log"""
        self.logger.log(LogItem(
            timestamp=time.time(),
            environment="system",
            action="scheduler_shutdown",
            result="success",
            success_rate=1.0
        ))
        try:
            self.scheduler.shutdown()
        except Exception:
            pass
