from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.portrait_utils import portrait_kind_key, should_crossfade_portrait


def test_portrait_kind_key_uses_filename_suffix_group() -> None:
    assert portrait_kind_key(Path("portraits/A020.png")) == "A"
    assert portrait_kind_key(Path("portraits/B180.png")) == "B"
    assert portrait_kind_key(Path("portraits/I010.png")) == "I"


def test_same_portrait_kind_crossfades_when_file_changes() -> None:
    assert should_crossfade_portrait(
        Path("portraits/A020.png"),
        Path("portraits/A150.png"),
    )
    assert should_crossfade_portrait(
        Path("portraits/I010.png"),
        Path("portraits/I180.png"),
    )


def test_different_portrait_kind_crossfades() -> None:
    assert should_crossfade_portrait(
        Path("portraits/A020.png"),
        Path("portraits/B180.png"),
    )


def test_same_portrait_file_does_not_crossfade() -> None:
    assert not should_crossfade_portrait(
        Path("portraits/A020.png"),
        Path("portraits/A020.png"),
    )


def test_pet_window_menu_keeps_only_allowed_checkable_switches() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    qtwidgets = pytest.importorskip("PySide6.QtWidgets")
    if not hasattr(qtwidgets, "QApplication") or not hasattr(qtwidgets, "QWidget"):
        pytest.skip("当前测试环境只提供了 PySide6 stub。")

    from app.pet_window import PetWindow, SUBTITLE_LANGUAGE_ZH

    QApplication = qtwidgets.QApplication
    QWidget = qtwidgets.QWidget
    app = QApplication.instance() or QApplication([])
    host = QWidget()
    host.subtitle_language = SUBTITLE_LANGUAGE_ZH
    host.free_access_enabled = True
    host._toggle_chinese_subtitles = lambda _checked: None
    host._toggle_free_access = lambda _checked: None
    host.show_history = lambda: None
    host.show_settings = lambda: None

    menu = PetWindow._build_menu(host)  # type: ignore[arg-type]
    actions = [action for action in menu.actions() if not action.isSeparator()]
    texts = [action.text() for action in actions]
    checkable_texts = [action.text() for action in actions if action.isCheckable()]

    assert texts[0] == "隐藏至托盘"
    assert "启用模型视觉" not in texts
    assert "允许自主看屏幕" not in texts
    assert "自由访问权限" not in texts
    assert "显示中文字幕" in checkable_texts
    assert "完整访问权限" in checkable_texts
    assert len(checkable_texts) == 2

    menu.deleteLater()
    host.deleteLater()
    app.processEvents()
