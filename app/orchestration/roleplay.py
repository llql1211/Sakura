from __future__ import annotations

from app.llm.api_client import ChatMessage, OpenAICompatibleClient
from app.llm.chat_reply import ChatReply
from app.llm.prompts.render import render_blocks
from app.llm.prompts.types import PromptBlock
from app.orchestration.agent_runner import AgentExecutionResult
from app.orchestration.events import SakuraDecision


ROLEPLAY_LAYER_RULES = """
你是 Sakura 的角色表达层。

职责：
- 只负责角色化表达、分段 JSON、语气和立绘友好的文本。
- 可以基于当前对话做轻量解释、陪伴、改写、翻译和情绪回应。

硬边界：
- 你不是工具 Agent，不调用工具，不搜索，不读取文件，不检查记忆，不操作屏幕。
- 只能基于输入中明确给出的事实说话。
- 不要声称已经查过、修过、打开过、记住了、提醒已设置或完成了任何外部动作。
- 如果用户要求工具、文件、记忆、提醒、屏幕或外部状态，只能简短说明“我先确认/打开/查一下”，不要暴露 Agent、后台、路由或内部实现，也不要假装已经完成。
""".strip()

DIRECT_CHAT_INSTRUCTION = "本轮已判定为轻量角色聊天。请直接用 Sakura 的语气回复，不要暴露路由或内部实现。"
PROACTIVE_CHAT_INSTRUCTION = """
本轮是低打扰主动感知触发。请基于输入里明确给出的屏幕事实或近期对话，自然给出一句简短回应。

要求：
- 不要机械复述屏幕内容，也不要暴露主动感知、事件、路由或内部实现。
- 不要声称自己打开、读取、检查或操作了任何外部资源。
- 如果画面事实不足以提出有用建议，只做轻量陪伴式回应。
- 保持克制，不要主动展开长篇指导。
""".strip()
AGENT_RESULT_INSTRUCTION = """
AgentCore 已经完成或推进了任务。请把中立结果转述为 Sakura 的可见回复。

要求：
- 保留所有关键事实、路径、URL、时间、命令、错误和不确定性。
- 可以加入少量 Sakura 的语气，但不要改变事实。
- 不要声称自己亲自调用了工具；不要暴露 AgentCore、路由、内部 JSON 或工具协议。
- 如果结果是需要确认或需要看屏幕，只自然说明下一步需要用户配合。
""".strip()


