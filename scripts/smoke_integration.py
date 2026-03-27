import time
import sys
import os
from pathlib import Path

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT_DIR)

from core.memory.memory_manager import MemoryManager
from core.memory.vector_memory import VectorMemory
from core.cognition.curiosity_reward import CuriosityRewardSystem
from core.capsules.capsule_manager import CapsuleManager
from core.capsules.agent_capsule import AgentCapsule
from core.capsules.error_capsule import ErrorCapsule
from core.tools.tool_manager import ToolManager


def _print_section(title: str):
    print("\n" + "=" * 20 + f" {title} " + "=" * 20)


def main() -> int:
    run_id = time.strftime("%Y%m%d_%H%M%S")
    base_dir = Path("data") / "_smoke" / run_id
    base_dir.mkdir(parents=True, exist_ok=True)

    user_id = "smoke_user"
    agent_id = "smoke_agent"

    ok = True

    _print_section("MemoryManager")
    try:
        mm = MemoryManager(user_id=user_id, data_dir=base_dir / "memory")
        mm.save_memory("用户手机号是13800138000，身份证622202123456789012", memory_type="user_input", source="user")
        results = mm.query_memory("用户", limit=5)
        print("query_memory_count:", len(results))
        if results:
            print("sample_memory:", results[0].get("content", "")[:120])
    except Exception as e:
        ok = False
        print("MemoryManager_failed:", e)

    _print_section("Capsules")
    try:
        cm = CapsuleManager(db_path=str(base_dir / "capsules.db"))
        c1 = AgentCapsule(agent_id=agent_id, content="{'problem':'如何优化Python性能','solution':'使用列表推导式'}", capsule_type="manual")
        cm.save_capsule(c1)
        c2 = ErrorCapsule(agent_id=agent_id, error_msg="示例异常", error_type="RuntimeError", traceback="traceback")
        cm.save_capsule(c2)
        caps = cm.get_capsules_by_agent(agent_id, limit=10)
        print("capsules_count:", len(caps))
        if caps:
            print("capsule_types:", [c.get("capsule_type") for c in caps][:10])
    except Exception as e:
        ok = False
        print("Capsules_failed:", e)

    _print_section("CuriosityRewardSystem + VectorMemory")
    try:
        reward = CuriosityRewardSystem(user_id=user_id, data_dir=base_dir / "curiosity")
        r1 = reward.calculate_reward(topic="你好，请介绍一下你自己", content="首次探索")
        r2 = reward.calculate_reward(topic="你好，请介绍一下你自己", content="再次探索")
        status = reward.get_current_status()
        print("reward_1:", r1)
        print("reward_2:", r2)
        print("status:", status)
    except Exception as e:
        ok = False
        print("CuriosityRewardSystem_failed:", e)

    try:
        vm = VectorMemory(persist_directory=str(base_dir / "vector_db"))
        vm.add_memory(doc_id="smoke_1", topic="t1", content_summary="hello world", metadata={"user_id": user_id})
        sims = vm.find_similar("hello world", n_results=3, threshold=0.2)
        print("vector_similar_count:", len(sims))
    except Exception as e:
        ok = False
        print("VectorMemory_failed:", e)

    _print_section("ToolManager + Feishu + Perception(System Tools)")
    try:
        tm = ToolManager(data_dir=base_dir / "tools")
        feishu_result = tm.call_tool("send_feishu_message", message="smoke test message")
        print("feishu_result:", feishu_result)
        unknown = tm.call_tool("unknown_tool", user_id=user_id, foo="bar")
        print("unknown_tool_result:", unknown)

        processes = tm.call_tool("list_processes")
        print("list_processes:", processes.get("success"), type(processes.get("result")).__name__)

        windows = tm.call_tool("list_windows")
        print("list_windows:", windows.get("success"), type(windows.get("result")).__name__)
    except Exception as e:
        ok = False
        print("ToolManager_failed:", e)

    _print_section("Result")
    print("base_dir:", str(base_dir))
    print("success:", ok)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

