from __future__ import annotations

from dataclasses import dataclass
from math import ceil

SCREEN_AWARENESS_DEFAULT_CHECK_INTERVAL_MINUTES = 2
SCREEN_AWARENESS_DEFAULT_COOLDOWN_MINUTES = 10
SCREEN_AWARENESS_DEFAULT_SCREEN_CONTEXT_BATCH_LIMIT = 6
SCREEN_AWARENESS_DEFAULT_SCREEN_CONTEXT_RESOLUTION_P = 720
SCREEN_AWARENESS_SCREEN_CONTEXT_RESOLUTION_OPTIONS = (720, 1080, 1440, 2160)
SCREEN_AWARENESS_TOKEN_PATCH_SIZE = 32
SCREEN_AWARENESS_MIN_CHECK_INTERVAL_MINUTES = 1
SCREEN_AWARENESS_MAX_CHECK_INTERVAL_MINUTES = 120
SCREEN_AWARENESS_MIN_COOLDOWN_MINUTES = 1
SCREEN_AWARENESS_MAX_COOLDOWN_MINUTES = 120
SCREEN_AWARENESS_MIN_SCREEN_CONTEXT_BATCH_LIMIT = 1
SCREEN_AWARENESS_MAX_SCREEN_CONTEXT_BATCH_LIMIT = 20
SCREEN_AWARENESS_TIMER_POLL_INTERVAL_MS = 10_000
SCREEN_AWARENESS_TIMER_DUE_GRACE_SECONDS = 1.0
SCREEN_AWARENESS_CONTEXT_HISTORY_MARKER = "[已抓取屏幕上下文]"


@dataclass(frozen=True)
class ScreenAwarenessSettings:
    """主动屏幕感知配置；启用后会定期截图并让模型基于屏幕找话题。"""

    enabled: bool = True
    screen_context_enabled: bool = True
    check_interval_minutes: int = SCREEN_AWARENESS_DEFAULT_CHECK_INTERVAL_MINUTES
    cooldown_minutes: int = SCREEN_AWARENESS_DEFAULT_COOLDOWN_MINUTES
    screen_context_batch_limit: int = SCREEN_AWARENESS_DEFAULT_SCREEN_CONTEXT_BATCH_LIMIT
    screen_context_resolution_p: int = SCREEN_AWARENESS_DEFAULT_SCREEN_CONTEXT_RESOLUTION_P

    def normalized(self) -> "ScreenAwarenessSettings":
        enabled = bool(self.enabled)
        screen_context_enabled = enabled and bool(self.screen_context_enabled)
        return ScreenAwarenessSettings(
            enabled=enabled,
            screen_context_enabled=screen_context_enabled,
            check_interval_minutes=_clamp_interval_minutes(
                self.check_interval_minutes,
                min_value=SCREEN_AWARENESS_MIN_CHECK_INTERVAL_MINUTES,
                max_value=SCREEN_AWARENESS_MAX_CHECK_INTERVAL_MINUTES,
            ),
            cooldown_minutes=_clamp_interval_minutes(
                self.cooldown_minutes,
                min_value=SCREEN_AWARENESS_MIN_COOLDOWN_MINUTES,
                max_value=SCREEN_AWARENESS_MAX_COOLDOWN_MINUTES,
            ),
            screen_context_batch_limit=_clamp_bounded_int(
                self.screen_context_batch_limit,
                min_value=SCREEN_AWARENESS_MIN_SCREEN_CONTEXT_BATCH_LIMIT,
                max_value=SCREEN_AWARENESS_MAX_SCREEN_CONTEXT_BATCH_LIMIT,
            ),
            screen_context_resolution_p=normalize_screen_context_resolution_p(
                self.screen_context_resolution_p
            ),
        )

    def allows_screen_context(self) -> bool:
        """主动屏幕感知依赖截图；关闭屏幕上下文时整个功能停止。"""
        normalized = self.normalized()
        return normalized.enabled and normalized.screen_context_enabled


def _clamp_interval_minutes(value: int, *, min_value: int, max_value: int) -> int:
    return _clamp_bounded_int(value, min_value=min_value, max_value=max_value)


def _clamp_bounded_int(value: int, *, min_value: int, max_value: int) -> int:
    return max(
        min_value,
        min(max_value, value),
    )


def normalize_screen_context_resolution_p(value: int) -> int:
    """归一化主动感知截图分辨率；未知值回落到默认 720P。"""
    try:
        resolution = int(value)
    except (TypeError, ValueError):
        return SCREEN_AWARENESS_DEFAULT_SCREEN_CONTEXT_RESOLUTION_P
    if resolution in SCREEN_AWARENESS_SCREEN_CONTEXT_RESOLUTION_OPTIONS:
        return resolution
    return SCREEN_AWARENESS_DEFAULT_SCREEN_CONTEXT_RESOLUTION_P


def screen_context_max_edge_for_resolution_p(resolution_p: int) -> int:
    """将 720P/1080P 等垂直分辨率换算为 16:9 下的最长边。"""
    normalized = normalize_screen_context_resolution_p(resolution_p)
    return int(round(normalized * 16 / 9))


def estimate_screen_context_image_tokens(resolution_p: int) -> int:
    """按 16:9 与 32x32 图像块粗略估算单张截图 token。"""
    normalized = normalize_screen_context_resolution_p(resolution_p)
    width = screen_context_max_edge_for_resolution_p(normalized)
    return ceil(width / SCREEN_AWARENESS_TOKEN_PATCH_SIZE) * ceil(
        normalized / SCREEN_AWARENESS_TOKEN_PATCH_SIZE
    )


def estimate_screen_context_batch_tokens(resolution_p: int, image_count: int) -> int:
    """估算一批主动感知截图的图像 token，不包含文本和工具协议开销。"""
    try:
        count = int(image_count)
    except (TypeError, ValueError):
        count = 0
    return estimate_screen_context_image_tokens(resolution_p) * max(0, count)
