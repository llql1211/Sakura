from __future__ import annotations

from app.agent import AgentProgress
from app.orchestration import DecisionInput, DecisionLayer
from app.orchestration.coordinator import _emit_delegated_ack


def test_decision_routes_lightweight_chat_to_roleplay() -> None:
    decision = DecisionLayer().decide(
        DecisionInput(
            source="user_message",
            messages=[{"role": "user", "content": "今天有点累，陪我说会儿话"}],
        )
    )

    assert decision.route == "roleplay_chat"
    assert not decision.requires_agent


def test_decision_routes_workspace_task_to_agent() -> None:
    decision = DecisionLayer().decide(
        DecisionInput(
            source="user_message",
            messages=[{"role": "user", "content": "帮我读取 app/core/chat_worker.py 看看"}],
        )
    )

    assert decision.route == "agent_task"
    assert decision.requires_agent


def test_decision_routes_visible_browser_search_to_agent() -> None:
    decision = DecisionLayer().decide(
        DecisionInput(
            source="user_message",
            messages=[{"role": "user", "content": "打开浏览器帮我搜一下二阶堂真红的信息,我们一起来看看吧"}],
        )
    )

    assert decision.route == "agent_task"
    assert decision.should_ack


def test_browser_handoff_ack_does_not_expose_agent() -> None:
    progresses: list[AgentProgress] = []

    _emit_delegated_ack(
        progresses.append,
        "规则命中工具或外部状态任务",
        "打开浏览器帮我搜一下二阶堂真红的信息,我们一起来看看吧",
    )

    assert progresses
    assert progresses[0].reply.translation == "好我打开浏览器搜搜看"
    assert "Agent" not in progresses[0].reply.translation
    assert "后台" not in progresses[0].reply.translation


def test_decision_routes_image_message_to_screen_observation() -> None:
    decision = DecisionLayer().decide(
        DecisionInput(
            source="user_message",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "看看这张截图"},
                        {"type": "image_url", "image_url": {"url": "data:image/png;base64,xxx"}},
                    ],
                }
            ],
        )
    )

    assert decision.route == "observe_screen"
    assert decision.needs_screen


def test_decision_honors_force_route_modes() -> None:
    layer = DecisionLayer()

    chat = layer.decide(
        DecisionInput(
            source="user_message",
            messages=[{"role": "user", "content": "帮我读取文件"}],
            route_mode="chat_only",
        )
    )
    agent = layer.decide(
        DecisionInput(
            source="user_message",
            messages=[{"role": "user", "content": "只是闲聊"}],
            route_mode="force_agent",
        )
    )

    assert chat.route == "roleplay_chat"
    assert agent.route == "agent_task"
