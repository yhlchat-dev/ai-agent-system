# -*- coding: utf-8 -*-
"""
API Adapter Base Class + Token Bucket Rate Limiter: Foundation for all third-party API adapters
"""
import time
from abc import ABC, abstractmethod

class TokenBucket:
    """Token Bucket Rate Limiter: Control API call frequency"""
    def __init__(self, rate, capacity):
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_refill = time.time()

    def consume(self, tokens=1):
        """Consume tokens, return whether successful"""
        now = time.time()
        delta = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + delta * self.rate)
        self.last_refill = now
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

class BaseAPIAdapter(ABC):
    """API Adapter Base Class: Unified third-party API call specification"""
    def __init__(self, name, config, security=None):
        self.name = name
        self.config = config
        self.security = security

    def _decrypt(self, value):
        """Decrypt sensitive information in config"""
        if self.security and SECURITY_AVAILABLE and value and isinstance(value, str):
            try:
                return decrypt_data(value)
            except Exception:
                return value
        return value

    @abstractmethod
    def call(self, **kwargs):
        """Execute API call, subclass must implement"""
        pass
