# core/curiosity_config.py
"""
Curiosity Configuration System
Manages all configuration parameters for the curiosity engine, supports persistence, parameter validation, and dynamic updates.
"""

import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path("logs/curiosity_config.log"), encoding="utf-8")
    ]
)
logger = logging.getLogger("CuriosityConfig")

class CuriosityConfig:
    """
    Curiosity Configuration Manager
    Features:
    - Configuration persistence to JSON file
    - Default configuration fallback to avoid missing keys
    - Configuration item type/range validation
    - Support for single/batch updates and reset
    """
    
    DEFAULT_SETTINGS: Dict[str, Any] = {
        "decay_rate": 0.3,
        "repeat_threshold": 0.8,
        "repeat_penalty": 20.0,
        "novelty_bonus": 10.0,
        "novelty_minimum": 0.7,
        "base_score_weight": 100.0,
        "novelty_weight": 0.6,
        "quality_weight": 0.4,
    }
    
    VALIDATION_RULES: Dict[str, tuple] = {
        "decay_rate": (float, 0.0, 1.0),
        "repeat_threshold": (float, 0.0, 1.0),
        "repeat_penalty": (float, 0.0, None),
        "novelty_bonus": (float, 0.0, None),
        "novelty_minimum": (float, 0.0, 1.0),
        "base_score_weight": (float, 0.1, None),
        "novelty_weight": (float, 0.0, 1.0),
        "quality_weight": (float, 0.0, 1.0),
    }

    def __init__(self, config_dir: str = "data"):
        """
        Initialize Configuration Manager
        :param config_dir: Configuration file save directory (auto-created)
        """
        if not isinstance(config_dir, str) or config_dir.strip() == "":
            raise ValueError("config_dir must be a non-empty string")
        
        self.config_dir = Path(config_dir.strip())
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / "curiosity_config.json"
        
        self.settings = self.DEFAULT_SETTINGS.copy()
        self.settings = self._load_and_validate_settings()
        logger.info(f"CuriosityConfig initialized - config file: {self.config_file}")

    def _validate_setting(self, key: str, value: Any) -> Any:
        """
        Validate single configuration item type and range
        :return: Validated value (auto type conversion)
        :raise ValueError: Thrown when validation fails
        """
        if key not in self.DEFAULT_SETTINGS:
            raise ValueError(f"Invalid config key: {key} (allowed keys: {list(self.DEFAULT_SETTINGS.keys())})")
        
        rule = self.VALIDATION_RULES.get(key)
        if not rule:
            logger.warning(f"No validation rule for key: {key}, skip validation")
            return value
        
        expected_type, min_val, max_val = rule
        
        try:
            if not isinstance(value, expected_type):
                value = expected_type(value)
        except (TypeError, ValueError):
            raise ValueError(f"Config key '{key}' must be {expected_type.__name__}, got {type(value).__name__}")
        
        if min_val is not None and value < min_val:
            raise ValueError(f"Config key '{key}' must be >= {min_val}, got {value}")
        if max_val is not None and value > max_val:
            raise ValueError(f"Config key '{key}' must be <= {max_val}, got {value}")
        
        if key in ["novelty_weight", "quality_weight"]:
            other_key = "quality_weight" if key == "novelty_weight" else "novelty_weight"
            current_other = self.settings.get(other_key, self.DEFAULT_SETTINGS[other_key])
            total = value + current_other
            if abs(total - 1.0) > 1e-6 and key in self.settings:
                logger.warning(f"Novelty+Quality weight sum is {total:.4f} (should be 1.0) - adjust manually if needed")
        
        return value

    def _load_and_validate_settings(self) -> Dict[str, Any]:
        """Load config file and validate all items, missing items use default values"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                logger.debug(f"Loaded config from file: {self.config_file}")
            except json.JSONDecodeError as e:
                logger.error(f"Config file is invalid JSON ({e}), use default settings")
                loaded = {}
            except IOError as e:
                logger.error(f"Failed to read config file ({e}), use default settings")
                loaded = {}
        else:
            loaded = {}
            logger.info(f"Config file not found, will create default config: {self.config_file}")
        
        validated = self.DEFAULT_SETTINGS.copy()
        for key, value in loaded.items():
            if key not in validated:
                logger.warning(f"Ignore unknown config key: {key}")
                continue
            try:
                validated[key] = self._validate_setting(key, value)
            except ValueError as e:
                logger.error(f"Invalid value for config key '{key}': {e}, use default value {validated[key]}")
        
        self._save_settings(validated)
        return validated

    def _save_settings(self, settings: Dict[str, Any]):
        """Save configuration to file (enhanced exception handling)"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2, ensure_ascii=False, sort_keys=True)
            logger.debug(f"Config saved to file: {self.config_file}")
        except IOError as e:
            logger.error(f"Failed to save config file: {e}")
            raise RuntimeError(f"Cannot save config to {self.config_file}") from e

    def get_settings(self) -> Dict[str, Any]:
        """Get all current settings (returns copy to avoid external modification)"""
        return self.settings.copy()

    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Get single configuration item
        :param key: Configuration item key name
        :param default: Default value when key doesn't exist (prioritize class default)
        """
        if key in self.settings:
            return self.settings[key]
        return self.DEFAULT_SETTINGS.get(key, default)

    def set_setting(self, key: str, value: Any):
        """
        Set single configuration item (auto validate + save)
        :raise ValueError: Thrown when configuration item is invalid
        """
        validated_value = self._validate_setting(key, value)
        self.settings[key] = validated_value
        self._save_settings(self.settings)
        logger.info(f"Updated config key '{key}': {validated_value}")

    def update_settings(self, updates: Dict[str, Any]):
        """
        Batch update configuration (atomic operation: all succeed or all fail)
        :param updates: Configuration item key-value pairs
        :raise ValueError: Thrown when any configuration item is invalid
        """
        if not isinstance(updates, dict):
            raise TypeError("updates must be a dictionary")
        if not updates:
            logger.warning("Empty updates, skip")
            return
        
        validated_updates = {}
        for key, value in updates.items():
            if key not in self.DEFAULT_SETTINGS:
                logger.warning(f"Ignore unknown config key: {key}")
                continue
            validated_updates[key] = self._validate_setting(key, value)
        
        self.settings.update(validated_updates)
        self._save_settings(self.settings)
        logger.info(f"Batch updated {len(validated_updates)} config items: {list(validated_updates.keys())}")

    def reset_to_defaults(self):
        """Reset all configuration to default values"""
        self.settings = self.DEFAULT_SETTINGS.copy()
        self._save_settings(self.settings)
        logger.info("All config reset to default values")

    def __repr__(self) -> str:
        return f"CuriosityConfig(file={self.config_file}, items={len(self.settings)})"
