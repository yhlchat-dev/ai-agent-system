#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Curiosity System

Features:
1. Actively complete user information
2. Improve user profile
3. Proactive interaction questioning
4. Intelligent question generation
"""
import random
from typing import List, Dict, Optional
import re


class CuriositySystem:
    """Curiosity System: Active information completion, user profile improvement, proactive interaction"""
    
    def __init__(self, user_id: str):
        """
        Initialize curiosity system
        
        :param user_id: User ID
        """
        self.user_id = user_id
        self.missing_fields = [
            "age",
            "occupation",
            "hobbies",
            "frequent_address",
            "birthday",
            "hometown",
            "favorite_movies",
            "favorite_music",
            "weekend_habits",
            "future_plans"
        ]
        
        self.asked_fields = []
        
        self.question_templates = {
            "age": [
                "By the way, would you mind telling me your age? I'd like to know you better~",
                "I don't know your age yet, would you like to share?",
                "Just curious, how old are you this year?"
            ],
            "occupation": [
                "What do you do for work?",
                "I'm curious about your profession, what is it?",
                "Would you mind telling me about your job?"
            ],
            "hobbies": [
                "Do you have any hobbies?",
                "What do you like to do in your free time?",
                "I'd like to know about your interests and hobbies~"
            ],
            "frequent_address": [
                "Which city do you frequent?",
                "Would you mind sharing your frequent address?",
                "Where do you live?"
            ],
            "birthday": [
                "When is your birthday?",
                "I'd like to remember your birthday, would you mind telling me?",
                "What's your zodiac sign?"
            ],
            "hometown": [
                "Where is your hometown?",
                "Where are you from?",
                "I'd like to know about your hometown~"
            ],
            "favorite_movies": [
                "What types of movies do you like?",
                "Have you watched any good movies recently?",
                "What's your favorite movie?"
            ],
            "favorite_music": [
                "What kind of music do you like?",
                "Whose songs do you usually listen to?",
                "What's your music taste like?"
            ],
            "weekend_habits": [
                "What do you usually like to do on weekends?",
                "Do you have any special weekend habits?",
                "How do you typically spend your weekends?"
            ],
            "future_plans": [
                "Do you have any plans for the near future?",
                "Is there anything you want to do in the future?",
                "What are your expectations for the future?"
            ]
        }
    
    def get_curiosity_question(self, memories: list) -> str:
        """
        Actively generate curiosity question to complete user information
        
        :param memories: User memory list
        :return: Curiosity question
        """
        known_info = []
        for memory in memories:
            content = memory.get("content", "")
            known_info.append(content)
        
        known_info_str = " ".join(known_info)
        
        unknown_fields = []
        for field in self.missing_fields:
            if field not in self.asked_fields and field not in known_info_str:
                unknown_fields.append(field)
        
        if not unknown_fields:
            return ""
        
        selected_field = random.choice(unknown_fields)
        
        self.asked_fields.append(selected_field)
        
        questions = self.question_templates.get(selected_field, [
            f"By the way, would you mind telling me your {selected_field}? I'd like to know you better~"
        ])
        
        return random.choice(questions)
    
    def should_ask_question(self, conversation_count: int) -> bool:
        """
        Determine whether to proactively ask a question
        
        :param conversation_count: Conversation round count
        :return: Whether to ask
        """
        return conversation_count > 0 and conversation_count % random.randint(3, 5) == 0
    
    def analyze_user_profile(self, memories: list) -> Dict:
        """
        Analyze user profile completeness
        
        :param memories: User memory list
        :return: Profile analysis result
        """
        profile = {
            "completeness": 0,
            "known_fields": [],
            "missing_fields": [],
            "details": {}
        }
        
        for memory in memories:
            content = memory.get("content", "")
            
            for field in self.missing_fields:
                if field in content:
                    profile["known_fields"].append(field)
                    profile["details"][field] = content
        
        profile["missing_fields"] = [
            field for field in self.missing_fields 
            if field not in profile["known_fields"]
        ]
        
        profile["completeness"] = len(profile["known_fields"]) / len(self.missing_fields) * 100
        
        return profile
    
    def get_personalized_greeting(self, memories: list) -> str:
        """
        Generate personalized greeting
        
        :param memories: User memory list
        :return: Personalized greeting
        """
        profile = self.analyze_user_profile(memories)
        
        if profile["completeness"] < 30:
            return "[Butler Style] Hello! I don't know much about you yet, could you tell me more about yourself?"
        elif profile["completeness"] < 60:
            return f"[Butler Style] Welcome back! I already know {len(profile['known_fields'])} aspects about you, and I'd like to learn more~"
        elif profile["completeness"] < 90:
            return f"[Butler Style] Nice to see you! My understanding of you has reached {int(profile['completeness'])}%!"
        else:
            return "[Butler Style] Welcome back! I feel like I know you quite well now, anything you'd like to chat about?"
    
    def reset_asked_fields(self):
        """Reset asked fields (for new session)"""
        self.asked_fields = []
