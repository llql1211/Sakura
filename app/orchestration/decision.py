from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.llm.api_client import ChatMessage, OpenAICompatibleClient, messages_contain_image
from app.orchestration.events import DecisionInput, SakuraDecision
from app.orchestration.route_modes import normalize_route_mode


logger = logging.getLogger(__name__)

DECISION_SYSTEM_PROMPT = """
你是 Sakura 的决策层，只负责选择本轮最快且安全的处理路线。

可选 route：
- roleplay_chat：纯聊天、陪伴、解释、翻译、改写、情绪支持、无需外部状态。
- observe_screen：用户需要理解当前截图、屏幕、报错、可见界面，但不一定需要操作。
- agent_task：需要工具、文件、项目、浏览器、记忆、提醒、命令、外部检索或后台执行。
- ask_confirm：任务明显会改变外部状态，且用户意图或目标不完整。
- silent：主动事件没有足够自然话题时保持安静。

只返回 JSON：
{"route":"roleplay_chat|observe_screen|agent_task|ask_confirm|silent","reason":"简短原因"}
""".strip()

AGENT_PATTERNS = (
    # 文件、项目、代码、命令和工具。
    r"(打开|查看|读取|检查|搜索|查找|扫描).*(文件|代码|项目|仓库|目录|工作区|日志|配置|测试)",
    r"(打开|查看|读取|检查|搜索|查找|扫描|修改|编辑|删除|运行|执行)\s+[\w./\\\-\u4e00-\u9fff]+\.[A-Za-z0-9_]+",
    r"(修改|编辑|删除|移除|重命名|移动|修复|改一下|重构).*(文件|代码|脚本|函数|类|模块|测试|配置|项目)",
    r"(创建|新建|生成|写).*(文件|脚本|函数|类|模块|测试|命令|程序|插件|skill|技能)",
    r"(运行|执行|启动|停止|安装|编译|构建|测试|提交|commit|push|pull|checkout)\b",
    r"(用|使用|调用|启用|安装|列出).*(工具|tool|技能|skill|mcp|浏览器|browser)",
    r"(打开|启动|用|使用).*(浏览器|browser)",
    r"(浏览器|browser).*(搜|查|搜索|检索|打开|访问|看)",
    r"\b(open|read|view|inspect|check|scan|search)\b.*\b(file|folder|directory|repo|repository|project|workspace|codebase|log|config)\b",
    r"\b(open|read|view|inspect|check|scan|search|edit|modify|delete|run|execute)\b\s+[\w./\\-]+\.[A-Za-z0-9_]+\b",
    r"\b(edit|modify|delete|remove|rename|move|fix|refactor)\b.*\b(file|code|script|function|class|module|test|config|project)\b",
    r"\b(create|write|generate)\b.*\b(file|script|function|class|module|test|command|program|plugin|skill)\b",
    r"\b(run|execute|start|stop|install|build|compile|test|commit|push|pull|checkout)\b",
    r"\b(use|call|enable|install|list)\b.*\b(tool|tools|skill|skills|mcp|browser)\b",
    # 记忆、提醒和外部状态。
    r"(记住|记下来|保存到记忆|存到记忆|查记忆|搜索记忆|忘掉|删除记忆)",
    r"(提醒我|设置提醒|定时提醒|计划任务|待办|后台任务|后台执行)",
    r"(搜索一下|搜一下|搜搜|查一下|查查|联网|网页搜索|浏览网页|打开网页|访问网页)",
    r"\b(remember|save this|store this|recall|memory|remind me|set a reminder|timer|schedule|web search|browse|look up)\b",
)

SCREEN_PATTERNS = (
    r"(看|看看|观察|识别|分析|解释).*(屏幕|截图|画面|窗口|界面|报错|弹窗|页面)",
    r"(屏幕|截图|画面|当前窗口|这个报错|这个页面|这里).*(是什么|什么意思|怎么回事|哪里不对|看得见)",
    r"\b(screen|screenshot|window|visible|what is this|what's on)\b",
)

FOLLOW_UP_AGENT_PATTERNS = (
    r"^(继续|接着|重试|再试一次|按刚才的|就这样|改成|换成|撤销|恢复)\b",
    r"^(continue|retry|try again|do that|change it to|undo|redo)\b",
)


