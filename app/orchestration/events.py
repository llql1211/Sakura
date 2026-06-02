from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.llm.api_client import ChatMessage
from app.orchestration.route_modes import DEFAULT_ROUTE_MODE, RouteMode


DecisionSource = Literal[
    "user_message",
    "proactive_tick",
    "screen_snapshot",
    "reminder_due",
]
DecisionRoute = Literal[
    "silent",
    "roleplay_chat",
    "observe_screen",
    "agent_task",
    "ask_confirm",
]
RiskLevel = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class DecisionInput:
    """DecisionLayer 的标准输入，避免直接依赖 UI 或 AgentRuntime 内部状态。"""

    source: DecisionSource
    user_text: str | None = None
    messages: list[ChatMessage] = field(default_factory=list)
    recent_dialogue: list[ChatMessage] = field(default_factory=list)
    visible_state_summary: str | None = None
    app_state: dict[str, Any] = field(default_factory=dict)
    route_mode: RouteMode = DEFAULT_ROUTE_MODE


@dataclass(frozen=True)
class SakuraDecision:
    """Sakura 的路由结果。"""

    route: DecisionRoute
    reason: str
    should_ack: bool = False
    needs_screen: bool = False
    emotion_hint: str | None = None
    risk_level: RiskLevel = "low"

    @property
    def requires_agent(self) -> bool:
        return self.route in {"agent_task", "observe_screen", "ask_confirm"}
