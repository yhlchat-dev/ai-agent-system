#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
280 Common Keyword Library
Includes: Identity info, Food preferences, Life hobbies, Travel, Personal goals, Body features, Q&A queries, Daily status
"""

KEYWORD_LIBRARY = {
    "identity": {
        "name": "Identity Info",
        "keywords": [
            "my name is", "name is", "I am", "name", "full name", "nickname", "alias",
            "years old", "age", "how old", "age", "years",
            "zodiac dog", "zodiac rat", "zodiac ox", "zodiac tiger", "zodiac rabbit", "zodiac dragon", "zodiac snake", "zodiac horse", "zodiac sheep", "zodiac monkey", "zodiac rooster", "zodiac pig", "zodiac sign",
            "height", "weight", "body type", "birthday", "birth date", "constellation", "origin", "hometown", "city", "gender", "male", "female"
        ],
        "category": "identity",
        "patterns": {
            "name": r"(?:my name is|name is|I am|name|full name|nickname|alias)([^\s,\.!?]+)",
            "age": r"(\d+) years old|age (\d+)",
            "zodiac": r"zodiac (dog|rat|ox|tiger|rabbit|dragon|snake|horse|sheep|monkey|rooster|pig)",
            "height": r"height (\d+)",
            "weight": r"weight (\d+)",
            "birthday": r"birthday (\d+/\d+|\d{4}/\d+/\d+)",
            "zodiac_sign": r"constellation (aries|taurus|gemini|cancer|leo|virgo|libra|scorpio|sagittarius|capricorn|aquarius|pisces)",
            "hometown": r"(?:origin|hometown|city)([^\s,\.!?]+)",
            "gender": r"(?:gender|male|female)"
        }
    },
    
    "food": {
        "name": "Food Preferences",
        "keywords": [
            "like to eat", "love to eat", "want to eat", "love to drink", "favorite drink",
            "staple food", "rice", "noodles", "dumplings", "buns",
            "soy products", "tofu", "soy milk", "dried tofu",
            "vegetables", "fruits", "meat", "beef", "pork", "chicken", "fish", "seafood",
            "hotpot", "bbq", "milk tea", "coffee", "cola", "water",
            "snacks", "nuts", "desserts",
            "spicy", "light", "salty", "sweet",
            "breakfast", "lunch", "dinner", "late night snack",
            "allergy", "don't eat", "allergic"
        ],
        "category": "preference",
        "patterns": {
            "like_food": r"(?:like to eat|love to eat|want to eat)([^\s,\.!?]+)",
            "like_drink": r"(?:love to drink|favorite drink)([^\s,\.!?]+)",
            "allergy": r"(?:allergy|don't eat|allergic)([^\s,\.!?]+)"
        }
    },
    
    "hobby": {
        "name": "Life Hobbies",
        "keywords": [
            "like", "hobby", "interest", "love to do", "love to play", "love to watch", "love to listen",
            "sports", "running", "fitness", "swimming", "basketball", "football",
            "games", "TV series", "movies", "music", "reading", "travel", "photography", "shopping", "fishing", "hiking", "cycling", "painting", "singing", "dancing",
            "programming", "work", "study", "sleep", "stay up late", "wake up early",
            "pets", "cat", "dog", "gardening", "tea", "smoking", "drinking", "shopping", "collecting", "crafts", "esports", "streaming"
        ],
        "category": "preference",
        "patterns": {
            "hobby": r"(?:like|hobby|interest|love to do|love to play|love to watch|love to listen)([^\s,\.!?]+)",
            "pet": r"(?:pets|cat|dog)([^\s,\.!?]*)"
        }
    },
    
    "travel": {
        "name": "Travel",
        "keywords": [
            "want to go", "go play", "travel", "trip", "vacation",
            "beach", "ocean", "sand", "mountain", "scenic area", "park",
            "abroad", "domestic", "city",
            "road trip", "fly", "train", "hotel",
            "camping", "hiking", "shopping", "check in", "attractions", "park", "aquarium", "zoo",
            "business trip", "go home", "visit family"
        ],
        "category": "plan",
        "patterns": {
            "destination": r"(?:want to go|go play|travel|trip|vacation)([^\s,\.!?]+)",
            "activity": r"(?:camping|hiking|shopping|check in)([^\s,\.!?]*)"
        }
    },
    
    "goal": {
        "name": "Personal Goals",
        "keywords": [
            "want", "hope", "plan", "intend", "find",
            "find partner", "find job", "find someone",
            "make money", "buy house", "buy car",
            "learn", "get certified", "fitness", "lose weight", "grow taller", "become handsome", "become beautiful",
            "travel", "startup", "promotion", "raise", "marriage", "dating",
            "wellness", "exercise", "save money", "learn skills", "reading", "sports", "quit smoking", "quit drinking",
            "companionship", "dream", "wish"
        ],
        "category": "plan",
        "patterns": {
            "goal": r"(?:want|hope|plan|intend|find)([^\s,\.!?]+)",
            "find": r"find (partner|job|someone)",
            "improve": r"(?:fitness|lose weight|grow taller|become handsome|become beautiful)([^\s,\.!?]*)"
        }
    },
    
    "body": {
        "name": "Body Features",
        "keywords": [
            "appearance", "face shape", "acne", "acne marks", "skin",
            "hairstyle", "hair", "eyes", "nose", "mouth",
            "height", "weight", "fat", "thin", "strong", "weak",
            "healthy", "sick", "cold", "fever", "wound", "scar",
            "nearsighted", "glasses", "braces"
        ],
        "category": "identity",
        "patterns": {
            "appearance": r"(?:appearance|face shape|skin)([^\s,\.!?]+)",
            "health": r"(?:healthy|sick|cold|fever)([^\s,\.!?]*)"
        }
    },
    
    "query": {
        "name": "Q&A Queries",
        "keywords": [
            "who am I", "what's my name", "how old am I", "what's my zodiac", "my zodiac sign",
            "my height", "my weight", "what do I like", "what do I love to eat", "where do I want to go",
            "what do I want to do", "my hobbies", "my goals", "my zodiac", "my constellation",
            "my hometown", "my origin", "my gender", "my birthday", "my habits",
            "my allergies", "my allergic", "my mood", "my status", "my plans",
            "my wishes", "my work", "my study", "my pets", "my daily life"
        ],
        "category": "query",
        "patterns": {
            "identity_query": r"who am I|what's my name",
            "age_query": r"how old am I|my age",
            "zodiac_query": r"what's my zodiac|my zodiac sign",
            "body_query": r"my height|my weight",
            "preference_query": r"what do I like|what do I love to eat|my hobbies",
            "plan_query": r"where do I want to go|what do I want to do|my goals|my plans",
            "info_query": r"my (hometown|origin|gender|birthday|constellation|habits|allergies|allergic)"
        }
    },
    
    "status": {
        "name": "Daily Status",
        "keywords": [
            "mood", "happy", "sad", "angry", "tired", "energetic",
            "good", "bad", "normal",
            "schedule", "wake up early", "stay up late", "nap",
            "go to work", "get off work", "go to school", "get out of school", "at home", "go out", "rest",
            "busy", "free", "healthy", "uncomfortable",
            "happy", "joyful", "troubled", "stressed", "relaxed", "hardworking"
        ],
        "category": "status",
        "patterns": {
            "mood": r"mood (good|bad|normal|happy|sad|angry|tired)",
            "activity": r"(go to work|get off work|go to school|get out of school|at home|go out|rest)"
        }
    }
}

QUERY_RESPONSE_TEMPLATES = {
    "identity_query": {
        "keywords": ["who am I", "what's my name", "my name"],
        "entity_type": "name",
        "response_template": "You are {name}",
        "fallback": "I haven't remembered your name yet"
    },
    "age_query": {
        "keywords": ["how old am I", "my age", "how old am I this year"],
        "entity_type": "age",
        "response_template": "You are {age} years old",
        "fallback": "I haven't remembered your age yet"
    },
    "zodiac_query": {
        "keywords": ["what's my zodiac", "my zodiac sign"],
        "entity_type": "zodiac",
        "response_template": "Your zodiac is {zodiac}",
        "fallback": "I haven't remembered your zodiac yet"
    },
    "height_query": {
        "keywords": ["my height"],
        "entity_type": "height",
        "response_template": "Your height is {height}cm",
        "fallback": "I haven't remembered your height yet"
    },
    "weight_query": {
        "keywords": ["my weight"],
        "entity_type": "weight",
        "response_template": "Your weight is {weight}kg",
        "fallback": "I haven't remembered your weight yet"
    },
    "preference_query": {
        "keywords": ["what do I like", "what do I love to eat", "my hobbies"],
        "entity_type": "hobby",
        "response_template": "You like {hobby}",
        "fallback": "I haven't remembered your preferences yet"
    },
    "food_query": {
        "keywords": ["what do I like to eat", "what do I love to eat"],
        "entity_type": "food",
        "response_template": "You like to eat {food}",
        "fallback": "I haven't remembered what you like to eat yet"
    }
}
