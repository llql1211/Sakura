from __future__ import annotations

import time
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from app.agent import AgentEvent, AgentProgress, AgentResult, AgentRuntime, PendingToolAction
from app.debug_log import debug_log, summarize_messages
from app.visual_observation import (
    VisualObservationJob,
    VisualObservationStore,
    summarize_visual_observation,
)


class ChatWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    progress = Signal(object)

    def __init__(
        self,
        agent_runtime: AgentRuntime,
        messages: list[dict[str, Any]] | None = None,
        confirmed_action: PendingToolAction | None = None,
        cancelled_action: PendingToolAction | None = None,
        visual_observation_store: VisualObservationStore | None = None,
        visual_observation_jobs: list[VisualObservationJob] | None = None,
    ) -> None:
        super().__init__()
        self.agent_runtime = agent_runtime
        self.messages = messages or []
        self.confirmed_action = confirmed_action
        self.cancelled_action = cancelled_action
        self.visual_observation_store = visual_observation_store
        self.visual_observation_jobs = visual_observation_jobs or []

    @Slot()
    def run(self) -> None:
        started_at = time.perf_counter()
        try:
            if self.confirmed_action is not None:
                debug_log("ChatWorker", "开始处理已确认动作", self.confirmed_action.to_dict())
                result: AgentResult = self.agent_runtime.handle_confirmed_action(
                    self.confirmed_action,
                    progress_callback=self._emit_progress,
                )
            elif self.cancelled_action is not None:
                debug_log("ChatWorker", "开始处理已取消动作", self.cancelled_action.to_dict())
                result = self.agent_runtime.handle_cancelled_action(self.cancelled_action)
            else:
                self._record_visual_observations()
                debug_log(
                    "ChatWorker",
                    "开始处理用户消息",
                    {
                        "message_count": len(self.messages),
                        "messages": summarize_messages(self.messages),
                    },
                )
                result = self.agent_runtime.handle_user_message(
                    self.messages,
                    progress_callback=self._emit_progress,
                )
        except Exception as exc:  # UI 边界统一转成可读错误。
            debug_log(
                "ChatWorker",
                "处理失败",
                {
                    "error": str(exc),
                    "elapsed_ms": int((time.perf_counter() - started_at) * 1000),
                },
            )
            self.failed.emit(str(exc))
            return
        debug_log(
            "ChatWorker",
            "处理完成",
            {
                "segments": len(result.reply.segments),
                "actions": [action.type for action in result.actions],
                "elapsed_ms": int((time.perf_counter() - started_at) * 1000),
            },
        )
        self.finished.emit(result)

    def _emit_progress(self, progress: AgentProgress) -> None:
        debug_log(
            "ChatWorker",
            "转发中间回复",
            {
                "stage": progress.stage,
                "segments": len(progress.reply.segments),
                "metadata": progress.metadata,
            },
        )
        self.progress.emit(progress)

    def _record_visual_observations(self) -> None:
        if self.visual_observation_store is None or not self.visual_observation_jobs:
            return
        for job in self.visual_observation_jobs:
            record = summarize_visual_observation(self.agent_runtime.api_client, job)
            self.visual_observation_store.append(record)
            debug_log(
                "ChatWorker",
                "视觉观察记录已保存",
                {
                    "visual_id": record.id,
                    "source": record.source,
                    "summary": record.summary,
                    "visible_text_count": len(record.visible_texts),
                    "sensitive_redacted": record.sensitive_redacted,
                },
            )


class EventWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    progress = Signal(object)

    def __init__(self, agent_runtime: AgentRuntime, event: AgentEvent) -> None:
        super().__init__()
        self.agent_runtime = agent_runtime
        # 避免覆盖 QObject.event() 虚函数名；PySide 在 moveToThread 时会访问该方法。
        self.agent_event = event
        self.visual_observation_store: VisualObservationStore | None = None
        self.visual_observation_jobs: list[VisualObservationJob] = []

    @Slot()
    def run(self) -> None:
        started_at = time.perf_counter()
        try:
            self._record_visual_observations()
            debug_log(
                "EventWorker",
                "开始处理主动事件",
                {
                    "type": self.agent_event.type,
                    "payload": self.agent_event.payload,
                },
            )
            result = self.agent_runtime.handle_event(
                self.agent_event,
                progress_callback=self._emit_progress,
            )
        except Exception as exc:  # 主动事件同样在 UI 边界转成可读错误。
            debug_log(
                "EventWorker",
                "处理失败",
                {
                    "error": str(exc),
                    "elapsed_ms": int((time.perf_counter() - started_at) * 1000),
                },
            )
            self.failed.emit(str(exc))
            return
        debug_log(
            "EventWorker",
            "处理完成",
            {
                "segments": len(result.reply.segments),
                "elapsed_ms": int((time.perf_counter() - started_at) * 1000),
            },
        )
        self.finished.emit(result)

    def _emit_progress(self, progress: AgentProgress) -> None:
        debug_log(
            "EventWorker",
            "转发中间回复",
            {
                "stage": progress.stage,
                "segments": len(progress.reply.segments),
                "metadata": progress.metadata,
            },
        )
        self.progress.emit(progress)

    def _record_visual_observations(self) -> None:
        if self.visual_observation_store is None or not self.visual_observation_jobs:
            return
        for job in self.visual_observation_jobs:
            record = summarize_visual_observation(self.agent_runtime.api_client, job)
            self.visual_observation_store.append(record)
            debug_log(
                "EventWorker",
                "视觉观察记录已保存",
                {
                    "visual_id": record.id,
                    "source": record.source,
                    "summary": record.summary,
                    "visible_text_count": len(record.visible_texts),
                    "sensitive_redacted": record.sensitive_redacted,
                },
            )
