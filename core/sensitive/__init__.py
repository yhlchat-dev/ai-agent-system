# -*- coding: utf-8 -*-
"""
Sensitive Detection Module Bridge
Import all functionality from utils.sensitive_detector, maintain backward compatibility
"""

from utils.sensitive_detector import *

__all__ = [
    'scan_text',
    'detect_sensitive',
    'get_masked_text',
    'DetectionResult'
]
