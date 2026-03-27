#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Agent Core Conversation Logic

Features:
1. Integrate all system capabilities
2. Memory retrieval
3. Multimedia context awareness
4. Sensitive information protection
5. Intelligent reply generation
"""
from typing import Dict, Any, List, Optional
import re


class AgentCoreLogic:
    """Agent Core Conversation Logic - Integrates all modules"""
    
    def __init__(self, user_id: str, memory_processor=None, media_manager=None):
        """
        Initialize Agent core logic
        
        :param user_id: User ID
        :param memory_processor: Memory processor
        :param media_manager: Multimedia manager
        """
        self.user_id = user_id
        self.memory = memory_processor
        self.media = media_manager
    
    def process_message(self, user_input: str) -> Dict[str, Any]:
        """
        Process user message, integrating all system capabilities
        
        :param user_input: User input
        :return: Processing result
        """
        result = {
            "user_id": self.user_id,
            "input": user_input,
            "memories": [],
            "media_context": None,
            "reply": "",
            "intent": self._detect_intent(user_input)
        }
        
        if self.memory:
            try:
                result["memories"] = self.memory.query_memory(user_input)
            except Exception as e:
                result["memories"] = []
        
        if self.media:
            try:
                result["media_context"] = self._get_media_context(user_input)
            except Exception as e:
                result["media_context"] = None
        
        is_sensitive, masked_input = self._protect_sensitive(user_input)
        result["is_sensitive"] = is_sensitive
        
        result["reply"] = self._generate_reply(user_input, result["memories"])
        
        return result
    
    def _detect_intent(self, user_input: str) -> str:
        """
        Detect user intent
        
        :param user_input: User input
        :return: Intent type
        """
        query_patterns = [
            r"who am i",
            r"what do i like",
            r"my phone",
            r"my .* is",
            r"what do i want"
        ]
        
        for pattern in query_patterns:
            if re.search(pattern, user_input, re.IGNORECASE):
                return "query"
        
        info_patterns = [
            r"i am",
            r"my name is",
            r"i like",
            r"my phone",
            r"i want to go"
        ]
        
        for pattern in info_patterns:
            if re.search(pattern, user_input, re.IGNORECASE):
                return "inform"
        
        media_patterns = [
            r"save .* image",
            r"save .* video",
            r"save .* audio",
            r"upload .* file"
        ]
        
        for pattern in media_patterns:
            if re.search(pattern, user_input, re.IGNORECASE):
                return "media"
        
        return "chat"
    
    def _get_media_context(self, user_input: str) -> Optional[Dict]:
        """
        Get multimedia context
        
        :param user_input: User input
        :return: Multimedia context
        """
        if not self.media:
            return None
        
        media_keywords = {
            "image": ["image", "photo", "avatar", "picture"],
            "video": ["video", "recording"],
            "audio": ["audio", "recording", "music"]
        }
        
        for media_type, keywords in media_keywords.items():
            for keyword in keywords:
                if keyword in user_input.lower():
                    media_list = self.media.get_media_by_type(media_type)
                    return {
                        "type": media_type,
                        "count": len(media_list),
                        "recent": media_list[:3] if media_list else []
                    }
        
        return None
    
    def _protect_sensitive(self, user_input: str) -> tuple:
        """
        Sensitive information protection
        
        :param user_input: User input
        :return: (is_sensitive, masked_input)
        """
        phone_pattern = r'(1[3-9]\d{9})'
        masked_input = re.sub(phone_pattern, lambda m: m.group(1)[:3] + '****' + m.group(1)[-4:], user_input)
        
        card_pattern = r'(6\d{15,18})'
        masked_input = re.sub(card_pattern, lambda m: m.group(1)[:4] + '****' + m.group(1)[-4:], masked_input)
        
        id_pattern = r'(\d{17}[\dXx])'
        masked_input = re.sub(id_pattern, lambda m: m.group(1)[:6] + '********' + m.group(1)[-4:], masked_input)
        
        is_sensitive = (masked_input != user_input)
        
        return is_sensitive, masked_input
    
    def _generate_reply(self, user_input: str, memories: list) -> str:
        """
        Intelligent reply generation
        
        :param user_input: User input
        :param memories: Memory list
        :return: Reply content
        """
        intent = self._detect_intent(user_input)
        
        if intent == "query":
            if not memories:
                return "[Butler Style] I haven't remembered your relevant information yet. Would you like to tell me something?"
            
            info_dict = {}
            for memory in memories:
                content = memory.get("content", "")
                if "i am" in content.lower() or "my name is" in content.lower():
                    info_dict["name"] = content.replace("I am", "").replace("My name is", "").strip()
                elif "like" in content.lower():
                    info_dict["preference"] = content.replace("I like", "").strip()
                elif "phone" in content.lower():
                    info_dict["phone"] = content.replace("My phone", "").strip()
            
            if "who am i" in user_input.lower():
                name = info_dict.get("name", "friend")
                return f"[Butler Style] You are {name}!"
            elif "like" in user_input.lower():
                preference = info_dict.get("preference", "haven't told me yet")
                return f"[Butler Style] You like {preference}!"
            elif "phone" in user_input.lower():
                phone = info_dict.get("phone", "haven't told me yet")
                return f"[Butler Style] Your phone number is {phone}!"
            else:
                return f"[Butler Style] I remember you: {memories[-1].get('content', '')}"
        
        elif intent == "inform":
            return "[Butler Style] Got it, I've remembered that!"
        
        elif intent == "media":
            return "[Butler Style] Sure, I'll help you handle this file!"
        
        else:
            if memories:
                return f"[Butler Style] I understand what you mean, {memories[-1].get('content', '')}"
            return "[Butler Style] I'm listening, please continue~"
