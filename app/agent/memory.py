from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


MEMORY_CATEGORIES = {"preference", "project", "habit", "fact", "relationship"}
MEMORY_SOURCES = {"auto", "manual", "legacy", "imported"}

_SENSITIVE_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(api[_-]?key|secret|token|password|passwd|pwd)\b\s*[:=]",
        r"\b(sk-[A-Za-z0-9_\-]{16,})\b",
        r"\b[A-Za-z0-9_\-]{24,}\.[A-Za-z0-9_\-]{12,}\.[A-Za-z0-9_\-]{12,}\b",
        r"\b(?:\d[ -]*?){13,19}\b",
        r"\b\d{17}[\dXx]\b",
        r"(密码|口令|密钥|令牌|银行卡|信用卡|身份证)\s*[:：]",
    )
]


@dataclass
class MemoryStore:
    """按 JSON 保存正式长期记忆。"""

    path: Path | None = None
    values: dict[str, Any] = field(default_factory=dict)

    def snapshot(self) -> dict[str, list[dict[str, Any]]]:
        return self._load()

    def list_memories(self, include_archived: bool = False) -> list[dict[str, Any]]:
        data = self._load()
        memories = data["memories"]
        if include_archived:
            return memories
        return [memory for memory in memories if not memory.get("archived", False)]

    def summary(self, limit: int = 12) -> str:
        memories = _rank_memories(self.list_memories())[:limit]
        if not memories:
            return "暂无长期记忆。"

        lines = ["长期记忆："]
        for memory in memories:
            lines.append(
                "- [{id}] {category} "
                "(重要度 {importance:.2f} / 置信度 {confidence:.2f}): {content}".format(
                    id=memory.get("id", ""),
                    category=memory.get("category", ""),
                    importance=_float_in_range(memory.get("importance"), default=0.5),
                    confidence=_float_in_range(memory.get("confidence"), default=0.7),
                    content=memory.get("content", ""),
                )
            )
        return "\n".join(lines)

    def search_memory(self, arguments: dict[str, Any]) -> dict[str, Any]:
        keyword = _optional_text(arguments, "keyword").lower()
        category = _optional_text(arguments, "category")
        include_archived = bool(arguments.get("include_archived", False))
        if category:
            category = _normalize_category(category)
        memories = [
            memory
            for memory in self.list_memories(include_archived=include_archived)
            if _matches_memory(memory, keyword, category)
        ]
        return {"memories": _rank_memories(memories)}

    def create_memory(self, arguments: dict[str, Any], *, allow_sensitive: bool = False) -> dict[str, Any]:
        content = _required_text(arguments, "content")
        source = _normalize_source(_optional_text(arguments, "source") or "manual")
        if not allow_sensitive and source != "manual" and is_sensitive_memory_content(content):
            raise ValueError("自动记忆包含敏感凭据或隐私字段，已拒绝写入。")

        now = _now_iso()
        memory = {
            "id": _optional_text(arguments, "id") or uuid.uuid4().hex[:8],
            "category": _normalize_category(_required_text(arguments, "category")),
            "content": content,
            "importance": _float_in_range(arguments.get("importance"), default=0.7),
            "confidence": _float_in_range(arguments.get("confidence"), default=0.8),
            "created_at": _optional_text(arguments, "created_at") or now,
            "updated_at": _optional_text(arguments, "updated_at") or now,
            "last_seen_at": _optional_text(arguments, "last_seen_at") or now,
            "seen_count": _positive_int(arguments.get("seen_count"), default=1),
            "source": source,
            "archived": bool(arguments.get("archived", False)),
        }
        data = self._load()
        data["memories"].append(memory)
        self._save(data)
        return {"memory": memory}

    def update_memory(self, arguments: dict[str, Any], *, allow_sensitive: bool = False) -> dict[str, Any]:
        memory_id = _required_text(arguments, "id")
        data = self._load()
        for index, memory in enumerate(data["memories"]):
            if memory.get("id") != memory_id:
                continue
            updated = dict(memory)
            if "category" in arguments:
                updated["category"] = _normalize_category(_required_text(arguments, "category"))
            if "content" in arguments:
                content = _required_text(arguments, "content")
                source = _normalize_source(str(updated.get("source") or "manual"))
                if not allow_sensitive and source != "manual" and is_sensitive_memory_content(content):
                    raise ValueError("自动记忆包含敏感凭据或隐私字段，已拒绝写入。")
                updated["content"] = content
            if "importance" in arguments:
                updated["importance"] = _float_in_range(arguments.get("importance"), default=updated["importance"])
            if "confidence" in arguments:
                updated["confidence"] = _float_in_range(arguments.get("confidence"), default=updated["confidence"])
            if "last_seen_at" in arguments:
                updated["last_seen_at"] = _optional_text(arguments, "last_seen_at") or _now_iso()
            if "seen_count" in arguments:
                updated["seen_count"] = _positive_int(arguments.get("seen_count"), default=updated["seen_count"])
            if "source" in arguments:
                updated["source"] = _normalize_source(_required_text(arguments, "source"))
            if "archived" in arguments:
                updated["archived"] = bool(arguments.get("archived", False))
            updated["updated_at"] = _now_iso()
            data["memories"][index] = _normalize_memory_record(updated)
            self._save(data)
            return {"memory": data["memories"][index]}
        raise ValueError(f"未找到记忆：{memory_id}")

    def delete_memory(self, arguments: dict[str, Any]) -> dict[str, Any]:
        memory_id = _required_text(arguments, "id")
        data = self._load()
        for index, memory in enumerate(data["memories"]):
            if memory.get("id") != memory_id:
                continue
            removed = data["memories"].pop(index)
            self._save(data)
            return {"memory": removed}
        raise ValueError(f"未找到记忆：{memory_id}")

    def archive_memory(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.update_memory({"id": _required_text(arguments, "id"), "archived": True})

    def forget_memory(self, arguments: dict[str, Any]) -> dict[str, Any]:
        removed = self.delete_memory(arguments)["memory"]
        return {"forgotten": removed}

    def upsert_auto_memory(self, arguments: dict[str, Any]) -> dict[str, Any]:
        content = _required_text(arguments, "content")
        if is_sensitive_memory_content(content):
            return {"ignored": content, "reason": "包含敏感凭据或隐私字段"}

        category = _normalize_category(_required_text(arguments, "category"))
        data = self._load()
        existing = _find_duplicate_memory(data["memories"], category, content)
        if existing is None:
            payload = {
                **arguments,
                "category": category,
                "content": content,
                "source": "auto",
                "seen_count": _positive_int(arguments.get("seen_count"), default=1),
            }
            return {"created": self.create_memory(payload)["memory"]}

        seen_count = _positive_int(existing.get("seen_count"), default=1) + 1
        update_payload = {
            "id": existing["id"],
            "content": content,
            "importance": max(
                _float_in_range(existing.get("importance"), default=0.7),
                _float_in_range(arguments.get("importance"), default=0.7),
            ),
            "confidence": max(
                _float_in_range(existing.get("confidence"), default=0.8),
                _float_in_range(arguments.get("confidence"), default=0.8),
            ),
            "last_seen_at": _now_iso(),
            "seen_count": seen_count,
            "archived": False,
        }
        return {"updated": self.update_memory(update_payload)["memory"]}

    def apply_curation_operations(self, operations: list[dict[str, Any]]) -> dict[str, int]:
        result = {"created": 0, "updated": 0, "archived": 0, "ignored": 0}
        for operation in operations:
            if not isinstance(operation, dict):
                result["ignored"] += 1
                continue
            action = _optional_text(operation, "action").lower()
            try:
                if action == "create":
                    applied = self.upsert_auto_memory(operation)
                    if "created" in applied:
                        result["created"] += 1
                    elif "updated" in applied:
                        result["updated"] += 1
                    else:
                        result["ignored"] += 1
                elif action == "update":
                    memory_id = _required_text(operation, "id")
                    payload = {"id": memory_id, **operation}
                    payload.pop("action", None)
                    payload["source"] = operation.get("source", "auto")
                    self.update_memory(payload)
                    result["updated"] += 1
                elif action == "archive":
                    self.archive_memory({"id": _required_text(operation, "id")})
                    result["archived"] += 1
                else:
                    result["ignored"] += 1
            except ValueError:
                result["ignored"] += 1
        return result

    def _load(self) -> dict[str, list[dict[str, Any]]]:
        if self.path is None:
            return _normalize_data(self.values)
        if not self.path.exists():
            return {"memories": []}

        try:
            raw_data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"记忆文件不是有效 JSON：{self.path}") from exc
        return _normalize_data(raw_data)

    def _save(self, data: dict[str, list[dict[str, Any]]]) -> None:
        normalized = _normalize_data(data)
        if self.path is None:
            self.values = normalized
            return

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def is_sensitive_memory_content(content: str) -> bool:
    text = content.strip()
    if not text:
        return False
    return any(pattern.search(text) for pattern in _SENSITIVE_PATTERNS)


