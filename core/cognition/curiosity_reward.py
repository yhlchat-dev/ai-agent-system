#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Curiosity Reward System (Production-Grade Final Version)
Core Features:
- Vector semantic deduplication-based curiosity reward calculation
- Multi-user data isolation
- Configuration-based threshold/weight parameter management
- Complete persistence and statistics capabilities
- Comprehensive exception handling and log monitoring
"""

import os
import hashlib
import logging
import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

log_dir = Path("logs")
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_dir / "curiosity_reward.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("CuriosityReward")

try:
    from ..memory.vector_memory import VectorMemory
except ImportError:
    try:
        from core.agent.vector_memory import VectorMemory
    except ImportError as e:
        logger.warning(f"Vector memory module import failed: {e}, using fallback mode")
        class MockVectorMemory:
            def __init__(self, persist_directory: str):
                self.persist_directory = persist_directory
            
            def find_similar(self, query_text: str, n_results: int, threshold: float) -> List[Dict]:
                return []
            
            def add_memory(self, doc_id: str, topic: str, content_summary: str, metadata: Dict):
                pass
            
            def get_total_count(self) -> int:
                return 0
            
            def close(self):
                pass
        
        VectorMemory = MockVectorMemory

try:
    from .curiosity_config import CuriosityConfig
except ImportError as e:
    logger.warning(f"Config system import failed: {e}, using built-in default config")
    class SimpleCuriosityConfig:
        DEFAULT_SETTINGS = {
            "repeat_threshold": 0.85,
            "base_score_weight": 10.0
        }
        
        def __init__(self, config_dir: str):
            self.settings = self.DEFAULT_SETTINGS.copy()
        
        def get_setting(self, key: str, default: Any = None) -> Any:
            return self.settings.get(key, default)
        
        def set_setting(self, key: str, value: Any):
            self.settings[key] = value
    
    CuriosityConfig = SimpleCuriosityConfig

class CuriosityRewardSystem:
    """
    Curiosity Reward System (Full Upgrade Version)
    Core Features:
    - Vector semantic deduplication support (based on VectorMemory)
    - Integrated configuration system with dynamically adjustable thresholds
    - Comprehensive parameter validation and exception handling
    - Optimized database operations (connection reuse, context managers)
    - Fully backward compatible with original CLI interface
    - Multi-user data isolation
    """
    
    def __init__(self, user_id: str, data_dir: Path, ltm: Optional[Any] = None):
        """
        Initialize Curiosity Reward System
        :param user_id: User ID (data isolation)
        :param data_dir: Data storage directory
        :param ltm: Long-term memory instance (optional, for backup)
        :raises ValueError: User ID is empty or data directory type error
        :raises RuntimeError: Database initialization failed
        """
        if not isinstance(user_id, str) or user_id.strip() == "":
            raise ValueError("user_id must be a non-empty string")
        if not isinstance(data_dir, Path):
            try:
                data_dir = Path(data_dir)
            except (TypeError, ValueError):
                raise ValueError("data_dir must be a Path object or convertible to Path string")
        
        self.user_id = user_id.strip()
        self.data_dir = data_dir
        self.ltm = ltm
        
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.db_path = self.data_dir / "curiosity_rewards.db"
        self._init_db()
        
        self.config = CuriosityConfig(config_dir=str(self.data_dir))
        self.similarity_threshold = self.config.get_setting("repeat_threshold", 0.85)
        logger.info(f"Semantic deduplication threshold loaded: {self.similarity_threshold}")
        
        self.vector_memory: Optional[Any] = None
        vector_db_path = self.data_dir / "vector_db"
        try:
            self.vector_memory = VectorMemory(persist_directory=str(vector_db_path))
            logger.info("Vector memory system loaded successfully (Semantic Deduplication Enabled)")
        except Exception as e:
            logger.error(f"Vector memory loading failed: {e}")
            self.vector_memory = None

    def _init_db(self) -> None:
        """
        Initialize SQLite database (idempotent design)
        :raises RuntimeError: Database initialization failed
        """
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                c = conn.cursor()
                c.execute('''CREATE TABLE IF NOT EXISTS rewards
                             (id INTEGER PRIMARY KEY AUTOINCREMENT,
                              user_id TEXT NOT NULL,
                              topic TEXT NOT NULL,
                              content_hash TEXT NOT NULL,
                              novelty_score REAL NOT NULL,
                              is_semantic_duplicate BOOLEAN NOT NULL DEFAULT 0,
                              similarity_score REAL NOT NULL DEFAULT 0.0,
                              reward_score REAL NOT NULL DEFAULT 0.0,
                              timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
                c.execute('CREATE INDEX IF NOT EXISTS idx_rewards_user_id ON rewards(user_id)')
                c.execute('CREATE INDEX IF NOT EXISTS idx_rewards_timestamp ON rewards(timestamp)')
                c.execute('CREATE INDEX IF NOT EXISTS idx_rewards_content_hash ON rewards(content_hash)')
                conn.commit()
            logger.info(f"Database initialized: {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"SQLite database initialization failed: {e}")
            raise RuntimeError(f"Cannot initialize database {self.db_path}") from e
        except Exception as e:
            logger.error(f"Database initialization exception: {e}")
            raise RuntimeError(f"Database initialization failed: {str(e)}") from e

    def _get_db_connection(self) -> sqlite3.Connection:
        """
        Get optimized database connection
        :return: SQLite connection object
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def calculate_reward(self, topic: str, content: str) -> Dict[str, float]:
        """
        Calculate curiosity reward score (core method)
        :param topic: Exploration topic (non-empty string)
        :param content: Exploration content (non-empty string)
        :return: Reward calculation result dict containing novelty_score/is_duplicate/similarity_score/reward
        :raises ValueError: topic or content is empty string
        """
        if not isinstance(topic, str) or topic.strip() == "":
            raise ValueError("topic must be a non-empty string")
        if not isinstance(content, str) or content.strip() == "":
            raise ValueError("content must be a non-empty string")
        
        topic = topic.strip()
        content = content.strip()

        is_duplicate = False
        similarity_score = 0.0
        novelty_score = 1.0
        reward_score = 0.0

        if self.vector_memory:
            try:
                query_text = f"{topic}: {content}"
                similar_items = self.vector_memory.find_similar(
                    query_text=query_text,
                    n_results=1,
                    threshold=self.similarity_threshold
                )
                
                if similar_items and len(similar_items) > 0:
                    is_duplicate = True
                    top_match = similar_items[0]
                    similarity_score = float(top_match.get('similarity', 0.0))
                    
                    penalty_factor = min(1.0, similarity_score)
                    novelty_score = max(0.0, 1.0 - penalty_factor)
                    
                    logger.info(
                        f"[Semantic Dedup] "
                        f"'{topic[:20]}...' similar to historical content (similarity: {similarity_score:.2f})"
                        f"-> novelty: {novelty_score:.2f}"
                    )
                else:
                    novelty_score = 1.0
                    doc_id = (
                        f"rew_{self.user_id}_"
                        f"{int(datetime.now().timestamp())}_"
                        f"{hashlib.md5(content.encode()).hexdigest()[:8]}"
                    )
                    self.vector_memory.add_memory(
                        doc_id=doc_id,
                        topic=topic,
                        content_summary=query_text,
                        metadata={
                            "user_id": self.user_id,
                            "timestamp": datetime.now().isoformat(),
                            "topic": topic
                        }
                    )
                    logger.info(f"[New Discovery] '{topic[:20]}...' is new content -> novelty: {novelty_score:.2f}")
            except Exception as e:
                logger.error(f"Semantic similarity detection failed: {e}, using fallback mode")
                novelty_score = 0.5
        else:
            novelty_score = 0.5
            logger.warning("No vector memory, using fallback mode for reward calculation")

        reward_weight = float(self.config.get_setting("base_score_weight", 10.0))
        reward_score = novelty_score * reward_weight

        self._log_to_db(
            topic=topic,
            content=content,
            novelty_score=novelty_score,
            is_dup=is_duplicate,
            sim_score=similarity_score,
            reward_score=reward_score
        )

        return {
            "novelty_score": round(novelty_score, 4),
            "is_duplicate": is_duplicate,
            "similarity_score": round(similarity_score, 4),
            "reward": round(reward_score, 4)
        }

    def _log_to_db(self, topic: str, content: str, novelty_score: float, 
                  is_dup: bool, sim_score: float, reward_score: float) -> None:
        """
        Log reward data to database
        :param topic: Exploration topic
        :param content: Exploration content
        :param novelty_score: Novelty score
        :param is_dup: Whether semantic duplicate
        :param sim_score: Similarity score
        :param reward_score: Final reward score
        """
        try:
            content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
            
            with self._get_db_connection() as conn:
                c = conn.cursor()
                c.execute('''INSERT INTO rewards 
                             (user_id, topic, content_hash, novelty_score, 
                              is_semantic_duplicate, similarity_score, reward_score)
                             VALUES (?, ?, ?, ?, ?, ?, ?)''',
                          (self.user_id, topic, content_hash, float(novelty_score),
                           int(is_dup), float(sim_score), float(reward_score)))
                conn.commit()
            logger.debug(
                f"Reward record saved - "
                f"topic: {topic[:20]}... | reward: {reward_score:.2f} | "
                f"duplicate: {is_dup} | novelty: {novelty_score:.2f}"
            )
        except sqlite3.Error as e:
            logger.error(f"SQLite database record failed: {e}")
        except Exception as e:
            logger.error(f"Database record failed: {e}")

    def get_current_status(self) -> Dict[str, Any]:
        """
        Backward compatible: Provides status structure required by legacy interface.
        Based on database statistics for approximate mapping:
        - month: Current year-month
        - total_score: Cumulative reward score (total_reward)
        - decayed_base: 0.0 (no decay model, reserved field)
        - this_month_raw: 0.0 (can be extended with SQL for precise monthly summary)
        - explorations: Total exploration count
        - failed_but_novel: 0 (no failure flag source, reserved field)
        - repeat_penalties: Semantic duplicate count
        """
        stats = self.get_stats()
        return {
            "month": datetime.now().strftime("%Y-%m"),
            "total_score": stats.get("total_reward", 0.0),
            "decayed_base": 0.0,
            "this_month_raw": 0.0,
            "explorations": stats.get("total_explorations", 0),
            "failed_but_novel": 0,
            "repeat_penalties": stats.get("semantic_duplicates", 0)
        }

    def record_exploration(self, topic: str, novelty: float, quality: float, is_failed: bool):
        """
        Backward compatible: Accepts legacy call parameters, internally calculates via calculate_reward,
        and returns ExplorationRecord structure with reasonable field mapping.
        """
        try:
            content = f"novelty:{novelty:.2f}; quality:{quality:.2f}; failed:{is_failed}"
            result = self.calculate_reward(topic=topic, content=content)
            penalty = 10.0 if result.get("is_duplicate") else 0.0
            bonus = 0.0
            similarity = result.get("similarity_score", 0.0)
            final_score = float(result.get("reward", 0.0))

            from .curiosity_core import ExplorationRecord
            rec = ExplorationRecord(
                topic=topic,
                novelty_score=float(result.get("novelty_score", novelty)),
                quality_score=float(quality),
                is_failed=bool(is_failed),
                final_score=float(final_score),
                penalty=float(penalty),
                bonus=float(bonus),
                similarity_to_past=float(similarity)
            )
            return rec
        except Exception as e:
            logger.error(f"Failed to record exploration data: {e}")
            raise

    def get_stats(self) -> Dict[str, Any]:
        """
        Get reward system statistics
        :return: Dictionary containing various statistical metrics
        """
        stats = {
            "user_id": self.user_id,
            "total_explorations": 0,
            "semantic_duplicates": 0,
            "unique_explorations": 0,
            "unique_rate": 1.0,
            "average_reward": 0.0,
            "total_reward": 0.0,
            "vector_memory_size": 0,
            "similarity_threshold": self.similarity_threshold
        }
        
        try:
            with self._get_db_connection() as conn:
                c = conn.cursor()
                
                c.execute("SELECT COUNT(*) FROM rewards WHERE user_id = ?", (self.user_id,))
                total = int(c.fetchone()[0])
                stats["total_explorations"] = total
                
                c.execute("""SELECT COUNT(*) FROM rewards 
                             WHERE user_id = ? AND is_semantic_duplicate = 1""", (self.user_id,))
                dups = int(c.fetchone()[0])
                stats["semantic_duplicates"] = dups
                
                stats["unique_explorations"] = total - dups
                stats["unique_rate"] = round((total - dups) / total, 4) if total > 0 else 1.0
                
                c.execute("""SELECT AVG(reward_score) FROM rewards 
                             WHERE user_id = ?""", (self.user_id,))
                avg_reward = c.fetchone()[0] or 0.0
                stats["average_reward"] = round(float(avg_reward), 4)
                
                c.execute("""SELECT SUM(reward_score) FROM rewards 
                             WHERE user_id = ?""", (self.user_id,))
                total_reward = c.fetchone()[0] or 0.0
                stats["total_reward"] = round(float(total_reward), 4)

            if self.vector_memory:
                try:
                    stats["vector_memory_size"] = self.vector_memory.get_total_count()
                except Exception as e:
                    logger.warning(f"Failed to get vector memory count: {e}")
            
            logger.debug(f"Statistics retrieved successfully - user: {self.user_id} | total explorations: {total}")
            
        except sqlite3.Error as e:
            logger.error(f"SQLite statistics query failed: {e}")
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
        
        return stats

    def update_similarity_threshold(self, new_threshold: float) -> None:
        """
        Dynamically update semantic similarity threshold
        :param new_threshold: New threshold (between 0.0-1.0)
        :raises ValueError: Threshold is not a number or out of range
        """
        if not isinstance(new_threshold, (int, float)):
            raise ValueError("Threshold must be a number (int/float)")
        new_threshold = float(new_threshold)
        if new_threshold < 0.0 or new_threshold > 1.0:
            raise ValueError("Threshold must be between 0.0-1.0")
        
        self.similarity_threshold = new_threshold
        self.config.set_setting("repeat_threshold", new_threshold)
        logger.info(f"Semantic similarity threshold updated to: {new_threshold}")

    def close(self) -> None:
        """Safely close all resources"""
        if hasattr(self, 'vector_memory') and self.vector_memory:
            try:
                self.vector_memory.close()
                logger.info("Vector memory resources released")
            except Exception as e:
                logger.error(f"Failed to release vector memory resources: {e}")
        
        logger.info("CuriosityReward resources safely closed")

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit (auto-close resources)"""
        self.close()
        if exc_type:
            logger.error(
                f"CuriosityReward execution exception - "
                f"type: {exc_type.__name__} | message: {exc_val}",
                exc_info=(exc_type, exc_val, exc_tb)
            )


if __name__ == "__main__":
    import shutil
    
    test_user_id = "test_user_001"
    test_data_dir = Path("./test_curiosity_data")
    
    try:
        with CuriosityReward(test_user_id, test_data_dir) as reward_sys:
            result1 = reward_sys.calculate_reward(
                topic="Research on new applications of quantum entanglement",
                content="Quantum entanglement can be used for ultra-secure quantum communication, breaking through the limitations of traditional encryption technology"
            )
            print(f"Test 1 - New content reward result:\n{result1}\n")
            
            result2 = reward_sys.calculate_reward(
                topic="Research on new applications of quantum entanglement",
                content="Quantum entanglement can be applied to quantum communication, improving encryption security"
            )
            print(f"Test 2 - Similar content reward result:\n{result2}\n")
    except Exception as e:
        print(f"Test failed: {e}")
    finally:
        # Clean up test data
        if test_data_dir.exists():
            shutil.rmtree(test_data_dir)
        print("Test completed and cleaned up")
