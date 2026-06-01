from __future__ import annotations

from pathlib import Path
from typing import Any

from sdk.plugin import PluginBase
from sdk.plugin_host_context import PluginHostContext
from sdk.register import PluginCapabilityRegistry
from sdk.tool_registry import tool
from sdk.types import ToolsTabContribution

from plugins.playwright_browser import browser


class PlaywrightBrowserPlugin(PluginBase):
    """Sakura 内置 Playwright 浏览器插件。"""

    @property
    def plugin_id(self) -> str:
        return "playwright_browser"

    @property
    def plugin_version(self) -> str:
        return "1.0.0"

    def initialize(
        self,
        register: PluginCapabilityRegistry,
        plugin_root: Path,
        host: PluginHostContext,
    ) -> None:
        _ = plugin_root, host
        _register_tools()
        register.register_tools_tab(
            ToolsTabContribution(
                tab_id="playwright_browser",
                title="Playwright 浏览器",
                build=_build_tools_tab,
                order=40.0,
            )
        )

    def shutdown(self) -> None:
        browser.shutdown_browser()


def _register_tools() -> None:
    tool(
        name="playwright_navigate",
        description="使用系统 Microsoft Edge 打开网页 URL，并返回当前页面标题。",
        group="browser",
        risk="medium",
        requires_confirmation=True,
    )(browser.navigate)
    tool(
        name="playwright_get_text",
        description="读取当前 Edge 页面文本。selector 默认 body。",
        group="browser",
        risk="low",
        requires_confirmation=False,
    )(browser.get_text)
    tool(
        name="playwright_search_web",
        description="使用系统 Microsoft Edge 执行网页搜索，并返回结构化搜索结果。",
        group="browser",
        risk="medium",
        requires_confirmation=True,
    )(browser.search_web)
    tool(
        name="playwright_screenshot",
        description="截取当前 Edge 页面截图，返回 data URL。",
        group="browser",
        risk="medium",
        requires_confirmation=False,
    )(browser.screenshot)
    tool(
        name="playwright_click",
        description="点击当前 Edge 页面中的 CSS selector。",
        group="browser",
        risk="medium",
        requires_confirmation=True,
    )(browser.click)
    tool(
        name="playwright_fill",
        description="向当前 Edge 页面中的 CSS selector 输入文本。",
        group="browser",
        risk="medium",
        requires_confirmation=True,
    )(browser.fill)
    tool(
        name="playwright_evaluate",
        description="在当前 Edge 页面执行 JavaScript 代码。",
        group="browser",
        risk="high",
        requires_confirmation=True,
    )(browser.evaluate)


def _build_tools_tab(_parent: Any = None) -> Any:
    try:
        from PySide6.QtWidgets import QLabel
    except Exception:
        return None
    return QLabel("Playwright 浏览器使用系统 Microsoft Edge。")
