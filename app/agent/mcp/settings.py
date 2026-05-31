from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
from pathlib import Path

from app.agent.mcp.config import MCPConfig
from app.env_config import load_env_file, save_env_values


WINDOWS_MCP_ENABLED_KEY = "WINDOWS_MCP_ENABLED"


@dataclass(frozen=True)
class MCPRuntimeSettings:
    """MCP 运行时开关；保存于 .env，启动时覆盖静态 mcp.yaml。"""

    windows_enabled: bool = False

    @classmethod
    def load(cls, env_path: Path) -> "MCPRuntimeSettings":
        values = load_env_file(env_path)
        return cls(
            windows_enabled=_parse_bool(
                values.get(WINDOWS_MCP_ENABLED_KEY),
                default=False,
            )
        )

    def save(self, env_path: Path) -> None:
        save_env_values(
            env_path,
            {WINDOWS_MCP_ENABLED_KEY: _format_bool(self.windows_enabled)},
        )


def apply_mcp_runtime_settings(
    config: MCPConfig,
    settings: MCPRuntimeSettings,
) -> MCPConfig:
    """按 .env 运行时开关覆盖需要重启加载的 MCP server。"""

    servers = [
        replace(server, enabled=settings.windows_enabled)
        if server.name == "windows"
        else server
        for server in config.servers
    ]
    return replace(config, servers=servers)


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on", "enabled"}:
        return True
    if normalized in {"0", "false", "no", "off", "disabled"}:
        return False
    return default


def _format_bool(value: bool) -> str:
    return "true" if value else "false"
