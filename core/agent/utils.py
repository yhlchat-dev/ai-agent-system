# -*- coding: utf-8 -*-
"""
Agent Common Utility Functions: Extract common small methods from cli
"""
import re
import time
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

def clean_text(text: str) -> str:
    """Clean special characters from text (enhanced: adapted for Chinese scenarios)"""
    if not text or not isinstance(text, str):
        return ""
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'[\x00-\x1f\x7f]', '', text)
    text = re.sub(r'([，。！？：；""''()（）【】])+', r'\1', text)
    return text

def format_timestamp(
    timestamp: Any, 
    format_str: str = "%Y-%m-%d %H:%M:%S"
) -> str:
    """Timestamp formatting (enhanced: compatible with more types)"""
    if timestamp is None:
        return ""
    if isinstance(timestamp, (int, float)):
        if timestamp > 1e12:
            timestamp = timestamp / 1000
        return datetime.fromtimestamp(timestamp).strftime(format_str)
    elif isinstance(timestamp, datetime):
        return timestamp.strftime(format_str)
    elif isinstance(timestamp, str):
        try:
            return datetime.strptime(timestamp, format_str).strftime(format_str)
        except:
            return timestamp
    else:
        return str(timestamp)

def get_user_id_from_context(context: Dict[str, Any]) -> str:
    """Extract user ID from context (enhanced: multi-field compatible)"""
    if not context:
        return "default_user"
    return context.get("user_id") or context.get("userId") or context.get("uid") or "default_user"

def log_agent_action(
    action: str, 
    user_id: str, 
    detail: str = "",
    log_file: Optional[str] = "./logs/agent_actions.log"
) -> str:
    """Agent operation log (enhanced: supports file persistence)"""
    log_time = format_timestamp(datetime.now())
    log_str = f"[{log_time}] [USER:{user_id}] {action} | {detail}"
    print(log_str)
    
    try:
        from pathlib import Path
        log_path = Path(log_file)
        log_path.parent.mkdir(exist_ok=True, parents=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(log_str + "\n")
    except Exception as e:
        print(f"Log write failed: {e}")
    return log_str

def validate_params(params: Dict[str, Any], required_keys: List[str]) -> Dict[str, Any]:
    """Parameter validation (new: generic parameter check)"""
    missing_keys = [key for key in required_keys if key not in params]
    if missing_keys:
        raise ValueError(f"Missing required parameters: {', '.join(missing_keys)}")
    cleaned_params = {k: clean_text(str(v)) if isinstance(v, str) else v for k, v in params.items()}
    return cleaned_params

def safe_json_loads(json_str: str) -> Dict[str, Any]:
    """Safe JSON parsing (new: avoid crash on parse failure)"""
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        log_agent_action("JSON parse failed", "system", f"Content: {json_str[:100]}...")
        return {}

def safe_json_dumps(data: Any) -> str:
    """Safe JSON generation (new: compatible with Chinese)"""
    try:
        return json.dumps(data, ensure_ascii=False, indent=2)
    except Exception as e:
        log_agent_action("JSON generation failed", "system", f"Error: {e}")
        return str(data)
