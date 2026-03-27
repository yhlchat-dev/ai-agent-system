#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
LLM Abstract Base Class
All model clients must implement this interface to ensure unified calling method
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Union, Callable, Optional


class BaseLLM(ABC):
    """
    LLM Abstract Base Class
    All model clients must implement this interface
    """
    
    @abstractmethod
    def generate(
        self,
        prompt: str,
        system: str = "You are an intelligent assistant",
        temperature: float = 0.7,
        max_tokens: int = 1024,
        stream: bool = False,
        **kwargs
    ) -> Union[Dict[str, Any], Callable]:
        """
        Generate response
        
        :param prompt: User prompt (non-empty)
        :param system: System prompt
        :param temperature: Temperature coefficient (0.0-2.0)
        :param max_tokens: Maximum generation tokens (1-8192)
        :param stream: Whether to stream response
        :param kwargs: Other model-specific parameters
        :return: Non-streaming returns dict, streaming returns generator function
        """
        pass
    
    @abstractmethod
    def get_config_info(self) -> Dict[str, Any]:
        """
        Return configuration info (for debugging)
        
        :return: Configuration info dict
        """
        pass
    
    def close(self) -> None:
        """
        Close client (reserved resource release interface)
        Subclasses can optionally override
        """
        pass
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit (auto close)"""
        self.close()
        return False
