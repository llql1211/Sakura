from __future__ import annotations

from typing import Literal, cast


DEFAULT_ROUTE_MODE = "auto"
ROUTE_MODE_VALUES = (
    "auto",
    "chat_only",
    "force_agent",
    "quiet",
    "proactive_only",
)
RouteMode = Literal["auto", "chat_only", "force_agent", "quiet", "proactive_only"]


def normalize_route_mode(value: str | None) -> RouteMode:
    """把外部配置中的路由模式收敛到 Sakura 支持的稳定枚举。"""

    cleaned = str(value or "").strip().lower()
    if cleaned in ROUTE_MODE_VALUES:
        return cast(RouteMode, cleaned)
    return DEFAULT_ROUTE_MODE
