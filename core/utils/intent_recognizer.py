#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Intent Recognition Module
Determine user query type based on keyword matching
"""

from typing import Optional, Dict, List
import re


def extract_chinese_name(text: str) -> str:
    """
    Strictly extract Chinese name (core fix)
    
    Rules:
    1. Match keywords: my name is / I am called / I am / name is
    2. Only capture consecutive Chinese names (2-4 characters)
    3. Stop immediately when encountering modal particles, thanks, extra text
    
    :param text: Original text
    :return: Cleaned name
    """
    suffix_stop_words = [
        "haven't done", "haven't", "thank you", "thanks", "grateful", "la", "oh", "ah", "ne", "ba", 
        "ya", "ma", "ou", "ha", "hei", "ai", "ei", "en", "heng", "wei", "wa"
    ]
    
    stop_chars = set([
        "no", "thank", "do", "have", "of", "the", "in", "and", "or",
        "you", "I", "he", "she", "it", "they", "this", "that", "what", "how",
        "where", "who", "when", "how many", "how much", "la", "oh", "ah", "ne", "ba", "ya"
    ])
    
    keywords = ["I'm called", "my name is", "I am", "name is", "name is"]
    
    name = ""
    for keyword in keywords:
        if keyword in text:
            idx = text.find(keyword)
            after_keyword = text[idx + len(keyword):]
            
            chinese_chars = []
            for char in after_keyword:
                if '\u4e00' <= char <= '\u9fff':
                    if char in stop_chars:
                        break
                    chinese_chars.append(char)
                    if len(chinese_chars) >= 4:
                        break
                else:
                    break
            
            if chinese_chars:
                name = "".join(chinese_chars)
                break
    
    if name:
        for stop_word in suffix_stop_words:
            if stop_word in name:
                name = name.split(stop_word)[0]
                break
        
        if name.endswith("thank") and "thanks" in text:
            name = name[:-1]
    
    if 2 <= len(name) <= 4:
        return name
    else:
        return ""


class IntentRecognizer:
    """Intent Recognizer"""
    
    INTENT_PATTERNS = {
        "identity": {
            "keywords": ["who am I", "what's my name", "my name", "what am I called", "my full name"],
            "info_types": ["name"],
            "info_category": "identity",
            "description": "Identity info query"
        },
        "contact": {
            "keywords": ["my phone number", "my phone", "contact info", "what's my phone number", "phone number", "what's my phone", "my phone"],
            "info_types": ["phone", "email", "address"],
            "info_category": "contact",
            "description": "Contact info query"
        },
        "preference": {
            "keywords": ["what do I like", "what do I love to eat", "my hobbies", "what do I like to eat", "my preferences", "what do I like to eat", "what do I usually like to eat"],
            "info_types": ["preference", "like", "hobby"],
            "info_category": "preference",
            "description": "Preference info query"
        },
        "plan": {
            "keywords": ["what do I want to do", "what am I going to do", "my plans", "what do I want to do", "my intentions", "where do I want to go", "where do I want to go", "where am I going"],
            "info_types": ["intent", "plan", "goal"],
            "info_category": "plan",
            "description": "Plan intent query"
        }
    }
    
    SAVE_PATTERNS = {
        "name": {
            "patterns": [
                r"my name is([^\s,\.!?]+)", 
                r"I am([^\s,\.!?]+)", 
                r"my name is([^\s,\.!?]+)",
                r"name is([^\s,\.!?]+)",
                r"name is([^\s,\.!?]+)"
            ],
            "info_category": "identity",
            "clean_prefixes": ["do", "is", "am", "of"]
        },
        "phone": {
            "patterns": [r"(1[3-9]\d{9})"],
            "info_category": "contact"
        },
        "preference": {
            "patterns": [r"I like to eat([^\s,\.!?]+)", r"I love to eat([^\s,\.!?]+)", r"I like([^\s,\.!?]+)", r"I love([^\s,\.!?]+)"],
            "info_category": "preference"
        },
        "intent": {
            "patterns": [r"I want to([^\s,\.!?]+)", r"I'm going to([^\s,\.!?]+)", r"I plan to([^\s,\.!?]+)", r"want to go to([^\s,\.!?]+)"],
            "info_category": "plan"
        },
        "bank_card": {
            "patterns": [r"I have bank card(\d{16,19})", r"bank card(\d{16,19})", r"my bank card(\d{16,19})"],
            "info_category": "sensitive"
        },
        "id_card": {
            "patterns": [r"ID card(\d{15}|\d{18})", r"my ID card(\d{15}|\d{18})"],
            "info_category": "sensitive"
        },
        "other": {
            "patterns": [r"I have([^\s,\.!?]+)"],
            "info_category": "other"
        }
    }
    
    @classmethod
    def recognize_query_intent(cls, query: str) -> Optional[Dict]:
        """
        Recognize query intent
        
        :param query: User query text
        :return: Intent info dict, containing intent, info_types, info_category, etc.
        """
        query = query.lower().strip()
        
        for intent, config in cls.INTENT_PATTERNS.items():
            for keyword in config["keywords"]:
                if keyword in query:
                    return {
                        "intent": intent,
                        "info_types": config["info_types"],
                        "info_category": config["info_category"],
                        "description": config["description"]
                    }
        
        return None
    
    @classmethod
    def recognize_save_intent(cls, message: str) -> List[Dict]:
        """
        Recognize save intent
        
        :param message: User message
        :return: Save intent list
        """
        save_intents = []
        
        pure_query_keywords = [
            "who am I", "what do I want to do", "what do I like to eat", "what else do I like",
            "how many", "what", "how", "where",
            "is it", "right", "do I have", "can I", "may I"
        ]
        
        question_marks = ["?", "?", "?"]
        
        is_pure_query = False
        
        for keyword in pure_query_keywords:
            if keyword in message:
                is_pure_query = True
                break
        
        if not is_pure_query:
            for mark in question_marks:
                if mark in message:
                    is_pure_query = True
                    break
        
        if is_pure_query:
            return []
        
        for info_type, config in cls.SAVE_PATTERNS.items():
            for pattern in config["patterns"]:
                matches = re.finditer(pattern, message)
                for match in matches:
                    value = match.group(1)
                    
                    if info_type == "name":
                        value = extract_chinese_name(message)
                        if not value:
                            continue
                    
                    save_intents.append({
                        "info_type": info_type,
                        "info_value": value,
                        "info_category": config["info_category"]
                    })
        
        return save_intents
    
    @classmethod
    def get_info_category_by_type(cls, info_type: str) -> str:
        """
        Get info category by type
        
        :param info_type: Info type
        :return: Info category
        """
        type_to_category = {
            "name": "identity",
            "phone": "contact",
            "email": "contact",
            "address": "contact",
            "preference": "preference",
            "like": "preference",
            "hobby": "preference",
            "intent": "plan",
            "plan": "plan",
            "goal": "plan"
        }
        
        return type_to_category.get(info_type, "other")

def recognize_intent(query: str) -> Optional[Dict]:
    """
    Convenience function: Recognize query intent
    
    :param query: User query text
    :return: Intent info dict
    """
    return IntentRecognizer.recognize_query_intent(query)

def recognize_save_intent(message: str) -> List[Dict]:
    """
    Convenience function: Recognize save intent
    
    :param message: User message
    :return: Save intent list
    """
    return IntentRecognizer.recognize_save_intent(message)
