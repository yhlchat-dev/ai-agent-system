#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
280 Common Keyword Library
Includes: Identity info, Food preferences, Travel, Goals, Q&A queries, Status features, Daily chat
"""

import re
from typing import Dict, List, Optional
from collections import defaultdict
import time


KEYWORD_LIBRARY = {
    "identity": {
        "name": "Identity Info",
        "keywords": [
            "my name is", "name is", "I am", "name", "years old", "age", "how old", "age",
            "zodiac dog", "zodiac tiger", "zodiac dragon", "what zodiac", "zodiac sign",
            "height", "weight", "188", "acne", "skin", "birthday", "constellation", "gender", "male", "female", "hometown", "origin"
        ],
        "category": "identity",
        "patterns": {
            "name": r"(?:my name is|name is|I am|name)([^\s,\.!?]+)",
            "age": r"(\d+) years old|age (\d+)",
            "zodiac": r"zodiac (dog|rat|ox|tiger|rabbit|dragon|snake|horse|sheep|monkey|rooster|pig)",
            "height": r"height (\d+)",
            "weight": r"weight (\d+)",
            "birthday": r"birthday (\d+/\d+|\d{4}/\d+/\d+)",
            "hometown": r"(?:hometown|origin)([^\s,\.!?]+)",
            "gender": r"gender (male|female)"
        }
    },
    
    "food": {
        "name": "Food Preferences",
        "keywords": [
            "like to eat", "love to eat", "soy products", "rice", "noodles", "hotpot", "bbq",
            "fruits", "vegetables", "seafood", "meat", "milk tea", "drink water", "snacks", "allergy", "allergic", "don't eat", "staple food"
        ],
        "category": "preference",
        "patterns": {
            "like_food": r"(?:like to eat|love to eat)([^\s,\.!?]+)"
        }
    },
    
    "travel": {
        "name": "Travel",
        "keywords": [
            "want to go", "go out", "travel", "beach", "ocean", "hiking", "swimming", "vacation", "trip",
            "where to go", "where to play", "go out", "shopping", "park", "zoo"
        ],
        "category": "plan",
        "patterns": {
            "destination": r"(?:want to go|where to go|travel|trip|vacation)([^\s,\.!?]+)"
        }
    },
    
    "goal": {
        "name": "Goals",
        "keywords": [
            "want to do", "want", "plan", "hope", "find", "find partner", "make money", "buy house", "buy car",
            "fitness", "lose weight", "learn", "work", "dream", "wish"
        ],
        "category": "plan",
        "patterns": {
            "goal": r"(?:want to do|want|plan|hope|find)([^\s,\.!?]+)"
        }
    },
    
    "query": {
        "name": "Q&A Queries",
        "keywords": [
            "who am I", "what's my name", "how old am I", "what's my zodiac", "what's my height", "what do I like to eat",
            "where do I want to go", "what do I want to do", "my hobbies", "my zodiac", "my weight", "my hometown"
        ],
        "category": "query",
        "patterns": {}
    },
    
    "status": {
        "name": "Status Features",
        "keywords": [
            "happy", "tired", "busy", "healthy", "uncomfortable", "acne", "appearance", "hairstyle",
            "glasses", "strong", "thin", "fat", "schedule", "stay up late", "wake up early"
        ],
        "category": "status",
        "patterns": {}
    },
    
    "chat": {
        "name": "Daily Chat",
        "keywords": [
            "hello", "hi", "are you there", "what's up", "thanks", "bye", "okay", "yes", "no", "why", "how"
        ],
        "category": "chat",
        "patterns": {}
    }
}

QUERY_RESPONSE_RULES = {
    "hello": "Hello!",
    "hi": "Hello!",
    "are you there": "Yes! What's up?",
    "thanks": "You're welcome!",
    "bye": "Bye! See you next time!",
    
    "who am I": {
        "query_type": "identity_query",
        "entity_type": "name",
        "response_template": "You are {name}",
        "fallback": "I haven't remembered your name yet"
    },
    "what's my name": {
        "query_type": "identity_query",
        "entity_type": "name",
        "response_template": "You are {name}",
        "fallback": "I haven't remembered your name yet"
    },
    "how old am I": {
        "query_type": "age_query",
        "entity_type": "age",
        "response_template": "You are {age} years old",
        "fallback": "I haven't remembered your age yet"
    },
    "what's my zodiac": {
        "query_type": "zodiac_query",
        "entity_type": "zodiac",
        "response_template": "Your zodiac is {zodiac}",
        "fallback": "I haven't remembered your zodiac yet"
    },
    "what's my height": {
        "query_type": "height_query",
        "entity_type": "height",
        "response_template": "Your height is {height}",
        "fallback": "I haven't remembered your height yet"
    },
    "my weight": {
        "query_type": "weight_query",
        "entity_type": "weight",
        "response_template": "Your weight is {weight}",
        "fallback": "I haven't remembered your weight yet"
    },
    "what do I like to eat": {
        "query_type": "food_query",
        "entity_type": "food",
        "response_template": "You like to eat {food}",
        "fallback": "I haven't remembered what you like to eat yet"
    },
    "my hobbies": {
        "query_type": "hobby_query",
        "entity_type": "hobby",
        "response_template": "You like {hobby}",
        "fallback": "I haven't remembered your hobbies yet"
    },
    "where do I want to go": {
        "query_type": "destination_query",
        "entity_type": "destination",
        "response_template": "You want to go to {destination}",
        "fallback": "I haven't remembered where you want to go yet"
    },
    "what do I want to do": {
        "query_type": "goal_query",
        "entity_type": "goal",
        "response_template": "You want to {goal}",
        "fallback": "I haven't remembered what you want to do yet"
    },
    "my hometown": {
        "query_type": "hometown_query",
        "entity_type": "hometown",
        "response_template": "Your hometown is {hometown}",
        "fallback": "I haven't remembered your hometown yet"
    }
}


class KeywordExtractor:
    """Keyword Extraction Engine"""
    
    def __init__(self):
        self.keyword_library = KEYWORD_LIBRARY
        self.response_rules = QUERY_RESPONSE_RULES
    
    def extract(self, text: str) -> List[Dict]:
        """Extract user information from text"""
        extracted_info = []
        
        for category, config in self.keyword_library.items():
            patterns = config.get("patterns", {})
            
            for entity_type, pattern in patterns.items():
                matches = re.finditer(pattern, text)
                
                for match in matches:
                    value = match.group(1) if match.lastindex else match.group(0)
                    
                    if value:
                        extracted_info.append({
                            "entity_type": entity_type,
                            "value": value,
                            "category": config["category"],
                            "keyword_category": category,
                            "timestamp": time.time()
                        })
        
        return extracted_info
    
    def detect_query(self, text: str) -> Optional[Dict]:
        """Detect query type"""
        text_clean = text.strip()
        
        if text_clean in self.response_rules:
            rule = self.response_rules[text_clean]
            
            if isinstance(rule, str):
                return {
                    "query_type": "chat",
                    "response": rule,
                    "is_chat": True
                }
            else:
                return {
                    "query_type": rule["query_type"],
                    "entity_type": rule["entity_type"],
                    "response_template": rule["response_template"],
                    "fallback": rule["fallback"],
                    "is_chat": False
                }
        
        return None
    
    def is_chat_message(self, text: str) -> bool:
        """Determine if it's daily chat"""
        text_clean = text.strip()
        return text_clean in ["hello", "hi", "are you there", "thanks", "bye"]
    
    def get_chat_response(self, text: str) -> Optional[str]:
        """Get daily chat response"""
        text_clean = text.strip()
        if text_clean in self.response_rules:
            rule = self.response_rules[text_clean]
            if isinstance(rule, str):
                return rule
        return None


_keyword_extractor = KeywordExtractor()


def get_keyword_library():
    """Get keyword library"""
    return KEYWORD_LIBRARY


def extract_user_info(text: str) -> List[Dict]:
    """Extract user information"""
    return _keyword_extractor.extract(text)


def detect_query(text: str) -> Optional[Dict]:
    """Detect query type"""
    return _keyword_extractor.detect_query(text)


def is_chat_message(text: str) -> bool:
    """Determine if it's daily chat"""
    return _keyword_extractor.is_chat_message(text)


def get_chat_response(text: str) -> Optional[str]:
    """Get daily chat response"""
    return _keyword_extractor.get_chat_response(text)
