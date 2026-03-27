#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Memory Assessor
================
Core Features:
- Analyze memory patrol results, evaluate information quality
- Determine if information is sufficient, has conflicts, or is outdated
- Calculate confidence and generate targeted action suggestions
- Support custom time thresholds and confidence rules

Design Features:
- Complete parameter validation and exception handling
- Structured log output for monitoring and debugging
- Configurable threshold constants for strategy adjustment
- Basic content conflict detection logic
- Precise type annotations and docstrings
"""

import time
import logging
from typing import List, Dict, Any, Optional, Set, Tuple

logger = logging.getLogger(__name__)

OUTDATED_DAYS = 30
FRESH_DAYS = 7
STALE_DAYS = 14

BASE_CONFIDENCE_MAX_COUNT = 10
FRESH_BOOST = 0.2
STALE_BOOST = 0.1
SUFFICIENT_CONFIDENCE_THRESHOLD = 0.5
MIN_EVIDENCE_COUNT = 1

CONFLICT_SIMILARITY_THRESHOLD = 0.7


def assess_memory(evidence: List[Dict[str, Any]], query: str) -> Dict[str, Any]:
    """
    Evaluate memory patrol evidence quality and usability
    
    :param evidence: Evidence list returned by patrol tools, each element should contain:
                     - source: Information source (str)
                     - content: Information content (str)
                     - timestamp: Timestamp (float/int, optional)
                     - metadata: Metadata (dict, optional)
    :param query: Original query string for context association
    :return: Structured evaluation result dict, containing:
             - is_sufficient: Whether there is sufficient information (bool)
             - has_conflict: Whether there is content conflict (bool)
             - is_outdated: Whether information is outdated (bool)
             - confidence: Confidence (0.0-1.0)
             - suggested_action: Suggested action (str)
             - metadata: Evaluation metadata (dict)
    :raises TypeError: Input parameter type does not meet requirements
    """
    try:
        if not isinstance(evidence, list):
            raise TypeError(f"evidence must be list type, got: {type(evidence)}")
        if not isinstance(query, str):
            raise TypeError(f"query must be string type, got: {type(query)}")
        
        if not evidence:
            logger.debug("Evaluation result: No available evidence")
            return _get_empty_evidence_result()
        
        valid_evidence = []
        for idx, item in enumerate(evidence):
            if not isinstance(item, dict):
                logger.warning(f"Ignoring invalid evidence[{idx}]: non-dict type")
                continue
            if "content" not in item or not item["content"]:
                logger.warning(f"Ignoring invalid evidence[{idx}]: missing valid content field")
                continue
            valid_evidence.append(item)
        
        if not valid_evidence:
            logger.debug("Evaluation result: No valid evidence (after filtering)")
            return _get_empty_evidence_result()
        
        timestamps: List[float] = []
        for item in valid_evidence:
            ts = item.get("timestamp")
            if ts is not None:
                try:
                    timestamps.append(float(ts))
                except (ValueError, TypeError):
                    logger.warning(f"Ignoring invalid timestamp: {ts}")
        
        now = time.time()
        newest_ts: Optional[float] = max(timestamps) if timestamps else None
        oldest_ts: Optional[float] = min(timestamps) if timestamps else None
        
        is_outdated = False
        if newest_ts:
            days_since_newest = (now - newest_ts) / (24 * 3600)
            is_outdated = days_since_newest > OUTDATED_DAYS
            logger.debug(f"Time analysis: Latest evidence is {days_since_newest:.1f} days old, outdated: {is_outdated}")
        else:
            logger.debug("Time analysis: No valid timestamps, cannot determine outdated status")
        
        has_conflict = _detect_content_conflict(valid_evidence, query)
        logger.debug(f"Conflict detection: {'Content conflict found' if has_conflict else 'No conflict'}")
        
        confidence = _calculate_confidence(
            evidence_count=len(valid_evidence),
            newest_timestamp=newest_ts,
            has_conflict=has_conflict,
            now=now
        )
        logger.debug(f"Confidence calculation result: {confidence:.2f}")
        
        is_sufficient = (
            len(valid_evidence) >= MIN_EVIDENCE_COUNT 
            and confidence >= SUFFICIENT_CONFIDENCE_THRESHOLD
            and not has_conflict
        )
        
        suggested_action = _generate_suggested_action(
            is_sufficient=is_sufficient,
            is_outdated=is_outdated,
            has_conflict=has_conflict,
            evidence_count=len(valid_evidence),
            confidence=confidence
        )
        
        sources: Set[str] = set()
        for item in valid_evidence:
            source = item.get("source")
            if source and isinstance(source, str):
                sources.add(source)
        
        metadata = {
            "sources": list(sources),
            "oldest_timestamp": oldest_ts,
            "newest_timestamp": newest_ts,
            "evidence_count": len(valid_evidence),
            "filtered_evidence_count": len(evidence) - len(valid_evidence),
            "confidence_breakdown": {
                "base": round(_calc_base_confidence(len(valid_evidence)), 2),
                "freshness_boost": round(confidence - _calc_base_confidence(len(valid_evidence)), 2),
                "conflict_penalty": -0.1 if has_conflict else 0.0
            }
        }
        
        result = {
            "is_sufficient": is_sufficient,
            "has_conflict": has_conflict,
            "is_outdated": is_outdated,
            "confidence": round(confidence, 2),
            "suggested_action": suggested_action,
            "metadata": metadata
        }
        
        logger.info(
            f"Memory assessment completed - "
            f"Sufficient: {is_sufficient}, "
            f"Conflict: {has_conflict}, "
            f"Outdated: {is_outdated}, "
            f"Confidence: {confidence:.2f}, "
            f"Valid evidence count: {len(valid_evidence)}"
        )
        
        return result
        
    except TypeError as e:
        logger.error(f"Parameter type error: {e}")
        raise
    except Exception as e:
        logger.error(f"Memory assessment process exception: {e}", exc_info=True)
        return {
            "is_sufficient": False,
            "has_conflict": False,
            "is_outdated": False,
            "confidence": 0.0,
            "suggested_action": f"Assessment process error: {str(e)}, suggest retry.",
            "metadata": {
                "sources": [],
                "oldest_timestamp": None,
                "newest_timestamp": None,
                "evidence_count": len(evidence) if isinstance(evidence, list) else 0,
                "error": str(e)
            }
        }


def _get_empty_evidence_result() -> Dict[str, Any]:
    """Generate default evaluation result for empty evidence"""
    return {
        "is_sufficient": False,
        "has_conflict": False,
        "is_outdated": False,
        "confidence": 0.0,
        "suggested_action": "No relevant information found, suggest user provide or ask for more details.",
        "metadata": {
            "sources": [],
            "oldest_timestamp": None,
            "newest_timestamp": None,
            "evidence_count": 0,
            "filtered_evidence_count": 0
        }
    }


def _calc_base_confidence(evidence_count: int) -> float:
    """Calculate base confidence (encapsulate original calc_confidence logic)"""
    try:
        from utils.helpers import calc_confidence
        return calc_confidence(evidence_count, BASE_CONFIDENCE_MAX_COUNT)
    except (ImportError, NameError):
        return min(1.0, max(0.0, evidence_count / BASE_CONFIDENCE_MAX_COUNT * 0.8))


def _calculate_confidence(
    evidence_count: int,
    newest_timestamp: Optional[float],
    has_conflict: bool,
    now: float
) -> float:
    """
    Calculate comprehensive confidence
    
    :param evidence_count: Valid evidence count
    :param newest_timestamp: Latest evidence timestamp
    :param has_conflict: Whether there is conflict
    :param now: Current timestamp
    :return: Confidence value 0.0-1.0
    """
    confidence = _calc_base_confidence(evidence_count)
    
    if newest_timestamp:
        days_since_newest = (now - newest_timestamp) / (24 * 3600)
        if days_since_newest <= FRESH_DAYS:
            confidence += FRESH_BOOST
        elif days_since_newest <= STALE_DAYS:
            confidence += STALE_BOOST
    
    if has_conflict:
        confidence -= 0.1
    
    return max(0.0, min(1.0, confidence))


def _detect_content_conflict(evidence: List[Dict[str, Any]], query: str) -> bool:
    """
    Detect if evidence content has conflicts (basic implementation)
    
    :param evidence: Valid evidence list
    :param query: Original query
    :return: Whether there is conflict
    """
    if len(evidence) < 2:
        return False
    
    query_keywords = set(query.lower().split())
    content_map: Dict[str, Set[str]] = {}
    
    for item in evidence:
        content = item["content"].lower()
        relevant_parts = []
        for word in content.split():
            if word in query_keywords or any(kw in word for kw in query_keywords):
                relevant_parts.append(word)
        
        if relevant_parts:
            content_str = " ".join(relevant_parts)
            source = item.get("source", "unknown")
            if source not in content_map:
                content_map[source] = set()
            content_map[source].add(content_str)
    
    contents = list(content_map.values())
    if len(contents) >= 2:
        first = contents[0]
        for other in contents[1:]:
            if not first.intersection(other) and len(first) > 0 and len(other) > 0:
                return True
    
    return False


def _generate_suggested_action(
    is_sufficient: bool,
    is_outdated: bool,
    has_conflict: bool,
    evidence_count: int,
    confidence: float
) -> str:
    """
    Generate targeted action suggestions
    
    :param is_sufficient: Whether information is sufficient
    :param is_outdated: Whether outdated
    :param has_conflict: Whether there is conflict
    :param evidence_count: Evidence count
    :param confidence: Confidence
    :return: Suggested action string
    """
    if has_conflict:
        return f"Found {evidence_count} conflicting pieces of information, confidence {confidence:.2f}, suggest user confirm information accuracy."
    elif is_sufficient:
        if is_outdated:
            return f"Information sufficient ({evidence_count} pieces), but may be outdated, suggest using with reference and prompting user to confirm."
        else:
            return f"Information sufficient ({evidence_count} pieces), confidence {confidence:.2f}, can use directly."
    elif is_outdated:
        return f"Information insufficient (only {evidence_count} pieces) and outdated, confidence {confidence:.2f}, suggest user provide latest information."
    elif evidence_count == 0:
        return "No relevant information found, suggest user provide or ask for more details."
    else:
        return f"Information insufficient (only {evidence_count} pieces), confidence {confidence:.2f}, suggest asking user or further exploration."


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    print("\n=== Test Case 1: Normal Fresh Data ===")
    sample_fresh = [
        {"source": "short_term", "content": "User said password is in 1Password", "timestamp": time.time() - 86400},
        {"source": "facts", "content": "Email password is app-specific password", "timestamp": time.time() - 2*86400}
    ]
    result_fresh = assess_memory(sample_fresh, "email password")
    print(f"Assessment result: {result_fresh}")
    
    print("\n=== Test Case 2: Outdated Data ===")
    sample_outdated = [
        {"source": "short_term", "content": "User said password is in 1Password", "timestamp": time.time() - 35*86400},
        {"source": "facts", "content": "Email password is app-specific password", "timestamp": time.time() - 40*86400}
    ]
    result_outdated = assess_memory(sample_outdated, "email password")
    print(f"Assessment result: {result_outdated}")
    
    print("\n=== Test Case 3: Conflicting Data ===")
    sample_conflict = [
        {"source": "short_term", "content": "User said password is in 1Password", "timestamp": time.time() - 86400},
        {"source": "facts", "content": "Email password is not in 1Password", "timestamp": time.time() - 2*86400}
    ]
    result_conflict = assess_memory(sample_conflict, "email password")
    print(f"Assessment result: {result_conflict}")
    
    print("\n=== Test Case 4: Empty Data ===")
    result_empty = assess_memory([], "email password")
    print(f"Assessment result: {result_empty}")