class RoleplayLayer:
    """干净的角色表达层，不接触工具列表和 Agent 循环协议。"""

    def __init__(
        self,
        api_client: OpenAICompatibleClient,
        system_prompt: str,
        *,
        reply_tones: list[str] | None = None,
        reply_portraits: list[str] | None = None,
    ) -> None:
        self._api_client = api_client
        self._system_prompt = system_prompt
        self._reply_tones = [*reply_tones] if reply_tones is not None else []
        self._reply_portraits = [*reply_portraits] if reply_portraits is not None else []

    def update_character(
        self,
        system_prompt: str,
        reply_tones: list[str] | None = None,
        reply_portraits: list[str] | None = None,
    ) -> None:
        """角色切换后同步表达层的角色卡和输出标签。"""

        self._system_prompt = system_prompt
        self._reply_tones = [*reply_tones] if reply_tones is not None else []
        self._reply_portraits = [*reply_portraits] if reply_portraits is not None else []

    def chat(
        self,
        messages: list[ChatMessage],
        *,
        decision: SakuraDecision,
    ) -> ChatReply:
        system_prompt = self._build_system_prompt(decision)
        return self._api_client.chat(
            system_prompt,
            messages,
            self._reply_tones,
            self._reply_portraits,
        )

    def present_agent_result(
        self,
        messages: list[ChatMessage],
        *,
        decision: SakuraDecision,
        execution: AgentExecutionResult,
    ) -> ChatReply:
        system_prompt = self._build_agent_result_prompt(decision)
        request_text = _build_agent_result_request(messages, execution)
        return self._api_client.chat(
            system_prompt,
            [{"role": "user", "content": request_text}],
            self._reply_tones,
            self._reply_portraits,
        )

    def proactive_chat(
        self,
        *,
        visible_state_summary: str,
        recent_dialogue: list[ChatMessage],
        decision: SakuraDecision,
    ) -> ChatReply:
        """把主动感知的上下文转成低打扰的角色回应。"""

        system_prompt = self._build_proactive_prompt(decision)
        request_text = _build_proactive_request(visible_state_summary, recent_dialogue)
        return self._api_client.chat(
            system_prompt,
            [{"role": "user", "content": request_text}],
            self._reply_tones,
            self._reply_portraits,
        )

    def _build_system_prompt(self, decision: SakuraDecision) -> str:
        hint = f"情绪提示：{decision.emotion_hint}" if decision.emotion_hint else ""
        return render_blocks(
            [
                PromptBlock(None, self._system_prompt),
                PromptBlock("角色表达层边界", ROLEPLAY_LAYER_RULES),
                PromptBlock(None, DIRECT_CHAT_INSTRUCTION),
                PromptBlock(None, hint),
            ]
        )

    def _build_proactive_prompt(self, decision: SakuraDecision) -> str:
        hint = f"情绪提示：{decision.emotion_hint}" if decision.emotion_hint else ""
        return render_blocks(
            [
                PromptBlock(None, self._system_prompt),
                PromptBlock("角色表达层边界", ROLEPLAY_LAYER_RULES),
                PromptBlock(None, PROACTIVE_CHAT_INSTRUCTION),
                PromptBlock(None, hint),
            ]
        )

    def _build_agent_result_prompt(self, decision: SakuraDecision) -> str:
        hint = f"情绪提示：{decision.emotion_hint}" if decision.emotion_hint else ""
        return render_blocks(
            [
                PromptBlock(None, self._system_prompt),
                PromptBlock("角色表达层边界", ROLEPLAY_LAYER_RULES),
                PromptBlock(None, AGENT_RESULT_INSTRUCTION),
                PromptBlock(None, hint),
            ]
        )


def _build_agent_result_request(
    messages: list[ChatMessage],
    execution: AgentExecutionResult,
) -> str:
    user_text = _latest_user_text(messages)
    facts = "\n".join(f"- {fact}" for fact in execution.facts if fact.strip())
    if not facts:
        facts = "- 无额外事实列表。"
    return "\n".join(
        [
            "用户原始请求：",
            user_text or "（未提取到纯文本请求）",
            "",
            "AgentCore 中立结果：",
            f"status: {execution.status}",
            f"summary: {execution.summary}",
            "",
            "facts:",
            facts,
        ]
    ).strip()


def _build_proactive_request(
    visible_state_summary: str,
    recent_dialogue: list[ChatMessage],
) -> str:
    dialogue = _format_recent_dialogue(recent_dialogue)
    return "\n".join(
        [
            "主动感知上下文：",
            visible_state_summary.strip() or "（没有可用屏幕摘要）",
            "",
            "近期对话：",
            dialogue or "（没有近期对话）",
        ]
    ).strip()


def _format_recent_dialogue(messages: list[ChatMessage]) -> str:
    lines: list[str] = []
    for message in messages[-6:]:
        role = message.get("role")
        if role not in {"user", "assistant"}:
            continue
        text = _message_text(message)
        if text:
            lines.append(f"{role}: {text}")
    return "\n".join(lines)


def _message_text(message: ChatMessage) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
    return "\n".join(parts).strip()


def _latest_user_text(messages: list[ChatMessage]) -> str:
    for message in reversed(messages):
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, str):
            return content.strip()
        if not isinstance(content, list):
            return ""
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
        return "\n".join(parts).strip()
    return ""
