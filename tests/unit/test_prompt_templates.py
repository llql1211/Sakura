from __future__ import annotations

from app.llm.prompt_templates import (
    build_event_system_prompt,
    build_proactive_check_tool_system_prompt,
    build_proactive_tool_loop_rules,
    build_segmented_reply_instruction,
)


def test_proactive_check_tool_prompt_contains_background_web_rules() -> None:
    prompt = build_proactive_check_tool_system_prompt(
        "角色设定",
        ["中性"],
        ["站立待机"],
        memory_summary="无",
        current_time="2026-06-01T12:00:00+08:00",
        step_index=0,
        remaining_steps=2,
        max_tool_calls_per_step=3,
        max_tool_calls_per_turn=6,
    )

    assert "【主动感知后台 Web 搜索规则】" in prompt
    assert "web__web_search" in prompt
    assert "web__fetch_url" in prompt
    assert "不能把截图本身当作反向图片搜索能力" in prompt
    assert "不能编造具体身份" in prompt
    assert "不主动做人肉式识别" in prompt


def test_proactive_check_tool_prompt_places_web_rules_before_loop_limits() -> None:
    prompt = build_proactive_check_tool_system_prompt(
        "角色设定",
        None,
        None,
        memory_summary="无",
        current_time="2026-06-01T12:00:00+08:00",
        step_index=1,
        remaining_steps=1,
        max_tool_calls_per_step=3,
        max_tool_calls_per_turn=6,
    )

    scene_index = prompt.index("【主动感知场景策略】")
    web_index = prompt.index("【主动感知后台 Web 搜索规则】")
    loop_index = prompt.index("当前 Agent 循环：")

    assert scene_index < web_index < loop_index


def test_proactive_check_tool_prompt_requires_history_and_image_fusion() -> None:
    prompt = build_proactive_check_tool_system_prompt(
        "角色设定",
        ["中性"],
        ["站立待机"],
        memory_summary="无",
        current_time="2026-06-01T12:00:00+08:00",
        step_index=0,
        remaining_steps=2,
        max_tool_calls_per_step=3,
        max_tool_calls_per_turn=6,
    )

    assert "recent_conversation 当作最近完整对话历史" in prompt
    assert "用户和 Sakura 的最近对话" in prompt
    assert "不只是用来避免 Sakura 自己复读" in prompt
    assert "把 screen_contexts/visual_contexts 和 recent_conversation 交叉对照" in prompt
    assert "最终回复至少包含一个来自图片或历史的具体依据" in prompt


def test_reminder_event_prompt_does_not_include_background_web_research_rules() -> None:
    prompt = build_event_system_prompt(
        "角色设定",
        ["中性"],
        ["站立待机"],
        event_type="reminder_due",
    )

    assert "主动感知后台 Web 搜索规则" not in prompt
    assert "web__web_search" not in prompt
    assert "web__fetch_url" not in prompt


def test_proactive_tool_loop_rules_contains_background_web_research_rules() -> None:
    rules = build_proactive_tool_loop_rules()

    assert "【主动感知后台 Web 搜索规则】" in rules
    assert "每次主动检查最多 2 次搜索" in rules
    assert "最多读取 2 个网页" in rules


def test_segmented_reply_instruction_can_omit_translation_rules() -> None:
    instruction = build_segmented_reply_instruction(
        ["中性"],
        ["站立待机"],
        include_translation_rules=False,
    )

    assert "ja 中绝对不要有任何非日语内容" not in instruction
    assert "ja 和 zh 必须一一对应" not in instruction
    assert "tone 只能从这些类别中选择：中性" in instruction