def _normalize_data(raw_data: Any) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(raw_data, dict):
        raise ValueError("记忆文件格式无效，顶层必须是 JSON object。")
    memories = _normalize_memory_records(raw_data.get("memories", []))
    return {"memories": memories}


def _normalize_memory_records(records: Any) -> list[dict[str, Any]]:
    if not isinstance(records, list):
        raise ValueError("记忆文件格式无效，memories 必须是列表。")
    result: list[dict[str, Any]] = []
    for item in records:
        if not isinstance(item, dict):
            continue
        try:
            result.append(_normalize_memory_record(item))
        except ValueError:
            continue
    return result


def _normalize_memory_record(item: dict[str, Any]) -> dict[str, Any]:
    memory_id = item.get("id")
    category = item.get("category")
    content = item.get("content")
    if not all(isinstance(value, str) and value.strip() for value in (memory_id, category, content)):
        raise ValueError("记忆记录缺少 id、category 或 content。")
    now = _now_iso()
    created_at = _text_or_default(item.get("created_at"), now)
    updated_at = _text_or_default(item.get("updated_at"), created_at)
    return {
        "id": memory_id.strip(),
        "category": _normalize_category(category),
        "content": content.strip(),
        "importance": _float_in_range(item.get("importance"), default=0.65),
        "confidence": _float_in_range(item.get("confidence"), default=0.8),
        "created_at": created_at,
        "updated_at": updated_at,
        "last_seen_at": _text_or_default(item.get("last_seen_at"), updated_at),
        "seen_count": _positive_int(item.get("seen_count"), default=1),
        "source": _normalize_source(str(item.get("source") or "legacy")),
        "archived": bool(item.get("archived", False)),
    }


