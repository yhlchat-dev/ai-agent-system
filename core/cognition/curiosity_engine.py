#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Curiosity Engine: Evaluate input entropy and generate exploration strategies (Full Upgrade Version)
Core Features:
- Guaranteed non-empty string return (strictly meeting requirements)
- Integrated configuration system with dynamically adjustable thresholds
- Enhanced entropy calculation logic (more precise heuristic rules)
- Structured logging for monitoring and debugging
- Comprehensive parameter validation and exception handling
- Fully compatible with original interfaces and test functions
"""

import random
import re
import logging
from typing import Optional, Dict, Any

from core.curiosity_config import CuriosityConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/curiosity_engine.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("CuriosityEngine")

class CuriosityEngine:
    """
    Curiosity Engine Core Class
    Core Promise: The explore method always returns a non-empty string regardless of input
    """
    
    def __init__(self, config: Optional[CuriosityConfig] = None):
        """
        Initialize Curiosity Engine
        :param config: Configuration instance (optional, auto-created by default)
        """
        self.config = config or CuriosityConfig()
        self.threshold = self.config.get_setting("entropy_threshold_engine", 0.5)
        
        self.high_entropy_patterns = self.config.get_setting(
            "high_entropy_patterns",
            {
                "question_marks": r'[?？]',
                "inquiry_words": r'\b(what|how|why|unknown|how to|why|what|how)\b',
                "long_text_min_length": 20,
                "char_diversity_min": 10
            }
        )
        
        self.entropy_weights = self.config.get_setting(
            "entropy_weights",
            {
                "question_mark_bonus": 0.4,
                "inquiry_word_bonus": 0.3,
                "long_text_bonus": 0.2,
                "char_diversity_bonus": 0.1
            }
        )
        
        logger.info(f"Curiosity Engine initialized - entropy threshold: {self.threshold}")

    def calculate_entropy(self, text: str) -> float:
        """
        Enhanced text entropy calculation (simulation)
        Improvements:
        1. More robust null handling
        2. More precise regex matching
        3. Configurable weights
        4. Detailed logging for debugging
        """
        if not isinstance(text, str) or text.strip() == "":
            logger.debug("Empty input, entropy set to 0.0")
            return 0.0
        
        text_clean = text.strip()
        score = 0.0
        weight_config = self.entropy_weights
        
        if re.search(self.high_entropy_patterns["question_marks"], text_clean):
            score += weight_config["question_mark_bonus"]
            logger.debug(f"Question mark detected, entropy +{weight_config['question_mark_bonus']}")
        
        if re.search(self.high_entropy_patterns["inquiry_words"], text_clean.lower()):
            score += weight_config["inquiry_word_bonus"]
            logger.debug(f"Inquiry word detected, entropy +{weight_config['inquiry_word_bonus']}")
        
        if len(text_clean) > self.high_entropy_patterns["long_text_min_length"]:
            score += weight_config["long_text_bonus"]
            logger.debug(f"Text length threshold met, entropy +{weight_config['long_text_bonus']}")
        
        if len(set(text_clean)) > self.high_entropy_patterns["char_diversity_min"]:
            score += weight_config["char_diversity_bonus"]
            logger.debug(f"Character diversity threshold met, entropy +{weight_config['char_diversity_bonus']}")
        
        final_score = min(score, 1.0)
        logger.debug(f"Entropy calculation complete - raw score: {score:.2f}, final score: {final_score:.2f}, text: {text_clean[:20]}...")
        
        return final_score

    def explore(self, input_text: str) -> str:
        """
        Generate exploration behavior based on input (core method)
        [Guaranteed]: Returns non-empty string regardless of input
        :param input_text: Input text
        :return: Non-empty exploration result string
        """
        try:
            if not isinstance(input_text, str):
                input_text = str(input_text) if input_text is not None else ""
            
            input_clean = input_text.strip()
            
            if not input_clean:
                logger.warning("Empty input received, returning default response")
                return "Empty input received."
            
            entropy = self.calculate_entropy(input_clean)
            
            if entropy > self.threshold:
                result = f"High entropy detected ({entropy:.2f}). Exploring: {input_clean[:100]}"
                logger.info(f"High entropy input triggered exploration - entropy: {entropy:.2f}, input: {input_clean[:20]}...")
            else:
                result = f"Low entropy ({entropy:.2f}). Context acknowledged: {input_clean[:100]}"
                logger.info(f"Low entropy input context acknowledged - entropy: {entropy:.2f}, input: {input_clean[:20]}...")
            
            if not result or not isinstance(result, str) or result.strip() == "":
                result = f"Processed input: {input_clean[:50]} (entropy: {entropy:.2f})"
            
            return result.strip()
        
        except Exception as e:
            logger.error(f"Exploration process exception: {e}", exc_info=True)
            fallback_msg = "Input processed with system notice: unexpected error occurred."
            return fallback_msg

    def update_threshold(self, new_threshold: float) -> bool:
        """
        Dynamically update entropy threshold
        :param new_threshold: New threshold (between 0-1)
        :return: Whether update succeeded
        """
        try:
            if not isinstance(new_threshold, (int, float)):
                raise TypeError("Threshold must be a number")
            if new_threshold < 0.0 or new_threshold > 1.0:
                raise ValueError("Threshold must be between 0.0-1.0")
            
            self.threshold = new_threshold
            self.config.set_setting("entropy_threshold_engine", new_threshold)
            logger.info(f"Entropy threshold updated to: {new_threshold}")
            return True
        
        except (TypeError, ValueError) as e:
            logger.error(f"Failed to update threshold: {e}")
            return False

    def get_engine_status(self) -> Dict[str, Any]:
        """
        Get engine status information
        :return: Status dictionary
        """
        return {
            "threshold": self.threshold,
            "config_keys": list(self.config.get_settings().keys()),
            "high_entropy_patterns_count": len(self.high_entropy_patterns),
            "entropy_weights_count": len(self.entropy_weights)
        }

def generate_exploration(input_text: str) -> str:
    """
    Convenience function: Generate exploration result (maintains original interface)
    :param input_text: Input text
    :return: Non-empty exploration result string
    """
    engine = CuriosityEngine()
    return engine.explore(input_text)

if __name__ == "__main__":
    engine = CuriosityEngine()
    
    test1_result = engine.explore("")
    print(f"Test 1 - Empty input result: '{test1_result}' (non-empty validation: {bool(test1_result)})")
    
    test2_result = engine.explore(None)
    print(f"Test 2 - None input result: '{test2_result}' (non-empty validation: {bool(test2_result)})")
    
    test3_result = engine.explore(123456)
    print(f"Test 3 - Number input result: '{test3_result}' (non-empty validation: {bool(test3_result)})")
    
    test4_result = engine.explore("I went to the supermarket today and bought apples")
    print(f"Test 4 - Low entropy text result: '{test4_result}'")
    
    test5_result = engine.explore("How does quantum computing apply to artificial intelligence? What are the unknown challenges?")
    print(f"Test 5 - High entropy text result: '{test5_result}'")
    
    engine.update_threshold(0.6)
    test6_result = engine.explore("What are the basic principles of machine learning?")
    print(f"Test 6 - Result after threshold adjustment: '{test6_result}'")
    
    test7_result = generate_exploration("How to optimize Python code performance?")
    print(f"Test 7 - Convenience function result: '{test7_result}'")
    
    status = engine.get_engine_status()
    print("\nTest 8 - Engine status:")
    for key, value in status.items():
        print(f"  {key}: {value}")
