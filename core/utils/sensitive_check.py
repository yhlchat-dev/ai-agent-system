# -*- coding: utf-8 -*-
"""
Lightweight Local Sensitive Detection Module
Supports detection of phone numbers, ID cards, bank cards and other sensitive information
Pure local implementation, no network required
"""

import re
from typing import List, Dict, Any


class DetectionResult:
    """Detection Result Class"""
    def __init__(self):
        self.is_sensitive = False
        self.sensitive_types = []
        self.masked_text = ""


def detect_sensitive(text: Any) -> List[Dict]:
    """
    Detect sensitive information in text
    
    Args:
        text: Text to be detected
        
    Returns:
        List of sensitive information
    """
    if not isinstance(text, str):
        return []
    
    results = []
    
    phone_pattern = r'1[3-9]\d{9}'
    phone_matches = re.finditer(phone_pattern, text)
    for match in phone_matches:
        results.append({
            'type': 'phone',
            'value': match.group(),
            'start': match.start(),
            'end': match.end()
        })
    
    id_pattern = r'\d{17}[\dXx]'
    id_matches = re.finditer(id_pattern, text)
    for match in id_matches:
        results.append({
            'type': 'id_card',
            'value': match.group(),
            'start': match.start(),
            'end': match.end()
        })
    
    bank_pattern = r'\d{16,19}'
    bank_matches = re.finditer(bank_pattern, text)
    for match in bank_matches:
        if match.group() not in [r['value'] for r in results if r['type'] == 'id_card']:
            results.append({
                'type': 'bank_card',
                'value': match.group(),
                'start': match.start(),
                'end': match.end()
            })
    
    return results


def get_masked_text(text: Any) -> str:
    """
    Get masked text
    
    Args:
        text: Text to be masked
        
    Returns:
        Masked text
    """
    if not isinstance(text, str):
        return str(text) if text is not None else ""
    
    masked_text = text
    
    phone_pattern = r'(1[3-9]\d{9})'
    masked_text = re.sub(phone_pattern, lambda m: m.group(1)[:3] + '****' + m.group(1)[-4:], masked_text)
    
    id_pattern = r'(\d{17}[\dXx])'
    masked_text = re.sub(id_pattern, lambda m: m.group(1)[:6] + '********' + m.group(1)[-4:], masked_text)
    
    bank_pattern = r'(\d{16,19})'
    masked_text = re.sub(bank_pattern, lambda m: m.group(1)[:4] + '****' + m.group(1)[-4:], masked_text)
    
    return masked_text


def scan_text(text: Any) -> DetectionResult:
    """
    Scan text and return detection result
    
    Args:
        text: Text to be detected
        
    Returns:
        DetectionResult object
    """
    result = DetectionResult()
    
    if not isinstance(text, str):
        result.masked_text = str(text) if text is not None else ""
        return result
    
    sensitive_list = detect_sensitive(text)
    
    if sensitive_list:
        result.is_sensitive = True
        result.sensitive_types = list(set([item['type'] for item in sensitive_list]))
        result.masked_text = get_masked_text(text)
    else:
        result.masked_text = text
    
    return result
