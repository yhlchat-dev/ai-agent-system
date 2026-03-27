# -*- coding: utf-8 -*-
"""
Feishu Robot Adapter
"""
import json
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from core.tools.adapters import BaseAPIAdapter

class FeishuRobotAdapter(BaseAPIAdapter):
    """Feishu Robot Adapter"""
    def call(self, message, **kwargs):
        webhook_url = self._decrypt(self.config.get('webhook_url'))
        if not webhook_url:
            return {"success": False, "result": None, "error": "Feishu robot Webhook URL not configured"}
            
        headers = {'Content-Type': 'application/json'}
        data = {
            "msg_type": "text",
            "content": {"text": message}
        }
        
        try:
            if not REQUESTS_AVAILABLE:
                return {"success": False, "result": None, "error": "requests library not installed"}
                
            resp = requests.post(webhook_url, headers=headers, json=data, timeout=5)
            if resp.status_code == 200:
                return {"success": True, "result": "Message sent", "error": None}
            else:
                return {"success": False, "result": None, "error": f"HTTP {resp.status_code}: {resp.text}"}
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}
