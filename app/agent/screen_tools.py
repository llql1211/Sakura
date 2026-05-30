from __future__ import annotations

from typing import Any

from app.agent.tool_registry import Tool


OBSERVE_SCREEN_TOOL_NAME = "observe_screen"
SCREEN_OBSERVATION_REQUEST_ACTION = "screen_observation_request"
SCREEN_OBSERVATION_CAPABILITY = "screen_observation"
SCREEN_OBSERVATION_DISABLED_ERROR = "模型视觉未启用，或本轮已经提供过屏幕截图。"


def create_screen_observation_tool() -> Tool:
    """创建屏幕观察请求工具；实际截图仍由 UI 层执行。"""
    return Tool(
        name=OBSERVE_SCREEN_TOOL_NAME,
        description="请求获取当前屏幕截图。仅当用户问题需要当前界面、窗口内容或视觉状态时使用。",
        parameters={
            "type": "object",
            "properties": {},
        },
        handler=request_screen_observation,
        requires_confirmation=False,
        group="screen",
        risk="low",
        capability=SCREEN_OBSERVATION_CAPABILITY,
    )


def request_screen_observation(_arguments: dict[str, Any]) -> dict[str, str]:
    """返回屏幕观察请求，由 Runtime 转成 UI action，避免在工具层依赖 QWidget。"""
    return {"action": SCREEN_OBSERVATION_REQUEST_ACTION}
