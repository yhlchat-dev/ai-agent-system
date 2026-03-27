#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Core Base Module: Logging, compression, error collection.
"""

import csv
import json
import sqlite3
import time
import traceback
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any

from infra.config import (
    DATA_DIR,
    SHORT_TERM_DB,
    ERRORS_JSON,
    BEHAVIOR_LOG,
    COMPRESS_INTERVAL_HOURS,
)
from core.memory.short_term_memory import ShortTermMemory
import core.self.self_repair as self_repair

try:
    from core.capsules.capsule_manager import CapsuleManager
    CAPSULE_AVAILABLE = True
except ImportError:
    CAPSULE_AVAILABLE = False
    CapsuleManager = None


@dataclass
class LogItem:
    """Single log record item"""
    timestamp: float
    environment: str
    action: str
    result: str
    success_rate: float
    trace_id: str = ""


class Logger:
    """Log Manager: Responsible for caching logs, writing to database, compression and error collection"""

    def __init__(self, stm: ShortTermMemory, capsule_manager: Optional[CapsuleManager] = None):
        self.stm = stm
        self.capsule_manager = capsule_manager
        self.trace_counter = 0
        self.log_archive_interval = 86400
        self.last_archive_time = time.time()
        self._buffer: List[LogItem] = []
        self._last_compress = time.time()
        self._error_buffer: List[Dict] = []
        self.data_dir = DATA_DIR

    def _generate_trace_id(self) -> str:
        """Generate unique trace ID"""
        self.trace_counter += 1
        return f"{int(time.time())}-{self.trace_counter}"

    def log(self, item: LogItem, trace_id: Optional[str] = None) -> None:
        """Record a log entry (buffer first)"""
        if trace_id is None:
            trace_id = self._generate_trace_id()
        item.trace_id = trace_id
        self._buffer.append(item)
        if len(self._buffer) % 10 == 0:
            self._check_archive()

    def flush(self) -> None:
        """Write buffered logs to short-term memory database and clear buffer"""
        if not self._buffer:
            return
        for item in self._buffer:
            self.stm.insert_log(asdict(item))
        self._buffer.clear()

    def _check_archive(self) -> None:
        """Check if log archiving is needed"""
        now = time.time()
        if now - self.last_archive_time > self.log_archive_interval:
            self.archive_logs()
            self.last_archive_time = now

    def archive_logs(self) -> None:
        """Archive current short-term memory logs to CSV and clean up expired records"""
        cutoff = time.time() - 7 * 24 * 3600
        conn = sqlite3.connect(str(SHORT_TERM_DB))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT timestamp, environment, action, result, success_rate FROM logs WHERE timestamp < ?",
            (cutoff,)
        )
        rows = cursor.fetchall()
        if rows:
            archive_path = self.data_dir / f"logs_archive_{datetime.fromtimestamp(cutoff).strftime('%Y%m%d')}.csv"
            with open(archive_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "environment", "action", "result", "success_rate"])
                writer.writerows(rows)
            cursor.execute("DELETE FROM logs WHERE timestamp < ?", (cutoff,))
            conn.commit()
        conn.close()

    def collect_error(self, error_type: str, message: str, exc_info=None, context: Optional[Dict] = None) -> None:
        """
        Collect error information, write to errors.json, and trigger self-repair.
        Also save high-value errors as capsules.
        """
        error_info = {
            "timestamp": time.time(),
            "type": error_type,
            "message": message,
            "traceback": traceback.format_exc() if exc_info else "",
            "context": context or {}
        }
        
        errors = []
        if ERRORS_JSON.exists():
            try:
                with open(ERRORS_JSON, 'r', encoding='utf-8') as f:
                    errors = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        errors.append(error_info)
        if len(errors) > 1000:
            errors = errors[-1000:]
        try:
            with open(ERRORS_JSON, 'w', encoding='utf-8') as f:
                json.dump(errors, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"Error recording failed: {e}")

        self_repair.report_error(error_info)
        
        if self.capsule_manager and CAPSULE_AVAILABLE:
            try:
                self.capsule_manager.add_capsule(
                    problem=f"Error type: {error_type}",
                    solution=f"{message}\nContext: {json.dumps(context, ensure_ascii=False) if context else 'None'}",
                    capsule_type='error',
                    tags=['error', error_type.lower()],
                    creator='error_collector'
                )
            except Exception as e:
                print(f"[Logger] Failed to save error capsule: {e}")

    def compress_logs(self) -> None:
        """
        Compress logs from the past hour, generate behavior trend CSV.
        Called hourly by task scheduler.
        """
        end_time = time.time()
        start_time = end_time - COMPRESS_INTERVAL_HOURS * 3600
        logs = self.stm.query_logs(start_time, end_time)

        stats: Dict[str, List[float]] = {}
        for log in logs:
            action = log.get("action", "unknown")
            if action not in stats:
                stats[action] = []
            value = 1.0 if log.get("result") == "success" else 0.0
            stats[action].append(value)

        file_exists = BEHAVIOR_LOG.exists()
        with open(BEHAVIOR_LOG, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["timestamp", "behavior_type", "value"])
            for action, values in stats.items():
                avg = sum(values) / len(values) if values else 0.0
                mid_time = (start_time + end_time) / 2
                writer.writerow([mid_time, action, round(avg, 2)])

        self._last_compress = time.time()

    def archive_memory(self) -> None:
        """
        Long-term memory archive (not yet implemented, placeholder only)
        """
        pass
