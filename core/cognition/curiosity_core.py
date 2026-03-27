#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Curiosity Core Engine (Full Upgrade Version)
Core Features:
- Integrated configuration system with dynamically adjustable thresholds/keywords
- Exploration history persistence (survives restarts)
- Enhanced information entropy calculation logic
- Comprehensive parameter validation and exception handling
- Structured logging for monitoring
- Fully backward compatible interface
"""

import time
import json
import hashlib
import logging
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass

@dataclass
class ExplorationRecord:
    topic: str
    novelty_score: float
    quality_score: float
    is_failed: bool
    final_score: float
    penalty: float = 0.0
    bonus: float = 0.0
    similarity_to_past: float = 0.0
    timestamp: str = time.strftime("%Y-%m-%d %H:%M:%S")

from .curiosity_config import CuriosityConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path("logs/curiosity_core.log"), encoding="utf-8")
    ]
)
logger = logging.getLogger("CuriosityCore")

class CuriosityCore:
    """
    Curiosity Core Engine
    Core Features:
    1. Calculate text information entropy (distinguish high-value exploration from low-value chat)
    2. Deduplication mechanism based on repeat count
    3. Exploration history persistence
    4. Dynamic configuration adjustment
    """
    
    DEFAULT_CONFIG_KEYS = {
        "novelty_minimum": 0.5,
        "repeat_threshold": 2,
        "repeat_penalty": 0.4,
        "novelty_bonus": 0.25,
    }

    def __init__(self, data_dir: Path, explore_level: int = None):
        """
        Initialize Curiosity Core Engine
        :param data_dir: Data storage directory (for persisting exploration history)
        :param explore_level: Exploration level (prioritize config value, parameter is backup)
        """
        if not isinstance(data_dir, Path):
            data_dir = Path(data_dir)
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.config = CuriosityConfig(config_dir=str(self.data_dir))
        self._init_config_defaults()
        
        self.entropy_threshold = self.config.get_setting("entropy_threshold", 0.5)
        self.max_triggers = self.config.get_setting("max_triggers", 2)
        self.explore_level = explore_level or self.config.get_setting("explore_level_default", 5)
        
        self.low_entropy_keywords = self.config.get_setting(
            "low_entropy_keywords",
            ['hello', 'hi', 'good morning', 'good', 'weather', 'how are you',
             'are you there', 'thanks', 'bye', 'ok', 'okay']
        )
        self.high_entropy_keywords = self.config.get_setting(
            "high_entropy_keywords",
            ['quantum', 'research', 'latest', 'progress', 'algorithm', 'architecture', 'optimization',
             'machine learning', 'deep learning', 'neural network', 'paper', 'experiment',
             'application', 'technology', 'principle', 'mechanism', 'model', 'system', 'biology', 'entanglement']
        )
        
        self.history_file = self.data_dir / "explore_history.json"
        self.history: Dict[str, int] = self._load_history()
        
        logger.info(f"Curiosity Core Engine initialized - explore level: {self.explore_level}, entropy threshold: {self.entropy_threshold}, max triggers: {self.max_triggers}")

    def _init_config_defaults(self):
        """Initialize configuration defaults (ensure config file contains all necessary keys)"""
        current_settings = self.config.get_settings()
        updates = {}
        for key, default_value in self.DEFAULT_CONFIG_KEYS.items():
            if key not in current_settings:
                updates[key] = default_value
        if updates:
            self.config.update_settings(updates)
            logger.debug(f"Initialized config defaults: {updates}")

    def _load_history(self) -> Dict[str, int]:
        """Load persisted exploration history"""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                if isinstance(history, dict):
                    history = {k: int(v) for k, v in history.items() if isinstance(v, (int, float))}
                    logger.info(f"Loaded exploration history - {len(history)} records")
                    return history
                else:
                    logger.warning("Exploration history file format error, using empty history")
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Failed to load exploration history: {e}, using empty history")
        return {}

    def _save_history(self):
        """Persist exploration history"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved exploration history - {len(self.history)} records")
        except IOError as e:
            logger.error(f"Failed to save exploration history: {e}")

    def _calculate_entropy(self, text: str) -> float:
        """
        Enhanced text information entropy calculation
        Improvements:
        1. All weights loaded from config, supports dynamic adjustment
        2. More precise keyword matching (case insensitive)
        3. Avoid negative entropy values
        """
        if not isinstance(text, str) or text.strip() == "":
            return 0.0
        text = text.strip()
        total_chars = len(text)
        if total_chars == 0:
            return 0.0
        
        unique_chars = len(set(text))
        base_entropy = unique_chars / total_chars
        logger.debug(f"Base entropy: {base_entropy:.4f} (unique chars: {unique_chars}/{total_chars})")
        
        text_lower = text.lower()
        low_entropy_penalty = self.config.get_setting("low_entropy_penalty", 0.4)
        penalty_count = 0
        for kw in self.low_entropy_keywords:
            if kw.lower() in text_lower:
                base_entropy -= low_entropy_penalty
                penalty_count += 1
        if penalty_count > 0:
            logger.debug(f"Low entropy keyword penalty - matched {penalty_count} keywords, penalty: {low_entropy_penalty}")
        
        high_entropy_bonus = self.config.get_setting("high_entropy_bonus", 0.25)
        bonus_count = 0
        for kw in self.high_entropy_keywords:
            if kw in text:
                base_entropy += high_entropy_bonus
                bonus_count += 1
        if bonus_count > 0:
            logger.debug(f"High entropy keyword bonus - matched {bonus_count} keywords, bonus: {high_entropy_bonus}")
        
        long_text_bonus_20 = self.config.get_setting("long_text_bonus_20", 0.1)
        long_text_bonus_50 = self.config.get_setting("long_text_bonus_50", 0.15)
        length_bonus = 0.0
        if total_chars > 20:
            base_entropy += long_text_bonus_20
            length_bonus += long_text_bonus_20
        if total_chars > 50:
            base_entropy += long_text_bonus_50
            length_bonus += long_text_bonus_50
        if length_bonus > 0:
            logger.debug(f"Text length bonus - length: {total_chars}, bonus: {length_bonus}")
        
        final_entropy = max(0.0, min(1.0, base_entropy))
        logger.debug(f"Final entropy: {final_entropy:.4f}")
        
        return final_entropy
    
    def explore(self, input_text: str, **kwargs) -> Optional[str]:
        """
        Core exploration method (fully backward compatible interface)
        :param input_text: Input text
        :param kwargs: Additional parameters (reserved for extension)
        :return: Returns exploration result for high-entropy new input, None for low-entropy/repeated input
        """
        if not isinstance(input_text, str) or input_text.strip() == "":
            logger.warning("Empty input, skip exploration")
            return None
        input_text = input_text.strip()
        
        entropy = self._calculate_entropy(input_text)
        
        if entropy < self.entropy_threshold:
            logger.info(f"Low entropy input skipped - entropy: {entropy:.4f} < threshold: {self.entropy_threshold}, text: {input_text[:50]}...")
            return None
        
        input_hash = hashlib.md5(input_text.encode('utf-8')).hexdigest()
        call_count = self.history.get(input_hash, 0)
        
        if call_count >= self.max_triggers:
            logger.info(f"Repeated input skipped - trigger count: {call_count}/{self.max_triggers}, text: {input_text[:50]}...")
            return None
        
        self.history[input_hash] = call_count + 1
        self._save_history()
        
        explore_result = f"Exploring: {input_text[:50]} (entropy={entropy:.2f}, level={self.explore_level})"
        logger.info(f"Exploration triggered - entropy: {entropy:.4f}, trigger count: {call_count+1}/{self.max_triggers}, text: {input_text[:50]}...")
        
        return explore_result

    def update_config(self, key: str, value: Any) -> bool:
        """
        Dynamically update configuration parameter (no restart needed)
        :param key: Configuration key name
        :param value: Configuration value
        :return: Whether update succeeded
        """
        try:
            self.config.set_setting(key, value)
            if hasattr(self, key):
                setattr(self, key, value)
                logger.info(f"Dynamic config update - {key}: {value}")
            else:
                logger.warning(f"Config key {key} has no corresponding instance attribute, only updated config file")
            return True
        except ValueError as e:
            logger.error(f"Failed to update config: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Get engine statistics
        :return: Statistics dictionary
        """
        total_explored = sum(self.history.values())
        unique_inputs = len(self.history)
        avg_triggers = total_explored / unique_inputs if unique_inputs > 0 else 0.0
        
        return {
            "explore_level": self.explore_level,
            "entropy_threshold": self.entropy_threshold,
            "max_triggers": self.max_triggers,
            "unique_inputs": unique_inputs,
            "total_explorations": total_explored,
            "average_triggers_per_input": round(avg_triggers, 2),
            "low_entropy_keywords_count": len(self.low_entropy_keywords),
            "high_entropy_keywords_count": len(self.high_entropy_keywords)
        }

    def reset_history(self):
        """Reset exploration history"""
        self.history = {}
        self._save_history()
        logger.info("Exploration history reset")

    def close(self):
        """Safely close (ensure history saved)"""
        self._save_history()
        logger.info("Curiosity Core Engine safely closed")

    def __enter__(self):
        """Support context manager"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Auto save history and close"""
        self.close()
        if exc_type:
            logger.error(f"CuriosityCore exception: {exc_val}", exc_info=(exc_type, exc_val, exc_tb))


if __name__ == "__main__":
    test_data_dir = Path("./test_curiosity_core")
    
    with CuriosityCore(test_data_dir, explore_level=5) as core:
        result1 = core.explore("Hello, how is the weather today?")
        print(f"Test 1 - Low entropy input result: {result1} (expected: None)")
        
        result2 = core.explore("Latest research progress on quantum entanglement, how to apply to quantum communication system optimization?")
        print(f"Test 2 - High entropy input result: {result2} (expected: exploration string)")
        
        result3 = core.explore("Latest research progress on quantum entanglement, how to apply to quantum communication system optimization?")
        print(f"Test 3 - Repeated high entropy input (2nd time) result: {result3} (expected: exploration string)")
        
        result4 = core.explore("Latest research progress on quantum entanglement, how to apply to quantum communication system optimization?")
        print(f"Test 4 - Repeated high entropy input (3rd time) result: {result4} (expected: None)")
        
        stats = core.get_stats()
        print("\nTest 5 - Engine statistics:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
        core.update_config("entropy_threshold", 0.4)
        result6 = core.explore("What are the optimization methods for machine learning algorithms?")
        print(f"\nTest 6 - Result after threshold update: {result6}")