class DecisionLayer:
    """规则优先的路由层，可选接入轻量 LLM 兜底。"""

    def __init__(
        self,
        decider_client: OpenAICompatibleClient | None = None,
        *,
        enable_llm_fallback: bool = False,
        max_tokens: int = 256,
    ) -> None:
        self._decider_client = decider_client
        self._enable_llm_fallback = enable_llm_fallback
        self._max_tokens = max(int(max_tokens), 1)

    def decide(self, decision_input: DecisionInput) -> SakuraDecision:
        route_mode = normalize_route_mode(decision_input.route_mode)
        if route_mode == "quiet":
            return SakuraDecision(route="silent", reason="路由模式要求保持安静")
        if route_mode == "chat_only":
            return SakuraDecision(route="roleplay_chat", reason="路由模式强制纯角色回复")
        if route_mode == "force_agent":
            return SakuraDecision(route="agent_task", reason="路由模式强制 Agent 处理", should_ack=True)

        if decision_input.source == "proactive_tick" and not _has_proactive_trigger(decision_input):
            return SakuraDecision(route="silent", reason="主动事件没有足够自然话题")

        text = (decision_input.user_text or _latest_user_text(decision_input.messages) or "").strip()
        if not text and not decision_input.messages:
            return SakuraDecision(route="roleplay_chat", reason="空输入按轻量聊天处理")

        if messages_contain_image(decision_input.messages):
            return SakuraDecision(
                route="observe_screen",
                reason="消息包含图片或截图，需要视觉理解",
                needs_screen=True,
            )

        if _matches_any(text, AGENT_PATTERNS):
            return SakuraDecision(route="agent_task", reason="规则命中工具或外部状态任务", should_ack=True)
        if _matches_any(text, SCREEN_PATTERNS):
            return SakuraDecision(
                route="observe_screen",
                reason="规则命中屏幕观察意图",
                should_ack=True,
                needs_screen=True,
            )
        if decision_input.recent_dialogue and _matches_any(text, FOLLOW_UP_AGENT_PATTERNS):
            return SakuraDecision(route="agent_task", reason="疑似延续上一轮可执行任务", should_ack=True)

        llm_decision = self._llm_decide(decision_input, text)
        if llm_decision is not None:
            return llm_decision
        return SakuraDecision(route="roleplay_chat", reason="无需工具的轻量对话")

    def _llm_decide(self, decision_input: DecisionInput, text: str) -> SakuraDecision | None:
        if not self._enable_llm_fallback or self._decider_client is None:
            return None
        try:
            content = self._decider_client.complete_raw(
                DECISION_SYSTEM_PROMPT,
                [
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "source": decision_input.source,
                                "user_text": text,
                                "visible_state_summary": decision_input.visible_state_summary or "",
                            },
                            ensure_ascii=False,
                        ),
                    }
                ],
                temperature=0,
                max_tokens=self._max_tokens,
                response_format={"type": "json_object"},
            )
        except Exception:
            logger.exception("DecisionLayer LLM fallback failed")
            return None
        return _parse_decision_response(content)


def _parse_decision_response(content: str) -> SakuraDecision | None:
    try:
        data = json.loads(_extract_json_object(content))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    route = str(data.get("route", "")).strip()
    aliases = {
        "chat": "roleplay_chat",
        "agent": "agent_task",
        "screen": "observe_screen",
    }
    route = aliases.get(route, route)
    if route not in {"silent", "roleplay_chat", "observe_screen", "agent_task", "ask_confirm"}:
        return None
    return SakuraDecision(
        route=route,  # type: ignore[arg-type]
        reason=str(data.get("reason", "")).strip() or "LLM 路由判断",
        should_ack=route in {"agent_task", "observe_screen", "ask_confirm"},
        needs_screen=route == "observe_screen",
    )


def _extract_json_object(content: str) -> str:
    cleaned = content.strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        return cleaned[start : end + 1]
    return cleaned


def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    if not text:
        return False
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _has_proactive_trigger(decision_input: DecisionInput) -> bool:
    summary = (decision_input.visible_state_summary or "").strip()
    if summary:
        return True
    app_state = decision_input.app_state or {}
    return bool(app_state.get("screen_contexts") or app_state.get("visual_contexts"))


def _latest_user_text(messages: list[ChatMessage]) -> str | None:
    for message in reversed(messages):
        if message.get("role") != "user":
            continue
        return _message_content_to_text(message.get("content"))
    return None


def _message_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            text = item.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts).strip()
