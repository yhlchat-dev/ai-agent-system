# core/agent_brain.py
"""
Agent Brain
Coordinates configuration system and reward system, simulates complete exploration decision loop.
"""
import random
import logging
from datetime import datetime
from typing import Dict, Optional, Any
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path("logs/agent_brain.log"), encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

from core.cognition.curiosity_config import CuriosityConfig
from core.cognition.curiosity_reward import CuriosityRewardSystem
from core.cognition.curiosity_core import ExplorationRecord
from core.cognition.curiosity_reward import CuriosityRewardSystem


class AgentBrain:
    """Agent Decision Core: Coordinates configuration and reward system, handles exploration decisions"""
    def __init__(self, persist_dir: str = "./data/agent_brain"):
        logger.info("Initializing AgentBrain...")
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            self.config = CuriosityConfig(config_dir=f"{persist_dir}/config")
            
            self.reward_sys = CuriosityRewardSystem(
                user_id="system",
                data_dir=self.persist_dir
            )
        except Exception as e:
            logger.error(f"Failed to initialize config/reward system: {e}", exc_info=True)
            raise RuntimeError(f"AgentBrain init failed: {e}") from e
        
        settings = self.config.get_settings()
        reward_status = self.reward_sys.get_current_status()
        logger.info(f"Loaded config - decay_rate={settings['decay_rate']}, repeat_threshold={settings['repeat_threshold']}")
        logger.info(f"Reward system ready - current month score={reward_status['total_score']}")
        logger.info("AgentBrain initialized successfully!")
        
    def adjust_config(self, key: str, value: Any):
        """Dynamically adjust curiosity engine configuration"""
        try:
            self.config.set_setting(key, value)
            logger.info(f"AgentBrain config updated - {key}: {value}")
            return True
        except ValueError as e:
            logger.error(f"Failed to adjust config: {e}")
            return False
    
    def batch_adjust_config(self, updates: Dict[str, Any]):
        """Batch adjust configuration"""
        try:
            self.config.update_settings(updates)
            logger.info(f"AgentBrain config batch updated: {list(updates.keys())}")
            return True
        except ValueError as e:
            logger.error(f"Failed to batch adjust config: {e}")
            return False    

    def simulate_exploration(self, user_prompt: str) -> Dict[str, Any]:
        """
        Simulate a complete exploration process
        :param user_prompt: User input exploration command
        :return: Structured result containing topic, record, feedback, total score
        """
        if not isinstance(user_prompt, str) or user_prompt.strip() == "":
            logger.error("Invalid user prompt: empty or non-string")
            return {
                "topic": "",
                "record": None,
                "feedback": "Invalid command: please enter a non-empty exploration topic!",
                "current_total_score": self.reward_sys.get_current_status()['total_score']
            }
        user_prompt = user_prompt.strip()
        logger.info(f"Received exploration prompt: '{user_prompt}'")
        
        topic = f"{user_prompt} - Deep Research Edition {random.randint(1, 100)}"
        
        base_novelty = random.uniform(0.4, 0.9)
        novelty_keywords = ["new", "innovative", "first", "never before", "breakthrough"]
        if any(keyword in user_prompt.lower() for keyword in novelty_keywords):
            base_novelty = min(1.0, base_novelty + 0.15)
            logger.debug(f"Novelty boosted by keywords - new value: {base_novelty:.2f}")
        
        quality = random.uniform(0.3, 0.95)
        if len(user_prompt) > 20:
            quality = min(0.99, quality + 0.05)
        
        fail_prob = 0.1 if len(user_prompt) > 10 else 0.2
        is_failed = random.random() < fail_prob
        
        logger.debug(
            f"Simulated LLM result - topic='{topic}', novelty={base_novelty:.2f}, "
            f"quality={quality:.2f}, is_failed={is_failed}"
        )
        
        try:
            record = self.reward_sys.record_exploration(
                topic=topic,
                novelty=base_novelty,
                quality=quality,
                is_failed=is_failed
            )
        except Exception as e:
            logger.error(f"Failed to record exploration: {e}", exc_info=True)
            return {
                "topic": topic,
                "record": None,
                "feedback": f"Exploration record failed: {str(e)}",
                "current_total_score": self.reward_sys.get_current_status()['total_score']
            }
        
        feedback = self._generate_feedback(record)
        current_score = self.reward_sys.get_current_status()['total_score']
        
        logger.info(f"Exploration completed - feedback='{feedback}', current_score={current_score}")
        return {
            "topic": topic,
            "record": record.__dict__ if record else None,
            "feedback": feedback,
            "current_total_score": current_score
        }

    def _generate_feedback(self, record: ExplorationRecord) -> str:
        """Generate humanized feedback based on exploration record"""
        if not record:
            return "Invalid exploration record, cannot generate feedback!"
        
        score = record.final_score
        feedback_templates = {
            "penalty": f"Warning: This topic is highly similar to historical explorations (similarity>{record.similarity_to_past:.2f}), deducted {record.penalty} points. Suggest trying more unique research directions or refining exploration dimensions!",
            "bonus": f"Excellent attempt! Although exploration failed (status: {'failed' if record.is_failed else 'success'}), the idea is highly novel (novelty>{record.novelty_score:.2f}), extra reward of {record.bonus} points! Failure is the path to innovation.",
            "high_score": "Excellent exploration results! Perfect combination of high novelty and quality, significantly boosting total score. Keep it up!",
            "mid_score": "Stable exploration performance, maintaining good balance between novelty and quality, score growing steadily.",
            "low_score": "This exploration yielded low returns, possibly due to topic homogeneity or insufficient completion quality. Suggest focusing on niche areas or improving execution precision!",
            "failed": "Exploration failed, no points earned. Suggest analyzing failure causes, adjusting strategy and retrying!"
        }
        
        if record.penalty > 0:
            return feedback_templates["penalty"]
        elif record.bonus > 0:
            return feedback_templates["bonus"]
        elif record.is_failed:
            return feedback_templates["failed"]
        elif score >= 80:
            return feedback_templates["high_score"]
        elif score >= 50:
            return feedback_templates["mid_score"]
        else:
            return feedback_templates["low_score"]

    def get_status_report(self) -> str:
        """Generate structured agent status report (supports log output)"""
        try:
            status = self.reward_sys.get_current_status()
            config = self.config.get_settings()
            
            report_lines = [
                "=== Agent Exploration Status Report ===",
                f"Statistics Period: {status['month']} (Current Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})",
                f"Total Score: {status['total_score']:.2f}",
                f"  - Base Score After Decay: {status['decayed_base']:.2f}",    
                f"  - This Month Raw Score: {status['this_month_raw']:.2f}",    
                f"Total Explorations: {status['explorations']} times",
                f"Failed But Novel Rewards: {status['failed_but_novel']} times",
                f"Repeat Exploration Penalties: {status['repeat_penalties']} times",
                f"Current Configuration Parameters:",
                f"  - Score Decay Rate: {config['decay_rate']}",
                f"  - Repeat Penalty Value: {config['repeat_penalty']} points", 
                f"  - Repeat Threshold: {config['repeat_threshold']}",
                "========================"
            ]
            return "\n".join(report_lines)
        except Exception as e:
            return f"Failed to generate status report: {e}"
