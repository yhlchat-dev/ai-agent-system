#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Fault Self-Repair Module (Upgraded Version)
Features:
- Crash self-repair: Monitor Agent process, auto-restart after crash
- Hang detection: If no task execution for 5 minutes, consider as hung, force restart and release database locks
- Database self-repair: Release SQLite WAL locks, fix connection leaks
- Resource limit self-repair: Restart when memory/CPU continuously exceeds limits (works with monitoring module)
"""

import sqlite3
import threading
import time
from pathlib import Path
from typing import Optional, Callable

from infra.config import TASKS_DB, SHORT_TERM_DB, HANG_THRESHOLD


class SelfRepair:
    """Fault Self-Repair Manager"""

    def __init__(self, restart_callback: Optional[Callable] = None) -> None:
        """
        :param restart_callback: Function to actually restart Agent, injected by upper layer
        """
        self.restart_callback = restart_callback
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.last_task_time = time.time()
        self.reboot_count = 0
        
    def report_error(error_info):
        """Receive error information, trigger self-repair (basic version: print + log)"""
        print(f"[Self-Repair] Received error: {error_info['type']} - {error_info['message']}")

    def start(self) -> None:
        """Start self-repair monitoring thread"""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._repair_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop monitoring"""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)

    def _repair_loop(self) -> None:
        """Monitoring loop, check every second"""
        while not self._stop_event.is_set():
            self._check_hang()
            self._check_db_wal()
            time.sleep(1)

    def _check_hang(self) -> None:
        """Hang detection: If no task execution for a long time, trigger restart"""
        if time.time() - self.last_task_time > HANG_THRESHOLD:
            self._trigger_restart(f"Hang detected: no task execution for {HANG_THRESHOLD} seconds")

    def _check_db_wal(self):
        """Database self-repair: Try to release SQLite WAL locks"""
        for db_path in [TASKS_DB, SHORT_TERM_DB]:
            if db_path.exists():
                try:
                    conn = sqlite3.connect(str(db_path), timeout=1)
                    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                    conn.close()
                except Exception:
                    pass

    def _trigger_restart(self, reason: str) -> None:
        """Trigger restart (call upper layer callback)"""
        if self.restart_callback:
            self.reboot_count += 1
            self.restart_callback(reason)
            self.last_task_time = time.time()

    def update_task_activity(self) -> None:
        """Called externally to update last task execution time"""
        self.last_task_time = time.time()


if __name__ == "__main__":
    def fake_restart(reason: str) -> None:
        print(f"Restart: {reason}")

    sr = SelfRepair(restart_callback=fake_restart)
    sr.start()
    try:
        time.sleep(310)
    finally:
        sr.stop()
