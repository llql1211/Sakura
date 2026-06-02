from __future__ import annotations

from app.agent import AgentEvent, AgentProgress, AgentResult, AgentRuntime, ProgressCallback
from app.core.debug_log import debug_log, summarize_messages
from app.llm.api_client import ChatMessage
from app.llm.chat_reply import ChatReply, ChatSegment
from app.orchestration.agent_runner import AgentRunner
from app.orchestration.decision import DecisionLayer
from app.orchestration.events import DecisionInput
from app.orchestration.roleplay import RoleplayLayer
from app.orchestration.route_modes import DEFAULT_ROUTE_MODE, RouteMode


class ConversationCoordinator:
    """同步编排层：先决策，再在 Roleplay 和 AgentRuntime 间分流。"""

    def __init__(
        self,
        *,
        agent_runner: AgentRunner,
        decision_layer: DecisionLayer,
        roleplay_layer: RoleplayLayer,
        route_mode: RouteMode = DEFAULT_ROUTE_MODE,
    ) -> None:
        self._agent_runner = agent_runner
        self._decision_layer = decision_layer
        self._roleplay_layer = roleplay_layer
        self._route_mode = route_mode

    @property
    def route_mode(self) -> RouteMode:
        return self._route_mode

    def set_route_mode(self, route_mode: RouteMode) -> None:
        self._route_mode = route_mode

    def handle_user_turn(
        self,
        messages: list[ChatMessage],
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> AgentResult:
        runtime = self._agent_runner.runtime
        self._roleplay_layer.update_character(
            runtime.system_prompt,
            runtime.reply_tones,
            runtime.reply_portraits,
        )
        decision = self._decision_layer.decide(
            DecisionInput(
                source="user_message",
                messages=messages,
                recent_dialogue=messages[:-1],
                route_mode=self._route_mode,
            )
        )
        debug_log(
            "ConversationCoordinator",
            "用户消息路由完成",
            {
                "route": decision.route,
                "reason": decision.reason,
                "message_count": len(messages),
                "messages": summarize_messages(messages),
            },
        )

        if decision.route == "silent":
            return AgentResult(reply=ChatReply([ChatSegment("")]))
        if decision.route == "roleplay_chat":
            reply = self._roleplay_layer.chat(messages, decision=decision)
            return AgentResult(reply=reply)

        if decision.should_ack:
            _emit_delegated_ack(progress_callback, decision.reason, _latest_user_text(messages))
        execution = self._agent_runner.run_task(
            messages,
            progress_callback=progress_callback,
        )
        reply = self._roleplay_layer.present_agent_result(
            messages,
            decision=decision,
            execution=execution,
        )
        return AgentResult(reply=reply, actions=execution.actions)

    def handle_event(
        self,
        event: AgentEvent,
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> AgentResult:
        runtime = self._agent_runner.runtime
        self._roleplay_layer.update_character(
            runtime.system_prompt,
            runtime.reply_tones,
            runtime.reply_portraits,
        )
        if event.type != "proactive_check":
            return self._agent_runner.run_event(event, progress_callback=progress_callback)

        recent_dialogue = _recent_dialogue_from_event(event)
        visible_state_summary = _visible_state_summary_from_event(event)
        decision = self._decision_layer.decide(
            DecisionInput(
                source="proactive_tick",
                recent_dialogue=recent_dialogue,
                visible_state_summary=visible_state_summary,
                app_state=dict(event.payload),
                route_mode=self._route_mode,
            )
        )
        debug_log(
            "ConversationCoordinator",
            "主动事件路由完成",
            {
                "route": decision.route,
                "reason": decision.reason,
                "event_type": event.type,
            },
        )
        if decision.route == "silent":
            return AgentResult(reply=ChatReply([ChatSegment("")]))
        if decision.route == "roleplay_chat":
            reply = self._roleplay_layer.proactive_chat(
                visible_state_summary=visible_state_summary,
                recent_dialogue=recent_dialogue,
                decision=decision,
            )
            return AgentResult(reply=reply)
        return self._agent_runner.run_event(event, progress_callback=progress_callback)


def create_conversation_coordinator(runtime: AgentRuntime) -> ConversationCoordinator:
    return ConversationCoordinator(
        agent_runner=AgentRunner(runtime),
        decision_layer=DecisionLayer(),
        roleplay_layer=RoleplayLayer(
            runtime.api_client,
            runtime.system_prompt,
            reply_tones=runtime.reply_tones,
            reply_portraits=runtime.reply_portraits,
        ),
    )


def _emit_delegated_ack(
    progress_callback: ProgressCallback | None,
    reason: str,
    user_text: str = "",
) -> None:
    if progress_callback is None:
        return
    ack = (
        ("ブラウザを開いて検索してみる。", "好我打开浏览器搜搜看")
        if _is_visible_browser_request(user_text)
        else ("確認してから答える。", "我先确认一下再回答。")
    )
    progress_callback(
        AgentProgress(
            reply=ChatReply(
                [
                    ChatSegment(
                        ack[0],
                        "请求",
                        ack[1],
                        "伸手命令",
                    )
                ]
            ),
            stage="route_handoff",
            metadata={"reason": reason},
        )
    )


def _is_visible_browser_request(text: str) -> bool:
    normalized = text.lower()
    return any(
        keyword in normalized
        for keyword in (
            "打开浏览器",
            "用浏览器",
            "浏览器搜索",
            "在浏览器",
            "可见浏览器",
            "前台浏览器",
            "browser",
        )
    )


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


def _recent_dialogue_from_event(event: AgentEvent) -> list[ChatMessage]:
    recent = event.payload.get("recent_conversation")
    if not isinstance(recent, list):
        return []
    messages: list[ChatMessage] = []
    for item in recent:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role in {"user", "assistant"} and isinstance(content, str) and content.strip():
            messages.append({"role": role, "content": content.strip()})
    return messages


def _visible_state_summary_from_event(event: AgentEvent) -> str:
    summaries: list[str] = []
    for key in ("visual_contexts", "screen_contexts"):
        value = event.payload.get(key)
        if isinstance(value, list) and value:
            summaries.append(f"{key}: {len(value)}")
            for item in value[:3]:
                if not isinstance(item, dict):
                    continue
                _append_context_summary(summaries, item)
        elif isinstance(value, dict):
            summaries.append(key)
            _append_context_summary(summaries, value)
    screen_context = event.payload.get("screen_context")
    if isinstance(screen_context, dict):
        summaries.append("screen_context")
        _append_context_summary(summaries, screen_context)
    return "\n".join(summaries).strip()


def _append_context_summary(summaries: list[str], item: dict[object, object]) -> None:
    for field in ("summary", "window_title", "app_name", "title"):
        value = item.get(field)
        if isinstance(value, str) and value.strip():
            summaries.append(value.strip())

    for field in ("visible_texts", "notable_elements"):
        value = item.get(field)
        if not isinstance(value, list):
            continue
        text = " / ".join(str(part).strip() for part in value[:4] if str(part).strip())
        if text:
            summaries.append(text)
