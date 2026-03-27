#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Agent Main Entry Point
Start UI Monitoring Panel
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

if __name__ == "__main__":
    from agent_monitor_ui import main
    main()
