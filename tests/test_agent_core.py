from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.agent.actions import PendingToolAction
from app.agent.memory import MemoryStore
from app.agent.reminders import ReminderStore
from app.agent.tool_registry import Tool, ToolRegistry


def test_add_reminder_delay_seconds_generates_future_time(tmp_path) -> None:
    store = ReminderStore(tmp_path / "reminders.json")
    before = datetime.now().astimezone()

    result = store.add_reminder({"text": "喝水", "delay_seconds": 30})

    trigger_at = datetime.fromisoformat(result["reminder"]["trigger_at"])
    after = datetime.now().astimezone()
    assert before + timedelta(seconds=25) <= trigger_at <= after + timedelta(seconds=35)


def test_add_reminder_delay_minutes_generates_future_time(tmp_path) -> None:
    store = ReminderStore(tmp_path / "reminders.json")
    before = datetime.now().astimezone()

    result = store.add_reminder({"text": "休息", "delay_minutes": 2})

    trigger_at = datetime.fromisoformat(result["reminder"]["trigger_at"])
    after = datetime.now().astimezone()
    assert before + timedelta(seconds=115) <= trigger_at <= after + timedelta(seconds=125)


def test_add_reminder_rejects_past_trigger_at(tmp_path) -> None:
    store = ReminderStore(tmp_path / "reminders.json")
    past = (datetime.now().astimezone() - timedelta(minutes=1)).isoformat(timespec="seconds")

    with pytest.raises(ValueError, match="提醒时间必须晚于当前时间"):
        store.add_reminder({"text": "过期提醒", "trigger_at": past})


def test_due_reminders_and_mark_completed(tmp_path) -> None:
    store = ReminderStore(tmp_path / "reminders.json")
    now = datetime.now().astimezone()
    due = store.add_reminder({"text": "到点", "delay_seconds": 1})["reminder"]
    future = store.add_reminder({"text": "稍后", "delay_minutes": 5})["reminder"]

    due["trigger_at"] = (now - timedelta(seconds=1)).isoformat(timespec="seconds")
    future["trigger_at"] = (now + timedelta(minutes=5)).isoformat(timespec="seconds")
    store._save({"reminders": [due, future]})

    due_reminders = store.due_reminders(now)
    assert [reminder["id"] for reminder in due_reminders] == [due["id"]]

    store.mark_completed(due["id"])

    assert store.due_reminders(now) == []


def test_memory_propose_update_only_creates_pending_record(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory.json")

    result = store.propose_memory_update(
        {
            "category": "preference",
            "content": "主人喜欢中文回复",
            "reason": "长期偏好",
        }
    )

    snapshot = store.snapshot()
    assert snapshot["memories"] == []
    assert snapshot["pending_updates"] == [result["pending_update"]]


def test_memory_confirm_update_moves_pending_to_memories(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory.json")
    pending = store.propose_memory_update(
        {
            "category": "project",
            "content": "Sakura 正在稳定 Agent 内核",
        }
    )["pending_update"]

    result = store.confirm_memory_update({"id": pending["id"]})

    snapshot = store.snapshot()
    assert snapshot["pending_updates"] == []
    assert snapshot["memories"] == [result["memory"]]


def test_tool_registry_requires_confirmation_returns_pending_action() -> None:
    registry = ToolRegistry(
        [
            Tool(
                name="open_url",
                description="打开网页",
                handler=lambda _arguments: {"opened": True},
                requires_confirmation=True,
            )
        ]
    )

    result = registry.prepare_or_execute(
        "open_url",
        {"url": "https://example.com"},
        "用户要求打开网页",
    )

    assert isinstance(result, PendingToolAction)
    assert result.tool_name == "open_url"
    assert result.arguments == {"url": "https://example.com"}
