with open('infra/sensitive_detector.py', 'w', encoding='utf-8') as f: 
    f.write('''#!/usr/bin/env python 
# -*- coding: utf-8 -*- 
ECHO 处于打开状态。
import re 
from dataclasses import dataclass 
from typing import List 
ECHO 处于打开状态。
ECHO 处于打开状态。
@dataclass 
class DetectionResult: 
    is_sensitive: bool 
    sensitive_types: List[str] 
    masked_text: str 
    original_text: str 
ECHO 处于打开状态。
ECHO 处于打开状态。
def scan_text(text: str) -
    sensitive_types = [] 
    masked_text = text 
    phone_pattern = r'1[3-9]\\d{9}' 
    if re.search(phone_pattern, text): 
        sensitive_types.append('phone') 
        masked_text = re.sub(phone_pattern, '1****0000', masked_text) 
    bank_pattern = r'\\b\\d{16,19}\\b' 
    if re.search(bank_pattern, text): 
        sensitive_types.append('bank_card') 
        for match in re.findall(bank_pattern, text): 
            masked_text = masked_text.replace(match, '****' + match[-4:]) 
    if re.search(api_pattern, text, re.IGNORECASE): 
        sensitive_types.append('api_key') 
        masked_text = re.sub(api_pattern, '****', masked_text) 
    return DetectionResult( 
        is_sensitive=len(sensitive_types) 
        sensitive_types=sensitive_types, 
        masked_text=masked_text, 
        original_text=text 
    ) 
''') 
