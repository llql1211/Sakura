from __future__ import annotations

from app.agent import AgentEvent, AgentResult, AgentTaskResult
from app.core.chat_pipeline import ChatPipeline
from app.llm.chat_reply import parse_chat_reply
from app.orchestration import create_conversation_coordinator


class ClientStub:
    def __init__(self) -> None:
        self.chat_prompts: list[str] = []
        self.chat_messages: list[list[dict]] = []

    def chat(self, system_prompt, messages, reply_tones=None, reply_portraits=None):  # type: ignore[no-untyped-def]
        del reply_tones, reply_portraits
        self.chat_prompts.append(system_prompt)
        self.chat_messages.append(messages)
        if "AgentCore 已经完成或推进了任务" in system_prompt:
            return parse_chat_reply(
                '{"segments":[{"ja":"結果は確認できた。","zh":"结果已经确认了。","tone":"中性","portrait":"站立待机"}]}'
            )
        if "低打扰主动感知" in system_prompt:
            return parse_chat_reply(
                '{"segments":[{"ja":"見えてる。","zh":"我看到了。","tone":"中性","portrait":"站立待机"}]}'
            )
        return parse_chat_reply(
            '{"segments":[{"ja":"ここにいる。","zh":"我在这里。","tone":"中性","portrait":"站立待机"}]}'
        )


class RuntimeStub:
    def __init__(self) -> None:
        self.api_client = ClientStub()
        self.system_prompt = "角色设定"
        self.reply_tones = ["中性"]
        self.reply_portraits = ["站立待机"]
        self.agent_calls: list[list[dict]] = []
        self.task_calls: list[list[dict]] = []
        self.event_calls: list[AgentEvent] = []

    def handle_user_message(self, messages, progress_callback=None):  # type: ignore[no-untyped-def]
        del progress_callback
        self.agent_calls.append(messages)
        return AgentResult(
            parse_chat_reply(
                '{"segments":[{"ja":"調べた。","zh":"我查过了。","tone":"中性","portrait":"站立待机"}]}'
            )
        )

    def run_user_task(self, messages, progress_callback=None):  # type: ignore[no-untyped-def]
        del progress_callback
        self.task_calls.append(messages)
        return AgentTaskResult(
            status="success",
            summary="README.md 已读取，标题是 Sakura。",
            facts=["README.md", "标题是 Sakura"],
        )

    def handle_event(self, event, progress_callback=None):  # type: ignore[no-untyped-def]
        del progress_callback
        self.event_calls.append(event)
        return AgentResult(
            parse_chat_reply(
                '{"segments":[{"ja":"見えてる。","zh":"我看到了。","tone":"中性","portrait":"站立待机"}]}'
            )
        )


def test_coordinator_routes_plain_chat_to_roleplay_without_agent_runtime() -> None:
    runtime = RuntimeStub()
    coordinator = create_conversation_coordinator(runtime)  # type: ignore[arg-type]

    result = coordinator.handle_user_turn([{"role": "user", "content": "陪我说会儿话"}])

    assert result.reply.translation == "我在这里。"
    assert runtime.agent_calls == []
    assert runtime.api_client.chat_prompts
    assert "角色表达层边界" in runtime.api_client.chat_prompts[-1]
    assert "可用工具能力领域" not in runtime.api_client.chat_prompts[-1]


def test_coordinator_routes_tool_task_through_neutral_agent_then_roleplay() -> None:
    runtime = RuntimeStub()
    coordinator = create_conversation_coordinator(runtime)  # type: ignore[arg-type]

    result = coordinator.handle_user_turn([{"role": "user", "content": "帮我读取 README.md"}])

    assert result.reply.translation == "结果已经确认了。"
    assert runtime.agent_calls == []
    assert len(runtime.task_calls) == 1
    assert "AgentCore 已经完成或推进了任务" in runtime.api_client.chat_prompts[-1]
    assert "README.md 已读取" in runtime.api_client.chat_messages[-1][0]["content"]


def test_chat_pipeline_uses_coordinator_when_available() -> None:
    runtime = RuntimeStub()
    coordinator = create_conversation_coordinator(runtime)  # type: ignore[arg-type]
    pipeline = ChatPipeline(runtime, conversation_coordinator=coordinator)  # type: ignore[arg-type]

    result = pipeline.run_user_message([{"role": "user", "content": "你好"}])

    assert result.reply.translation == "我在这里。"
    assert runtime.agent_calls == []


def test_coordinator_keeps_proactive_event_silent_without_context() -> None:
    runtime = RuntimeStub()
    coordinator = create_conversation_coordinator(runtime)  # type: ignore[arg-type]

    result = coordinator.handle_event(AgentEvent(type="proactive_check", payload={}))

    assert result.reply.text == ""
    assert result.actions == []
    assert runtime.event_calls == []


def test_coordinator_routes_proactive_event_with_visual_context_to_roleplay() -> None:
    runtime = RuntimeStub()
    coordinator = create_conversation_coordinator(runtime)  # type: ignore[arg-type]

    result = coordinator.handle_event(
        AgentEvent(
            type="proactive_check",
            payload={
                "visual_contexts": [
                    {
                        "summary": "屏幕里正在编辑 runtime.py。",
                        "visible_texts": ["runtime.py", "AgentRuntime"],
                    }
                ]
            },
        )
    )

    assert result.reply.translation == "我看到了。"
    assert runtime.event_calls == []
    assert "低打扰主动感知" in runtime.api_client.chat_prompts[-1]
    assert "屏幕里正在编辑 runtime.py" in runtime.api_client.chat_messages[-1][0]["content"]


def test_coordinator_summarizes_screen_context_without_raw_image_data() -> None:
    runtime = RuntimeStub()
    coordinator = create_conversation_coordinator(runtime)  # type: ignore[arg-type]

    result = coordinator.handle_event(
        AgentEvent(
            type="proactive_check",
            payload={
                "screen_context": {
                    "summary": "屏幕里有一个测试失败提示。",
                    "window_title": "pytest",
                    "visible_texts": ["FAILED test_example.py"],
                    "notable_elements": ["终端窗口"],
                    "data_url": "data:image/png;base64,secret",
                }
            },
        )
    )

    request_text = runtime.api_client.chat_messages[-1][0]["content"]
    assert result.reply.translation == "我看到了。"
    assert "屏幕里有一个测试失败提示" in request_text
    assert "FAILED test_example.py" in request_text
    assert "data:image/png" not in request_text


def test_coordinator_can_force_agent_for_proactive_event() -> None:
    runtime = RuntimeStub()
    coordinator = create_conversation_coordinator(runtime)  # type: ignore[arg-type]
    coordinator.set_route_mode("force_agent")

    result = coordinator.handle_event(
        AgentEvent(
            type="proactive_check",
            payload={
                "visual_contexts": [
                    {
                        "summary": "屏幕里正在编辑 runtime.py。",
                        "visible_texts": ["runtime.py", "AgentRuntime"],
                    }
                ]
            },
        )
    )

    assert result.reply.translation == "我看到了。"
    assert len(runtime.event_calls) == 1
