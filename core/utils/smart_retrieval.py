#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Smart Retrieval Engine
Includes: Dynamic weight adaptation, smart sorting optimization, post-deduplication mechanism, dynamic TopN recall
"""

import re
import time
from typing import Dict, List, Optional, Tuple
from collections import defaultdict


class SmartRetrievalEngine:
    """Smart Retrieval Engine"""
    
    ENTITY_RULES = {
        "name": {
            "keywords": ["my name is", "I am", "name is", "name is", "I'm called"],
            "pattern": r"(?:my name is|I am|name is|name is|I'm called)([^\s,\.!?]+)",
            "extractor": "extract_name",
            "weight": 1.0,
            "category": "identity"
        },
        "age": {
            "keywords": ["years old", "age", "how old", "age"],
            "pattern": r"(\d+) years old|age (\d+)",
            "extractor": "extract_age",
            "weight": 0.9,
            "category": "identity"
        },
        "hobby": {
            "keywords": ["like", "love", "hobby", "interest", "usually"],
            "pattern": r"(?:like|love|hobby|interest)([^\s,\.!?]+)",
            "extractor": "extract_hobby",
            "weight": 0.8,
            "category": "preference"
        },
        "goal": {
            "keywords": ["want", "hope", "want to find", "want to go", "plan", "goal"],
            "pattern": r"(?:want|hope|want to find|want to go|plan|goal)([^\s,\.!?]+)",
            "extractor": "extract_goal",
            "weight": 0.8,
            "category": "plan"
        },
        "phone": {
            "keywords": ["phone number", "phone", "contact"],
            "pattern": r"(1[3-9]\d{9})",
            "extractor": "extract_phone",
            "weight": 1.0,
            "category": "contact"
        }
    }
    
    QUERY_TYPE_RULES = {
        "identity_query": {
            "keywords": ["who am I", "what's my name", "my name", "what am I called"],
            "entity_type": "name",
            "top_n": 3,
            "weight_boost": 1.0
        },
        "age_query": {
            "keywords": ["how old am I", "my age", "how old am I this year"],
            "entity_type": "age",
            "top_n": 3,
            "weight_boost": 1.0
        },
        "preference_query": {
            "keywords": ["what do I like", "my hobbies", "what do I love", "what do I like to eat"],
            "entity_type": "hobby",
            "top_n": 5,
            "weight_boost": 0.9
        },
        "plan_query": {
            "keywords": ["what do I want to do", "what do I want", "my goals", "where do I want to go"],
            "entity_type": "goal",
            "top_n": 5,
            "weight_boost": 0.9
        },
        "contact_query": {
            "keywords": ["my phone number", "my phone", "contact info"],
            "entity_type": "phone",
            "top_n": 3,
            "weight_boost": 1.0
        }
    }
    
    def __init__(self):
        self.memory_usage_count = defaultdict(int)
        self.memory_timestamps = {}
    
    def detect_query_type(self, query: str) -> Optional[Dict]:
        """
        Detect query type
        
        :param query: User query
        :return: Query type configuration
        """
        query = query.lower().strip()
        
        for query_type, config in self.QUERY_TYPE_RULES.items():
            for keyword in config["keywords"]:
                if keyword in query:
                    return {
                        "query_type": query_type,
                        "entity_type": config["entity_type"],
                        "top_n": config["top_n"],
                        "weight_boost": config["weight_boost"]
                    }
        
        return None
    
    def calculate_dynamic_weights(self, query_type: Optional[str], entity_type: Optional[str]) -> Dict[str, float]:
        """
        Dynamic weight adaptation
        
        :param query_type: Query type
        :param entity_type: Entity type
        :return: Dynamic weight dictionary
        """
        weights = {}
        
        for entity, config in self.ENTITY_RULES.items():
            base_weight = config["weight"]
            
            if query_type and entity_type:
                if entity == entity_type:
                    weights[entity] = base_weight * 1.5
                else:
                    weights[entity] = base_weight * 0.5
            else:
                weights[entity] = base_weight
        
        return weights
    
    def smart_sort(self, memories: List[Dict], query_type: Optional[str] = None) -> List[Dict]:
        """
        Smart sorting optimization
        Triple sorting: time decay + usage heat + capsule priority
        
        :param memories: Memory list
        :param query_type: Query type
        :return: Sorted memory list
        """
        if not memories:
            return []
        
        current_time = time.time()
        
        def calculate_score(memory: Dict) -> float:
            timestamp = memory.get("timestamp", current_time)
            time_decay = 1.0 / (1.0 + (current_time - timestamp) / 86400)
            
            memory_key = memory.get("content", "")
            usage_count = self.memory_usage_count.get(memory_key, 0)
            usage_score = min(usage_count / 10.0, 1.0)
            
            capsule_priority = 0.0
            if memory.get("is_capsule"):
                capsule_priority = 0.3
            if memory.get("is_sensitive"):
                capsule_priority = 0.5
            
            entity_type = memory.get("entity_type", "")
            if entity_type in ["name", "phone", "age"]:
                entity_bonus = 0.2
            else:
                entity_bonus = 0.1
            
            total_score = (time_decay * 0.4 + usage_score * 0.3 + capsule_priority * 0.2 + entity_bonus * 0.1)
            
            return total_score
        
        sorted_memories = sorted(memories, key=calculate_score, reverse=True)
        
        return sorted_memories
    
    def smart_deduplicate(self, memories: List[Dict]) -> List[Dict]:
        """
        Post smart deduplication mechanism
        Keep only 1 record for same information, auto filter duplicate redundant data
        
        :param memories: Memory list
        :return: Deduplicated memory list
        """
        if not memories:
            return []
        
        seen_entities = {}
        unique_memories = []
        
        for memory in memories:
            entity_type = memory.get("entity_type", "other")
            content = memory.get("content", "")
            
            if entity_type in ["name", "age", "phone"]:
                if entity_type not in seen_entities:
                    seen_entities[entity_type] = content
                    unique_memories.append(memory)
                else:
                    if content != seen_entities[entity_type]:
                        seen_entities[entity_type] = content
                        unique_memories.append(memory)
            else:
                dedup_key = f"{entity_type}:{content}"
                if dedup_key not in seen_entities:
                    seen_entities[dedup_key] = True
                    unique_memories.append(memory)
        
        return unique_memories
    
    def calculate_dynamic_top_n(self, query: str, query_type: Optional[Dict] = None) -> int:
        """
        Dynamic TopN recall
        Short text query: Top3
        Long text input: Top5-Top10
        
        :param query: User query
        :param query_type: Query type configuration
        :return: TopN count
        """
        if query_type:
            return query_type.get("top_n", 5)
        
        query_length = len(query)
        
        if query_length <= 10:
            return 3
        elif query_length <= 20:
            return 5
        else:
            return 10
    
    def extract_entities(self, text: str) -> List[Dict]:
        """
        Extract entity information
        
        :param text: User input text
        :return: Extracted entity list
        """
        entities = []
        
        for entity_type, config in self.ENTITY_RULES.items():
            pattern = config["pattern"]
            matches = re.finditer(pattern, text)
            
            for match in matches:
                value = match.group(1) if match.lastindex else match.group(0)
                
                if entity_type == "name":
                    value = self._clean_name(value)
                    if not value or len(value) < 2 or len(value) > 4:
                        continue
                
                if entity_type == "age":
                    value = self._clean_age(value)
                    if not value:
                        continue
                
                entities.append({
                    "entity_type": entity_type,
                    "value": value,
                    "category": config["category"],
                    "weight": config["weight"],
                    "timestamp": time.time()
                })
        
        return entities
    
    def _clean_name(self, name: str) -> str:
        """Clean name"""
        stop_chars = set([
            "no", "thank", "do", "have", "of", "the", "in", "and", "or",
            "you", "I", "he", "she", "it", "they", "this", "that", "what", "how"
        ])
        
        cleaned = []
        for char in name:
            if char.isalpha():
                if char.lower() in stop_chars:
                    break
                cleaned.append(char)
                if len(cleaned) >= 4:
                    break
            else:
                break
        
        result = "".join(cleaned)
        
        return result if 2 <= len(result) <= 4 else ""
    
    def _clean_age(self, age_str: str) -> str:
        """Clean age"""
        if not age_str:
            return ""
        
        digits = re.findall(r'\d+', age_str)
        if digits:
            age = int(digits[0])
            if 1 <= age <= 150:
                return str(age)
        
        return ""
    
    def retrieve(self, query: str, memories: List[Dict]) -> Dict:
        """
        Smart retrieval main entry
        
        :param query: User query
        :param memories: Memory list
        :return: Retrieval result
        """
        query_type_config = self.detect_query_type(query)
        
        query_type = query_type_config["query_type"] if query_type_config else None
        entity_type = query_type_config["entity_type"] if query_type_config else None
        
        weights = self.calculate_dynamic_weights(query_type, entity_type)
        
        top_n = self.calculate_dynamic_top_n(query, query_type_config)
        
        sorted_memories = self.smart_sort(memories, query_type)
        
        unique_memories = self.smart_deduplicate(sorted_memories)
        
        if entity_type:
            filtered_memories = [m for m in unique_memories if m.get("entity_type") == entity_type]
        else:
            filtered_memories = unique_memories
        
        final_memories = filtered_memories[:top_n]
        
        for memory in final_memories:
            memory_key = memory.get("content", "")
            self.memory_usage_count[memory_key] += 1
        
        return {
            "query_type": query_type,
            "entity_type": entity_type,
            "top_n": top_n,
            "weights": weights,
            "results": final_memories,
            "total_count": len(memories),
            "filtered_count": len(filtered_memories)
        }


smart_retrieval_engine = SmartRetrievalEngine()
