#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
User Personalization Data Management Module
Responsible for user configuration read/write, sensitive data encryption/decryption (interfaces with security.py).

Core Features:
1. Independent configuration file for each user, data isolation
2. Sensitive data encrypted storage (supports custom keys)
3. Configuration persistence combined with memory caching
4. Comprehensive exception handling and logging
5. Compatible with original interface, smooth upgrade
"""

import json
import os
import re
import logging
import hashlib
from pathlib import Path
from typing import Any, Dict, Optional, TypedDict, Union
from datetime import datetime, timedelta

try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    load_dotenv = None

from utils.security import encrypt_data, decrypt_data
from infra.config import BASE_DIR, get_user_data_dir

LOG_LEVEL = logging.INFO
LOG_FORMAT = "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s"

CONFIG_FILE_NAME = "user_configs.json"
CONFIG_VERSION = "1.0"
DEFAULT_ENCRYPT_KEY_MIN_LENGTH = 16

PreferenceConfig = TypedDict('PreferenceConfig', {
    'min_mentions': int,
    'min_interval_days': int
})

PREFERENCE_MODES: Dict[str, PreferenceConfig] = {
    'low': {'min_mentions': 3, 'min_interval_days': 0},
    'medium': {'min_mentions': 4, 'min_interval_days': 1},
    'high': {'min_mentions': 5, 'min_interval_days': 2}
}

PENDING_CONFIRM_TIMEOUT = 300

logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
logger = logging.getLogger("UserDataManager")

class UserData:
    """
    User Personalization Data Management Class
    
    Features:
    - Each instance corresponds to one user, data files isolated
    - Sensitive data automatically encrypted storage
    - Configuration persistence, memory caching for performance
    - Comprehensive exception handling and logging
    - Compatible with original interface, supports smooth upgrade
    """
    
    def __init__(self, user_id: str = 'default', data_dir: Optional[Path] = None) -> None:
        """
        Initialize user data manager
        
        :param user_id: User unique identifier
        :param data_dir: Custom data storage directory (None uses default path)
        """
        self.user_id = self._validate_user_id(user_id)
        self.data_dir = self._init_data_dir(data_dir)
        
        self.config_file = self.data_dir / CONFIG_FILE_NAME
        
        self._load_env()
        self._validate_encrypt_key()
        
        self.configs: Dict[str, Any] = {}
        self._load_config()
        
        self.pending_confirmations: Dict[str, Dict[str, Any]] = {}
        
        logger.info(f"UserData instance initialized - user ID: {self.user_id}, data directory: {self.data_dir}")

    def _validate_user_id(self, user_id: str) -> str:
        """Validate and normalize user ID"""
        if not isinstance(user_id, str) or not user_id.strip():
            logger.warning(f"Invalid user ID, using default: {user_id}")
            return "default"
        
        safe_user_id = re.sub(r'[\\/:*?"<>|]', '_', user_id.strip())
        if safe_user_id != user_id.strip():
            logger.warning(f"User ID contains illegal characters, converted: {user_id} -> {safe_user_id}")
        
        return safe_user_id

    def _init_data_dir(self, data_dir: Optional[Path]) -> Path:
        """Initialize data directory"""
        if data_dir is None:
            data_dir = get_user_data_dir(self.user_id)
        
        try:
            data_dir = Path(data_dir)
            data_dir.mkdir(parents=True, exist_ok=True)
            return data_dir
        except Exception as e:
            logger.error(f"Failed to create data directory: {data_dir} - {e}", exc_info=True)
            default_dir = Path(BASE_DIR) / "user_data" / self.user_id
            default_dir.mkdir(parents=True, exist_ok=True)
            return default_dir

    def _load_env(self) -> None:
        """Load environment variables (prioritize .env file)"""
        if DOTENV_AVAILABLE and load_dotenv:
            env_path = Path(BASE_DIR) / ".env"
            if env_path.exists():
                load_dotenv(env_path)
                logger.debug(f"Loaded environment file: {env_path}")
        
        self.encrypt_key = os.getenv('ENCRYPT_KEY', '')
        
        key_file = Path(BASE_DIR) / "encryption.key"
        if not self.encrypt_key and key_file.exists():
            try:
                with open(key_file, 'r', encoding='utf-8') as f:
                    self.encrypt_key = f.read().strip()
                logger.debug("Loaded encryption key from key file")
            except Exception as e:
                logger.warning(f"Failed to read key file: {e}")
        
        if not self.encrypt_key:
            self.encrypt_key = 'default-dev-key-16bytes'
            logger.warning(
                "Encryption key not configured! Using development default key, "
                "production environment please set ENCRYPT_KEY environment variable "
                "or create encryption.key file"
            )

    def _validate_encrypt_key(self) -> None:
        """Validate encryption key strength"""
        if len(self.encrypt_key) < DEFAULT_ENCRYPT_KEY_MIN_LENGTH:
            logger.warning(
                f"Encryption key length insufficient (current {len(self.encrypt_key)} chars, minimum {DEFAULT_ENCRYPT_KEY_MIN_LENGTH}), "
                "sensitive data encryption security is lower"
            )
        
        key_hash = hashlib.sha256(self.encrypt_key.encode()).hexdigest()[:8]
        logger.debug(f"Encryption key hash: {key_hash}")

    def _load_config(self) -> None:
        """Load user configuration (with version compatibility and exception handling)"""
        if not self.config_file.exists():
            logger.debug(f"Configuration file does not exist, initializing empty config: {self.config_file}")
            self.configs = {"_version": CONFIG_VERSION}
            return
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                raw_config = json.load(f)
            
            self.configs = self._migrate_config(raw_config)
            logger.debug(f"Configuration file loaded successfully: {self.config_file}, config items: {len(self.configs)}")
            
        except json.JSONDecodeError as e:
            logger.error(f"Configuration file JSON parse failed: {self.config_file} - {e}", exc_info=True)
            self._backup_corrupted_config()
            self.configs = {"_version": CONFIG_VERSION}
            
        except Exception as e:
            logger.error(f"Failed to load configuration file: {self.config_file} - {e}", exc_info=True)
            self.configs = {"_version": CONFIG_VERSION}

    def _migrate_config(self, raw_config: Dict[str, Any]) -> Dict[str, Any]:
        """Configuration version migration (compatible with old version configs)"""
        config_version = raw_config.get('_version', '0.0')
        
        if config_version < CONFIG_VERSION:
            logger.info(f"Upgrading configuration file version: {config_version} -> {CONFIG_VERSION}")
            
            if 'auto_save_count' in raw_config and 'auto_save_counts' not in raw_config:
                raw_config['auto_save_counts'] = raw_config.pop('auto_save_count', {})
        
        raw_config['_version'] = CONFIG_VERSION
        return raw_config

    def _backup_corrupted_config(self) -> None:
        """Backup corrupted configuration file"""
        try:
            backup_name = f"user_configs_corrupted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            backup_path = self.data_dir / backup_name
            
            with open(self.config_file, 'rb') as src, open(backup_path, 'wb') as dst:
                dst.write(src.read())
            
            logger.warning(f"Backed up corrupted configuration file: {backup_path}")
        except Exception as e:
            logger.error(f"Failed to backup corrupted configuration file: {e}", exc_info=True)

    def _save_config(self) -> None:
        """Safely save configuration file (with atomic write)"""
        try:
            temp_file = self.config_file.with_suffix('.tmp')
            
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(
                    self.configs, 
                    f, 
                    ensure_ascii=False, 
                    indent=2,
                    sort_keys=False
                )
            
            temp_file.replace(self.config_file)
            logger.debug(f"Configuration file saved successfully: {self.config_file}")
            
        except Exception as e:
            logger.error(f"Failed to save configuration file: {self.config_file} - {e}", exc_info=True)
            raise

    def get_user_config(self, user_id: str) -> Dict[str, Any]:
        """
        Get all configuration for specified user (compatible with old interface)
        
        :param user_id: User ID (compatible parameter, actually uses instance's user_id)
        :return: User configuration dictionary
        """
        if user_id != self.user_id:
            logger.warning(
                f"get_user_config called with user_id({user_id}) doesn't match instance user_id({self.user_id}), "
                "returning current instance configuration"
            )
        
        return self.configs.copy()

    def set_user_config(self, user_id: str, key: str, value: Any) -> None:
        """
        Set user configuration item (compatible with old interface)
        
        :param user_id: User ID (compatible parameter, actually ignored)
        :param key: Configuration item key name
        :param value: Configuration item value
        """
        if user_id != self.user_id:
            logger.warning(
                f"set_user_config called with user_id({user_id}) doesn't match instance user_id({self.user_id}), "
                "operating on current instance configuration"
            )
        
        if not isinstance(key, str) or not key.strip():
            raise ValueError("Configuration item key must be a non-empty string")
        
        if key.lower() in ['phone', 'password', 'token', 'card', 'idcard']:
            if isinstance(value, str):
                value = self.encrypt_sensitive(value)
                logger.debug(f"Sensitive configuration item auto-encrypted: {key}")
        
        self.configs[key.strip()] = value
        self._save_config()

    def get_config(self, key: str, default: Any = None) -> Any:
        """
        Get current user's configuration item (recommended, no redundant parameters)
        
        :param key: Configuration item key name
        :param default: Default value
        :return: Configuration item value
        """
        return self.configs.get(key.strip(), default)

    def set_config(self, key: str, value: Any) -> None:
        """
        Set current user's configuration item (recommended, no redundant parameters)
        
        :param key: Configuration item key name
        :param value: Configuration item value
        """
        self.set_user_config(self.user_id, key, value)

    def encrypt_sensitive(self, text: Optional[str]) -> Optional[str]:
        """
        Sensitive data encryption
        
        :param text: Plaintext data
        :return: Encrypted string or None
        """
        if text is None or not isinstance(text, str) or text.strip() == "":
            return text
        
        try:
            encrypted = encrypt_data(text, key=self.encrypt_key)
            logger.debug(f"Sensitive data encrypted successfully, length: {len(text)}")
            return encrypted
        except Exception as e:
            logger.error(f"Sensitive data encryption failed: {e}", exc_info=True)
            raise

    def decrypt_sensitive(self, encrypted: Optional[str]) -> Optional[str]:
        """
        Sensitive data decryption
        
        :param encrypted: Encrypted string
        :return: Decrypted plaintext or None
        """
        if encrypted is None or not isinstance(encrypted, str) or encrypted.strip() == "":
            return encrypted
        
        try:
            decrypted = decrypt_data(encrypted, key=self.encrypt_key)
            logger.debug(f"Sensitive data decrypted successfully")
            return decrypted
        except Exception as e:
            logger.warning(f"Sensitive data decryption failed, trying to return as plaintext: {e}")
            return encrypted

    def set_pending(self, user_id: str, item: dict, timeout: int = PENDING_CONFIRM_TIMEOUT) -> None:
        """
        Set user pending confirmation item (with timeout)
        
        :param user_id: User ID
        :param item: Pending confirmation item dictionary
        :param timeout: Timeout duration (seconds)
        """
        if user_id != self.user_id:
            logger.warning(f"Pending confirmation item user_id doesn't match: {user_id} != {self.user_id}")
        
        if not isinstance(item, dict):
            raise ValueError("Pending confirmation item must be a dictionary type")
        
        pending_item = {
            'data': item,
            'create_time': datetime.now().timestamp(),
            'timeout': timeout
        }
        
        self.pending_confirmations[user_id] = pending_item
        logger.debug(f"Set pending confirmation item - user: {user_id}, content: {list(item.keys())}")

    def get_pending(self, user_id: str) -> Optional[dict]:
        """
        Get user pending confirmation item (auto cleanup expired items)
        
        :param user_id: User ID
        :return: Pending confirmation item dictionary or None
        """
        self._clean_expired_pending()
        
        pending = self.pending_confirmations.get(user_id)
        if pending:
            logger.debug(f"Got pending confirmation item - user: {user_id}")
            return pending['data']
        
        return None

    def clear_pending(self, user_id: str) -> None:
        """
        Clear user pending confirmation item
        
        :param user_id: User ID
        """
        if self.pending_confirmations.pop(user_id, None):
            logger.debug(f"Cleared pending confirmation item - user: {user_id}")

    def _clean_expired_pending(self) -> None:
        """Clean up all expired pending confirmation items"""
        now = datetime.now().timestamp()
        expired_ids = []
        
        for user_id, pending in self.pending_confirmations.items():
            expire_time = pending['create_time'] + pending['timeout']
            if now > expire_time:
                expired_ids.append(user_id)
        
        for user_id in expired_ids:
            self.pending_confirmations.pop(user_id)
            logger.debug(f"Cleaned expired pending confirmation item - user: {user_id}")

    def get_preference_learning_config(self) -> PreferenceConfig:
        """
        Get preference learning configuration
        
        :return: Configuration dictionary containing min_mentions and min_interval_days
        """
        config = self.configs.get('preference_learning', {})
        
        try:
            min_mentions = int(config.get('min_mentions', 4))
            min_interval_days = int(config.get('min_interval_days', 2))
            
            min_mentions = max(1, min_mentions)
            min_interval_days = max(0, min_interval_days)
            
            return {
                'min_mentions': min_mentions,
                'min_interval_days': min_interval_days
            }
        except (ValueError, TypeError):
            logger.warning("Invalid preference learning configuration, using default")
            return PREFERENCE_MODES['medium']

    def set_preference_learning_config(self, mode: str) -> None:
        """
        Set preference learning mode
        
        :param mode: Mode name (low/medium/high)
        :raises ValueError: Thrown when unknown mode
        """
        if mode not in PREFERENCE_MODES:
            raise ValueError(f"Unknown preference learning mode: {mode}, available: {list(PREFERENCE_MODES.keys())}")
        
        self.configs['preference_learning'] = PREFERENCE_MODES[mode].copy()
        self._save_config()
        logger.info(f"Preference learning mode set to: {mode}")

    def increment_auto_save_count(self, info_type: str) -> int:
        """
        Increment auto-save count for specified info type
        
        :param info_type: Info type (e.g. phone/password etc.)
        :return: Current count
        """
        if not isinstance(info_type, str) or not info_type.strip():
            raise ValueError("Info type must be a non-empty string")
        
        info_type = info_type.strip()
        counts = self.configs.get('auto_save_counts', {})
        
        if not isinstance(counts, dict):
            counts = {}
        
        counts[info_type] = counts.get(info_type, 0) + 1
        self.configs['auto_save_counts'] = counts
        self._save_config()
        
        current_count = counts[info_type]
        logger.debug(f"Auto-save count incremented - type: {info_type}, current: {current_count}")
        
        return current_count

    def get_auto_save_count(self, info_type: str) -> int:
        """
        Get auto-save count for specified info type
        
        :param info_type: Info type
        :return: Count value
        """
        info_type = info_type.strip()
        counts = self.configs.get('auto_save_counts', {})
        
        if isinstance(counts, dict):
            return int(counts.get(info_type, 0))
        else:
            logger.warning("Invalid auto-save count dictionary, returning 0")
            return 0

    def is_auto_save(self, info_type: str, threshold: int = 2) -> bool:
        """
        Check if auto-save threshold is reached
        
        :param info_type: Info type
        :param threshold: Threshold (default 2)
        :return: Whether threshold is reached
        """
        count = self.get_auto_save_count(info_type)
        result = count >= threshold
        
        logger.debug(
            f"Auto-save threshold check - type: {info_type}, count: {count}, "
            f"threshold: {threshold}, result: {result}"
        )
        
        return result

    def close(self) -> None:
        """Clean up resources"""
        try:
            self._save_config()
        except Exception as e:
            logger.error(f"Failed to save configuration on close: {e}", exc_info=True)
        
        self.pending_confirmations.clear()
        logger.info(f"UserData instance closed - user ID: {self.user_id}")

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
        if exc_type:
            logger.error(f"UserData instance exited with exception: {exc_type}: {exc_val}", exc_info=True)

if __name__ == "__main__":
    with UserData(user_id='user123') as ud1:
        phone = '13800138000'
        encrypted_phone = ud1.encrypt_sensitive(phone)
        print(f"\nOriginal phone: {phone}")
        print(f"Encrypted: {encrypted_phone}")
        decrypted_phone = ud1.decrypt_sensitive(encrypted_phone)
        print(f"Decrypted: {decrypted_phone}")
        assert decrypted_phone == phone, "Encryption/decryption failed"

        ud1.set_config('phone', phone)
        cfg = ud1.get_config('phone')
        print(f"\nSaved phone config: {cfg}")
        assert ud1.decrypt_sensitive(cfg) == phone, "Config encryption failed"

        ud1.set_preference_learning_config('low')
        pref_cfg = ud1.get_preference_learning_config()
        print(f"\nLow sensitivity preference config: {pref_cfg}")
        assert pref_cfg['min_mentions'] == 3, "Preference config setting failed"

        ud1.increment_auto_save_count('phone')
        count1 = ud1.get_auto_save_count('phone')
        print(f"\nAuto-save count 1: {count1}")
        ud1.increment_auto_save_count('phone')
        count2 = ud1.get_auto_save_count('phone')
        print(f"Auto-save count 2: {count2}")
        assert count2 == 2, "Count increment failed"
        print(f"Is auto-save (threshold 2): {ud1.is_auto_save('phone')}")
