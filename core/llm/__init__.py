# -*- coding: utf-8 -*-
"""
LLM Unified Access Layer - Package Initialization File
=======================================================
Provides unified calling interface for mainstream LLMs, including:
- Abstract base class: BaseLLM
- Unified client class: LLMClient
- Factory class: LLMFactory
- Quick access functions for 10 mainstream models

Exception Handling:
- Logs warnings on import failure, ensures basic package availability
- Missing components are marked as None for runtime checking
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

__version__ = "1.1.0"
__author__ = "LLM Client Team"
__description__ = "Unified access layer for mainstream large language models"

BaseLLM: Optional[object] = None
LLMClient: Optional[object] = None
LLMFactory: Optional[object] = None

tongyi = None
deepseek = None
xinghuo = None
qwen = None
zhipu = None
openai = None
claude = None
gemini = None
llama2 = None
xai = None

get_llm_client = None

try:
    from .base import BaseLLM as _BaseLLM
    BaseLLM = _BaseLLM
    
    from .llm_client import (
        LLMClient as _LLMClient,
        tongyi as _tongyi,
        deepseek as _deepseek,
        xinghuo as _xinghuo,
        qwen as _qwen,
        zhipu as _zhipu,
        openai as _openai,
        claude as _claude,
        gemini as _gemini,
        llama2 as _llama2,
        xai as _xai,
    )
    
    from .factory import (
        LLMFactory as _Factory,
        get_llm_client as _get_llm_client,
    )
    
    LLMClient = _LLMClient
    LLMFactory = _Factory
    tongyi = _tongyi
    deepseek = _deepseek
    xinghuo = _xinghuo
    qwen = _qwen
    zhipu = _zhipu
    openai = _openai
    claude = _claude
    gemini = _gemini
    llama2 = _llama2
    xai = _xai
    get_llm_client = _get_llm_client
    
    logger.info("LLM client components imported successfully")

except ImportError as e:
    logger.warning(f"Partial LLM client components import failed: {e}")
    logger.warning("Missing components will be set to None, please check dependencies before use")

except Exception as e:
    logger.error(f"LLM client components import exception: {e}", exc_info=True)

__all__ = [
    "BaseLLM",
    "LLMClient",
    "LLMFactory",
    "get_llm_client",
    "tongyi",
    "deepseek",
    "xinghuo",
    "qwen",
    "zhipu",
    "openai",
    "claude",
    "gemini",
    "llama2",
    "xai",
    "__version__",
    "__author__",
]

def check_availability() -> dict:
    """
    Check component availability
    Returns: Dictionary of component availability status
    """
    return {
        "BaseLLM": BaseLLM is not None,
        "LLMClient": LLMClient is not None,
        "LLMFactory": LLMFactory is not None,
        "get_llm_client": get_llm_client is not None,
        "tongyi": tongyi is not None,
        "deepseek": deepseek is not None,
        "xinghuo": xinghuo is not None,
        "qwen": qwen is not None,
        "zhipu": zhipu is not None,
        "openai": openai is not None,
        "claude": claude is not None,
        "gemini": gemini is not None,
        "llama2": llama2 is not None,
        "xai": xai is not None,
        "version": __version__,
    }

if __name__ == "__main__":
    import pprint
    print("=== LLM Client Component Status ===")
    pprint.pprint(check_availability())
