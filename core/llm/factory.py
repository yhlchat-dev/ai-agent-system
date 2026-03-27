#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
LLM Factory Class
Supports dynamic model switching, hot-plugging, environment variable configuration
"""

import os
from typing import Dict, Any, Optional, Callable
from core.llm.base import BaseLLM
from core.llm.llm_client import LLMClient


class LLMFactory:
    """
    LLM Client Factory
    Supports dynamic model switching, hot-plugging, environment variable configuration
    """
    
    _models: Dict[str, Callable] = {
        "tongyi": lambda config: LLMClient("tongyi", config),
        "deepseek": lambda config: LLMClient("deepseek", config),
        "xinghuo": lambda config: LLMClient("xinghuo", config),
        "qwen": lambda config: LLMClient("qwen", config),
        "zhipu": lambda config: LLMClient("zhipu", config),
        "openai": lambda config: LLMClient("openai", config),
        "claude": lambda config: LLMClient("claude", config),
        "gemini": lambda config: LLMClient("gemini", config),
        "llama2": lambda config: LLMClient("llama2", config),
        "xai": lambda config: LLMClient("xai", config),
    }
    
    _client_cache: Dict[str, BaseLLM] = {}
    
    @classmethod
    def get_client(
        cls, 
        model_type: str, 
        config: Optional[Dict[str, str]] = None,
        use_cache: bool = True
    ) -> BaseLLM:
        """
        Get specified model client
        
        :param model_type: Model type
        :param config: Custom configuration
        :param use_cache: Whether to use cache
        :return: BaseLLM instance
        """
        model_type = model_type.lower()
        
        cache_key = f"{model_type}_{id(config)}" if config else model_type
        
        if use_cache and cache_key in cls._client_cache:
            return cls._client_cache[cache_key]
        
        if model_type not in cls._models:
            raise ValueError(
                f"Unsupported model type: {model_type}, available: {list(cls._models.keys())}"
            )
        
        client = cls._models[model_type](config)
        
        if use_cache:
            cls._client_cache[cache_key] = client
        
        return client
    
    @classmethod
    def from_env(cls, config: Optional[Dict[str, str]] = None) -> BaseLLM:
        """
        Read model name from environment variable LLM_MODEL and return corresponding client
        
        :param config: Custom configuration
        :return: BaseLLM instance
        """
        model_type = os.getenv("LLM_MODEL", "qwen")
        return cls.get_client(model_type, config)
    
    @classmethod
    def register_model(cls, name: str, builder: Callable) -> None:
        """
        Dynamically register new model
        
        :param name: Model name
        :param builder: Builder function, accepts config parameter, returns BaseLLM instance
        """
        cls._models[name.lower()] = builder
    
    @classmethod
    def unregister_model(cls, name: str) -> bool:
        """
        Unregister model
        
        :param name: Model name
        :return: Whether successful
        """
        name = name.lower()
        if name in cls._models:
            del cls._models[name]
            return True
        return False
    
    @classmethod
    def list_models(cls) -> list:
        """
        List all supported models
        
        :return: Model name list
        """
        return list(cls._models.keys())
    
    @classmethod
    def clear_cache(cls) -> None:
        """Clear client cache"""
        cls._client_cache.clear()


def get_llm_client(
    model_type: Optional[str] = None,
    config: Optional[Dict[str, str]] = None
) -> BaseLLM:
    """
    Shortcut function: Get LLM client
    
    :param model_type: Model type, None to read from environment variable
    :param config: Custom configuration
    :return: BaseLLM instance
    """
    if model_type:
        return LLMFactory.get_client(model_type, config)
    return LLMFactory.from_env(config)