def _rank_memories(memories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        memories,
        key=lambda memory: (
            _float_in_range(memory.get("importance"), default=0.5)
            * _float_in_range(memory.get("confidence"), default=0.7),
            str(memory.get("last_seen_at", "")),
            _positive_int(memory.get("seen_count"), default=1),
        ),
        reverse=True,
    )


def _find_duplicate_memory(
    memories: list[dict[str, Any]],
    category: str,
    content: str,
) -> dict[str, Any] | None:
    normalized_content = _normalize_for_match(content)
    for memory in memories:
        if memory.get("category") != category:
            continue
        if _normalize_for_match(str(memory.get("content", ""))) == normalized_content:
            return memory
    return None


def _matches_memory(memory: dict[str, Any], keyword: str, category: str) -> bool:
    if category and memory.get("category") != category:
        return False
    if not keyword:
        return True
    content = str(memory.get("content", "")).lower()
    memory_id = str(memory.get("id", "")).lower()
    memory_category = str(memory.get("category", "")).lower()
    return keyword in content or keyword in memory_id or keyword in memory_category


def _required_text(arguments: dict[str, Any], key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"缺少必填参数：{key}")
    return value.strip()


def _optional_text(arguments: dict[str, Any], key: str) -> str:
    value = arguments.get(key, "")
    return value.strip() if isinstance(value, str) else ""


def _normalize_category(category: str) -> str:
    normalized = category.strip()
    if normalized not in MEMORY_CATEGORIES:
        raise ValueError(f"记忆分类必须是：{', '.join(sorted(MEMORY_CATEGORIES))}")
    return normalized


def _normalize_source(source: str) -> str:
    normalized = source.strip().lower()
    if normalized in MEMORY_SOURCES:
        return normalized
    return "manual"


def _float_in_range(value: Any, *, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return max(0.0, min(1.0, number))


def _positive_int(value: Any, *, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(1, number)


def _text_or_default(value: Any, default: str) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default


def _normalize_for_match(content: str) -> str:
    return re.sub(r"\s+", "", content).casefold()


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
