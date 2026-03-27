#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Patrol Manager: Call patrol tools in sequence, collect evidence and evaluate.
Optimization Features:
- Comprehensive parameter validation and exception handling
- Structured logging for monitoring and debugging
- Tool call fault tolerance (single tool failure does not affect overall flow)
- Configurable patrol steps and parameters
- More robust summary generation logic
- Fully compatible with original interface
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

log_dir = Path("logs")
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_dir / "patrol_manager.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("PatrolManager")

try:
    from core.memory.memory_assessor import assess_memory
except ImportError as e:
    logger.warning(f"Memory assessment module import failed: {e}, using Mock implementation")
    def assess_memory(evidence: list, query: str) -> Dict[str, Any]:
        return {
            "is_sufficient": len(evidence) > 0,
            "confidence": 0.8 if len(evidence) > 0 else 0.2,
            "suggested_action": "Add more information" if len(evidence) == 0 else "Information sufficient"
        }

try:
    from utils.tool_manager import ToolManager
except ImportError as e:
    logger.warning(f"Tool manager import failed: {e}, using Mock implementation")
    class MockToolManager:
        def call_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
            logger.debug(f"Mock tool call: {tool_name}, params: {kwargs}")
            return {
                "success": True,
                "data": [{"source": tool_name, "content": f"Mock data-{tool_name}", "score": 0.9}],
                "message": "Mock tool call successful"
            }
    ToolManager = MockToolManager


