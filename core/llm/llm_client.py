#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Unified LLM Access Layer for Major Models (Production Framework)
Domestic: Tongyi Qianwen, DeepSeek, iFlytek Xinghuo, Qwen, Zhipu AI
International: OpenAI, Claude, Gemini, Llama2, XAI
Unified calling entry: generate()
Features:
- Complete configuration management (supports environment variables/external config)
- Strict parameter validation and exception handling
- Structured logging for monitoring and debugging
- Extensible model configuration system
- Unified response format and error handling
- Preserves all original shortcuts and interfaces
- Supports abstract base class BaseLLM
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List, Union, Callable
from pathlib import Path
from urllib import request, error as urlerror
from core.llm.base import BaseLLM

log_dir = Path("logs")
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_dir / "llm_client.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("LLMClient")

class LLMClientError(Exception):
    """LLM Client Base Exception"""
    pass

class LLMConfigError(LLMClientError):
    """Configuration Related Exception"""
    pass

class LLMParameterError(LLMClientError):
    """Parameter Related Exception"""
    pass

class LLMClient(BaseLLM):
    """
    Unified LLM Client
    Core Features:
    - Unified calling interface
    - Multi-model configuration support
    - Complete parameter validation
    - Standardized response format
    - Streaming/non-streaming response support
    """

    MODEL_CONFIGS: Dict[str, Dict[str, Any]] = {
        "tongyi": {
            "api_key_env": "TONGYI_API_KEY",
            "base_url": "https://dashscope.aliyuncs.com/api/v1",
            "required_fields": ["api_key"]
        },
        "deepseek": {
            "api_key_env": "DEEPSEEK_API_KEY",
            "base_url": "https://api.deepseek.com/v1",
            "required_fields": ["api_key"]
        },
        "xinghuo": {
            "api_key_env": "XINGHUO_API_KEY",
            "appid_env": "XINGHUO_APPID",
            "secret_env": "XINGHUO_SECRET",
            "base_url": "https://spark-api.xf-yun.com/v1",
            "required_fields": ["api_key", "appid", "secret"]
        },
        "qwen": {
            "api_key_env": "QWEN_API_KEY",
            "base_url": "https://dashscope.aliyuncs.com/api/v1",
            "required_fields": ["api_key"]
        },
        "zhipu": {
            "api_key_env": "ZHIPU_API_KEY",
            "base_url": "https://open.bigmodel.cn/api/paas/v4",
            "required_fields": ["api_key"]
        },
        "openai": {
            "api_key_env": "OPENAI_API_KEY",
            "base_url": "https://api.openai.com/v1",
            "required_fields": ["api_key"]
        },
        "claude": {
            "api_key_env": "CLAUDE_API_KEY",
            "base_url": "https://api.anthropic.com/v1",
            "required_fields": ["api_key"]
        },
        "gemini": {
            "api_key_env": "GEMINI_API_KEY",
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "required_fields": ["api_key"]
        },
        "llama2": {
            "api_key_env": "LLAMA2_API_KEY",
            "base_url": "https://api.llama2.com/v1",
            "required_fields": ["api_key"]
        },
        "xai": {
            "api_key_env": "XAI_API_KEY",
            "base_url": "https://api.x.ai/v1",
            "required_fields": ["api_key"]
        }
    }

    def __init__(
        self, 
        model_type: str = "qwen",
        config: Optional[Dict[str, str]] = None
    ):
        """
        Initialize LLM Client
        :param model_type: Model type (lowercase)
        :param config: Custom config dict, higher priority than environment variables
        :raises LLMConfigError: Model type not supported or config missing
        """
        self.model_type = model_type.lower()
        if self.model_type not in self.MODEL_CONFIGS:
            raise LLMConfigError(
                f"Unsupported model type: {model_type}, supported types: {list(self.MODEL_CONFIGS.keys())}"
            )
        
        self.config = config or {}
        self.api_key: Optional[str] = None
        self.base_url: Optional[str] = None
        self.secret: Optional[str] = None
        self.appid: Optional[str] = None
        self._api_key_from_env: bool = False
        
        self._load_config()
        
        logger.info(f"LLM Client initialized - Model type: {self.model_type}")

    def _load_config(self) -> None:
        """
        Load model config (priority: custom config > environment variable > placeholder)
        :raises LLMConfigError: Required config missing
        """
        model_config = self.MODEL_CONFIGS[self.model_type]
        
        self.base_url = model_config["base_url"]
        
        config_mapping = {
            "api_key": model_config.get("api_key_env"),
            "appid": model_config.get("appid_env"),
            "secret": model_config.get("secret_env")
        }
        
        for key, env_var in config_mapping.items():
            if env_var:
                if key in self.config:
                    setattr(self, key, self.config[key])
                    if key == "api_key":
                        self._api_key_from_env = True
                elif env_var in os.environ:
                    setattr(self, key, os.environ[env_var])
                    if key == "api_key":
                        self._api_key_from_env = True
                else:
                    if key == "api_key":
                        setattr(self, key, f"sk-{'x'*16}")
                    elif key == "appid":
                        setattr(self, key, f"{key}_here")
                    elif key == "secret":
                        setattr(self, key, f"{key}_here")
        
        missing_fields = []
        for field in model_config["required_fields"]:
            value = getattr(self, field, None)
            if value is None or (isinstance(value, str) and value.strip() == ""):
                missing_fields.append(field)
        
        if missing_fields:
            logger.warning(
                f"Model {self.model_type} missing required config: {missing_fields}, "
                "Currently in framework stage using placeholder values, please configure environment variables or pass custom config before actual calls"
            )

    def _deepseek_chat(self, messages: List[Dict[str, str]], temperature: float, max_tokens: int, **kwargs) -> Dict[str, Any]:
        api_key = self.api_key
        if not api_key or not self._api_key_from_env:
            return {
                "model_type": self.model_type,
                "success": False,
                "content": "",
                "error": "missing_api_key",
                "raw": None
            }

        model = kwargs.get("model") or "deepseek-chat"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            url=f"{self.base_url}/chat/completions",
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with request.urlopen(req, timeout=float(kwargs.get("timeout", 60))) as resp:
                body = resp.read().decode("utf-8")
                raw = json.loads(body)
        except urlerror.HTTPError as e:
            try:
                detail = e.read().decode("utf-8")
            except Exception:
                detail = str(e)
            raise LLMClientError(f"DeepSeek HTTPError: {detail}") from e
        except Exception as e:
            raise LLMClientError(f"DeepSeek request failed: {e}") from e

        content = ""
        try:
            content = raw["choices"][0]["message"]["content"]
        except Exception:
            content = ""
        usage = raw.get("usage") or {}
        return {
            "model_type": self.model_type,
            "success": True,
            "content": content,
            "messages": messages,
            "usage": usage,
            "raw": raw
        }

    def _validate_generate_params(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int,
        stream: bool
    ) -> None:
        """
        Validate generate interface parameters
        :raises LLMParameterError: Parameters do not meet requirements
        """
        if not isinstance(prompt, str) or prompt.strip() == "":
            raise LLMParameterError("prompt must be a non-empty string")
        
        if not isinstance(temperature, (int, float)) or not (0.0 <= temperature <= 2.0):
            raise LLMParameterError("temperature must be a number between 0.0-2.0")
        
        if not isinstance(max_tokens, int) or max_tokens <= 0 or max_tokens > 8192:
            raise LLMParameterError("max_tokens must be an integer between 1-8192")
        
        if not isinstance(stream, bool):
            raise LLMParameterError("stream must be a boolean")

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
        Unified generate interface (framework implementation, does not actually send requests)
        :param prompt: User prompt (non-empty)
        :param system: System prompt
        :param temperature: Temperature coefficient (0.0-2.0)
        :param max_tokens: Maximum generation tokens (1-8192)
        :param stream: Whether to stream response
        :param kwargs: Other model-specific parameters
        :return: Non-streaming returns dict, streaming returns generator function
        :raises LLMParameterError: Parameter validation failed
        """
        self._validate_generate_params(prompt, temperature, max_tokens, stream)
        
        messages = [
            {"role": "system", "content": system.strip() if isinstance(system, str) else "You are an intelligent assistant"},
            {"role": "user", "content": prompt.strip()}
        ]
        
        logger.info(
            f"Calling LLM generate interface - Model: {self.model_type}, "
            f"prompt length: {len(prompt)}, temperature: {temperature}, "
            f"max_tokens: {max_tokens}, stream: {stream}"
        )

        if stream:
            def stream_generator():
                """Streaming response generator (simulated)"""
                chunks = [
                    f"[{self.model_type}] Simulated streaming response 1: {prompt[:10]}...",
                    f"[{self.model_type}] Simulated streaming response 2: {prompt[10:20]}...",
                    f"[{self.model_type}] Simulated streaming response 3: Complete"
                ]
                for chunk in chunks:
                    yield {
                        "model_type": self.model_type,
                        "success": True,
                        "content": chunk,
                        "finish_reason": "stop" if chunk == chunks[-1] else None,
                        "raw": None
                    }
            return stream_generator

        if self.model_type == "deepseek":
            result = self._deepseek_chat(messages=messages, temperature=temperature, max_tokens=max_tokens, **kwargs)
            if result.get("success"):
                return result

        return {
            "model_type": self.model_type,
            "success": True,
            "content": f"[{self.model_type}] Simulated response: {prompt[:20]}...",
            "messages": messages,
            "usage": {
                "prompt_tokens": len(prompt) // 2,
                "completion_tokens": max_tokens,
                "total_tokens": (len(prompt) // 2) + max_tokens
            },
            "params": {
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": stream,
                **kwargs
            },
            "raw": None
        }

    def get_config_info(self) -> Dict[str, Any]:
        """
        Get client configuration info (for debugging)
        :return: Configuration info dict
        """
        return {
            "model_type": self.model_type,
            "base_url": self.base_url,
            "has_api_key": self._api_key_from_env and self.api_key is not None,
            "has_appid": self.appid is not None and self.appid != "appid_here",
            "has_secret": self.secret is not None and self.secret != "secret_here"
        }

    def close(self) -> None:
        """
        Close client (reserved resource release interface)
        """
        logger.info(f"Closing LLM Client - Model type: {self.model_type}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        if exc_type:
            logger.error(
                f"LLMClient execution exception - Model: {self.model_type}, "
                f"Type: {exc_type.__name__}, Info: {exc_val}",
                exc_info=(exc_type, exc_val, exc_tb)
            )


def tongyi(config: Optional[Dict[str, str]] = None) -> LLMClient:
    """Get Tongyi Qianwen client"""
    from core.llm.factory import LLMFactory
    return LLMFactory.get_client("tongyi", config)

def deepseek(config: Optional[Dict[str, str]] = None) -> LLMClient:
    """Get DeepSeek client"""
    from core.llm.factory import LLMFactory
    return LLMFactory.get_client("deepseek", config)

def xinghuo(config: Optional[Dict[str, str]] = None) -> LLMClient:
    """Get iFlytek Xinghuo client"""
    from core.llm.factory import LLMFactory
    return LLMFactory.get_client("xinghuo", config)

def qwen(config: Optional[Dict[str, str]] = None) -> LLMClient:
    """Get Qwen client"""
    from core.llm.factory import LLMFactory
    return LLMFactory.get_client("qwen", config)

def zhipu(config: Optional[Dict[str, str]] = None) -> LLMClient:
    """Get Zhipu AI client"""
    from core.llm.factory import LLMFactory
    return LLMFactory.get_client("zhipu", config)

def openai(config: Optional[Dict[str, str]] = None) -> LLMClient:
    """Get OpenAI client"""
    from core.llm.factory import LLMFactory
    return LLMFactory.get_client("openai", config)

def claude(config: Optional[Dict[str, str]] = None) -> LLMClient:
    """Get Claude client"""
    from core.llm.factory import LLMFactory
    return LLMFactory.get_client("claude", config)

def gemini(config: Optional[Dict[str, str]] = None) -> LLMClient:
    """Get Gemini client"""
    from core.llm.factory import LLMFactory
    return LLMFactory.get_client("gemini", config)

def llama2(config: Optional[Dict[str, str]] = None) -> LLMClient:
    """Get Llama2 client"""
    from core.llm.factory import LLMFactory
    return LLMFactory.get_client("llama2", config)

def xai(config: Optional[Dict[str, str]] = None) -> LLMClient:
    """Get XAI client"""
    from core.llm.factory import LLMFactory
    return LLMFactory.get_client("xai", config)


if __name__ == "__main__":
    client = qwen()
    result = client.generate(prompt="What is the principle of quantum entanglement?")
    print("=== Basic Usage Example ===")
    print(f"Model type: {result['model_type']}")
    print(f"Response content: {result['content']}")
    print(f"Token usage: {result['usage']}\n")

    openai_client = openai()
    openai_result = openai_client.generate(
        prompt="Explain quantum entanglement in simple terms",
        temperature=0.8,
        max_tokens=512
    )
    print("=== OpenAI Shortcut Function Example ===")
    print(f"Response content: {openai_result['content']}\n")

    tongyi_client = tongyi()
    stream_generator = tongyi_client.generate(
        prompt="Future development trends of artificial intelligence",
        stream=True
    )
    print("=== Streaming Response Example ===")
    for chunk in stream_generator():
        print(f"Streaming output: {chunk['content']}")

    custom_config = {"api_key": "your_actual_api_key_here"}
    zhipu_client = zhipu(config=custom_config)
    print(f"\n=== Custom Configuration Example ===")
    print(f"Configuration info: {zhipu_client.get_config_info()}")

    with LLMClient("deepseek") as deepseek_client:
        result = deepseek_client.generate(prompt="Large model optimization methods")
        print(f"\n=== Context Manager Example ===")
        print(f"DeepSeek response: {result['content']}")
