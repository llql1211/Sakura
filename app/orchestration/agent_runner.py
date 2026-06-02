from __future__ import annotations

from dataclasses import dataclass, field

from app.agent import AgentAction, AgentEvent, AgentResult, AgentRuntime, AgentTaskResult, ProgressCallback
from app.llm.api_client import ChatMessage


@dataclass(frozen=True)
class AgentExecutionResult:
    """编排层使用的中立 Agent 执行结果。"""

    status: str
    summary: str
    actions: list[AgentAction] = field(default_factory=list)
    facts: list[str] = field(default_factory=list)
    raw_result: AgentResult | None = None
    raw_task_result: AgentTaskResult | None = None


class AgentRunner:
    """现阶段对 AgentRuntime 的薄包装，为后续中立 AgentCore 留出边界。"""

    def __init__(self, runtime: AgentRuntime) -> None:
        self.runtime = runtime

    def run_user_message(
        self,
        messages: list[ChatMessage],
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> AgentResult:
        return self.runtime.handle_user_message(
            messages,
            progress_callback=progress_callback,
        )

    def run_task(
        self,
        messages: list[ChatMessage],
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> AgentExecutionResult:
        run_user_task = getattr(self.runtime, "run_user_task", None)
        if callable(run_user_task):
            task_result = run_user_task(messages, progress_callback=progress_callback)
            return AgentExecutionResult(
                status=str(task_result.status or "success"),
                summary=str(task_result.summary or "").strip(),
                actions=[*task_result.actions],
                facts=[*task_result.facts],
                raw_task_result=task_result,
            )

        raw_result = self.run_user_message(
            messages,
            progress_callback=progress_callback,
        )
        return AgentExecutionResult(
            status=_status_from_actions(raw_result.actions),
            summary=raw_result.reply.translation or raw_result.reply.text,
            actions=[*raw_result.actions],
            raw_result=raw_result,
        )

    def run_event(
        self,
        event: AgentEvent,
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> AgentResult:
        return self.runtime.handle_event(event, progress_callback=progress_callback)


def _status_from_actions(actions: list[AgentAction]) -> str:
    if any(action.type == "pending_action" for action in actions):
        return "needs_confirmation"
    if any(action.type == "screen_observation_request" for action in actions):
        return "needs_screen"
    return "success"