class PatrolManager:
    """
    Patrol Manager, responsible for executing multi-step patrols and integrating results
    Core Features:
    - Execute patrol steps strictly in sequence
    - Single tool call failure does not affect overall flow
    - Comprehensive exception handling and log monitoring
    - Configurable patrol parameters
    - Compatible with original interface
    """

    DEFAULT_PATROL_STEPS: List[Tuple[str, Dict[str, Any]]] = [
        ("patrol_recent", {"days": 7, "max_results": 5}),
        ("patrol_facts", {"max_results": 5}),
        ("patrol_knowledge", {"max_results": 5})
    ]

    def __init__(self, tool_manager: ToolManager, user_id: str = 'default') -> None:
        """
        Initialize Patrol Manager
        :param tool_manager: Tool manager instance
        :param user_id: User identifier (for data isolation)
        :raises TypeError: tool_manager is not a ToolManager instance
        :raises ValueError: user_id is empty string
        """
        if not isinstance(tool_manager, ToolManager):
            raise TypeError(f"tool_manager must be a ToolManager instance, current type: {type(tool_manager)}")
        if not isinstance(user_id, str) or user_id.strip() == "":
            raise ValueError("user_id must be a non-empty string")

        self.tm = tool_manager
        self.user_id = user_id.strip()
        self.patrol_steps = self.DEFAULT_PATROL_STEPS.copy()
        
        logger.info(f"Patrol Manager initialized - user ID: {self.user_id}, patrol steps: {len(self.patrol_steps)}")

    def set_patrol_steps(self, steps: List[Tuple[str, Dict[str, Any]]]) -> None:
        """
        Customize patrol steps
        :param steps: Patrol steps list, format: [(tool_name, default_params), ...]
        :raises ValueError: Step format error
        """
        for idx, (tool_name, params) in enumerate(steps):
            if not isinstance(tool_name, str) or tool_name.strip() == "":
                raise ValueError(f"Step {idx+1} tool name cannot be empty")
            if not isinstance(params, dict):
                raise ValueError(f"Step {idx+1} parameters must be a dictionary type")
        
        self.patrol_steps = steps
        logger.info(f"Patrol steps updated - new steps count: {len(self.patrol_steps)}")

    def patrol(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute patrol process, call tools strictly in sequence
        :param query: User's original query (non-empty string)
        :param context: Additional context (optional)
        :return: Evaluated comprehensive report (guaranteed non-empty dictionary)
        :raises ValueError: query is empty string
        """
        if not isinstance(query, str) or query.strip() == "":
            raise ValueError("query must be a non-empty string")
        if context is None:
            context = {}
        elif not isinstance(context, dict):
            logger.warning(f"context must be a dictionary type, current type: {type(context)}, converted to empty dictionary")
            context = {}
        
        query = query.strip()
        all_evidence = []
        tool_call_results = {}

        logger.info(f"Starting patrol process - user ID: {self.user_id}, query: {query[:50]}...")

        for step_idx, (tool_name, default_params) in enumerate(self.patrol_steps, 1):
            try:
                logger.debug(f"Executing patrol step {step_idx} - tool: {tool_name}")
                
                tool_params = {
                    "user_id": self.user_id,
                    **default_params
                }
                
                if tool_name == "patrol_facts":
                    tool_params["keywords"] = query
                elif tool_name == "patrol_knowledge":
                    tool_params["query"] = query
                
                result = self.tm.call_tool(tool_name, **tool_params)
                tool_call_results[tool_name] = result
                
                if isinstance(result, dict):
                    if result.get("success") and isinstance(result.get("data"), list):
                        valid_evidence = [e for e in result["data"] if isinstance(e, dict)]
                        all_evidence.extend(valid_evidence)
                        logger.info(f"Patrol step {step_idx} complete - tool: {tool_name}, valid evidence: {len(valid_evidence)}")
                    else:
                        logger.warning(f"Patrol step {step_idx} has no valid data - tool: {tool_name}, result: {result.get('message', 'no message')}")
                else:
                    logger.error(f"Patrol step {step_idx} result format error - tool: {tool_name}, result type: {type(result)}")
            
            except Exception as e:
                tool_call_results[tool_name] = {
                    "success": False,
                    "error": str(e),
                    "data": []
                }
                logger.error(f"Patrol step {step_idx} execution failed - tool: {tool_name}, exception: {e}", exc_info=True)

        try:
            assessment = assess_memory(all_evidence, query)
            if not isinstance(assessment, dict):
                logger.warning(f"Evidence assessment result format error, using default assessment - result type: {type(assessment)}")
                assessment = {
                    "is_sufficient": len(all_evidence) > 0,
                    "confidence": 0.0,
                    "suggested_action": "Assessment failed, please check data"
                }
        except Exception as e:
            logger.error(f"Evidence assessment failed - exception: {e}", exc_info=True)
            assessment = {
                "is_sufficient": len(all_evidence) > 0,
                "confidence": 0.0,
                "error": str(e),
                "suggested_action": "Assessment process error, suggest retry"
            }

        try:
            summary = self._generate_summary(all_evidence, assessment)
        except Exception as e:
            logger.error(f"Summary generation failed - exception: {e}", exc_info=True)
            summary = f"Summary generation failed, collected {len(all_evidence)} evidence items"

        final_report = {
            "status": "success" if assessment.get("is_sufficient", False) else "insufficient",
            "summary": summary,
            "evidence": all_evidence,
            "assessment": assessment,
            "tool_call_details": tool_call_results,
            "metadata": {
                "user_id": self.user_id,
                "query": query,
                "total_evidence_count": len(all_evidence),
                "patrol_steps_count": len(self.patrol_steps)
            }
        }

        logger.info(f"Patrol process complete - user ID: {self.user_id}, total evidence: {len(all_evidence)}, status: {final_report['status']}")
        return final_report

    def _generate_summary(self, evidence: list, assessment: dict) -> str:
        """
        Generate readable summary based on evidence and assessment (enhanced version)
        :param evidence: Evidence list
        :param assessment: Assessment result dictionary
        :return: Readable summary string
        """
        if not isinstance(evidence, list):
            evidence = []
        if not isinstance(assessment, dict):
            assessment = {}

        total_evidence = len(evidence)
        
        if total_evidence == 0:
            return "No relevant patrol records found, unable to evaluate query content."
        
        sources = []
        for e in evidence:
            if isinstance(e, dict) and "source" in e:
                sources.append(str(e["source"]))
        
        unique_sources = list(set(sources)) if sources else ["unknown source"]
        source_str = ", ".join(unique_sources[:5])
        if len(unique_sources) > 5:
            source_str += " etc."

        is_sufficient = assessment.get("is_sufficient", False)
        confidence = assessment.get("confidence", 0.0)
        suggested_action = assessment.get("suggested_action", "no suggestion")

        if is_sufficient:
            summary = (
                f"Found {total_evidence} relevant patrol records (sources: {source_str}), "
                f"information sufficient (confidence: {confidence:.1%})."
            )
        else:
            summary = (
                f"Found {total_evidence} patrol records (sources: {source_str}), "
                f"but information may be insufficient (confidence: {confidence:.1%}). "
                f"Suggestion: {suggested_action}"
            )

        return summary

    def close(self) -> None:
        """
        Safely close resources (if tool manager needs)
        """
        try:
            if hasattr(self.tm, 'close'):
                self.tm.close()
                logger.info("Tool manager resources released")
        except Exception as e:
            logger.error(f"Failed to release tool manager resources - exception: {e}")

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit (auto close resources)"""
        self.close()
        if exc_type:
            logger.error(
                f"PatrolManager execution exception - "
                f"type: {exc_type.__name__} | message: {exc_val}",
                exc_info=(exc_type, exc_val, exc_tb)
            )


if __name__ == "__main__":
    mock_tool_manager = ToolManager()
    
    with PatrolManager(mock_tool_manager, user_id="test_user_001") as patrol_manager:
        report = patrol_manager.patrol(
            query="Latest application research on quantum entanglement",
            context={"priority": "high"}
        )
        
        print("=== Patrol Report ===")
        print(f"Status: {report['status']}")
        print(f"Summary: {report['summary']}")
        print(f"Total Evidence: {len(report['evidence'])}")
        print(f"Assessment: {report['assessment']}")
        
        patrol_manager.set_patrol_steps([
            ("patrol_recent", {"days": 3, "max_results": 3}),
            ("patrol_facts", {"max_results": 3})
        ])
        
        report2 = patrol_manager.patrol(query="Artificial intelligence ethics issues")
        print("\n=== Custom Steps Patrol Report ===")
        print(f"Summary: {report2['summary']}")
        print(f"Metadata: {report2['metadata']}")
