[English](README.en.md)

# Sakura Desktop Pet

一个桌面上的角色 Agent——能聊天、换表情、用语音说话、记住你允许的事，也会在确认后帮你处理任务。它不只是「桌宠+聊天」，而是一个桌面陪伴型 Agent。

![Sakura 桌宠预览](_pet_style_preview.png)

## 设计思路

普通 AI 聊天窗口只是一个会回答问题的文本框。Sakura 想做的是另一种体验：角色一直停在桌面上，用自己的语气说话，用立绘表达情绪，能在需要时查时间、记提醒、读网页，也可以在你允许时看一眼屏幕。

模型的回复按段落组织为双语 JSON 片段（日文原文 + 中文字幕 + 语气标签），UI 对同一份结构同步驱动字幕、表情和可选的 TTS。

## 核心功能

- **角色包驱动。** `CharacterRegistry` 扫描 `characters/*/character.json`，校验角色卡、立绘和语音参考资源。新增角色主要是加一个角色目录，而不是改主程序。

- **分段双语回复。** 模型返回 JSON 片段，每段包含日文、中文和语气标签，UI 同步显示字幕、切换立绘、播放语音。

- **语气联动表情和语音。** 语气同时驱动立绘切换和 TTS 参考音频选择，支持 GPT-SoVITS 权重切换。

- **Agent 工具循环。** `AgentRuntime` 每轮先让模型规划是否需要工具，再执行待办、提醒、笔记、记忆、浏览器、屏幕观察等工具，最后基于工具结果生成回复。

- **按需屏幕观察。** 模型可在对话轮中请求一次当前屏幕截图，以 OpenAI 兼容 `image_url` 消息发送；截图不写入聊天历史。

- **自主屏幕观察。** 启用后，模型可在对话或主动事件中自主决定是否获取屏幕信息。

- **主动关怀。** 周期性根据上下文状态主动搭话，可以选择是否附带屏幕信息作为话题依据。支持批量发送观察快照。

- **手动框选截图。** 支持手动截取屏幕指定区域发送给模型。

- **受控浏览器。** Sakura 可打开一个由应用托管的浏览器页面，读取页面文本/链接、滚动、点击 CSS 选择器。会改变外部状态的动作需要确认。

- **本地桌面操作。** 支持通过模型调用鼠标点击、输入文字等本地桌面操作（通过 MCP Windows 工具），有助于完成浏览器交互和无障碍操作。

- **长期记忆与候选确认。** 待办、提醒、笔记、长期记忆都保存到 `data/` 下。长期记忆先写候选，只有你明确确认后才写入正式记忆。

- **自动记忆整理。** 达到一定对话轮次后，自动调用模型提取并整理对话中的关键事实作为记忆候选。

- **历史回看与回溯。** 支持查看历史对话记录，并可从历史点回溯继续对话。

- **MCP 扩展。** `data/config/mcp.yaml` 可注册 stdio 或 SSE MCP Server，外部工具带名称前缀挂入工具注册表，按风险级别决定是否需要确认。支持运行时开关（如 Windows MCP）。

- **立绘动效。** 角色立绘支持淡入淡出、弹跳等切换动效，搭配毛玻璃效果气泡。

- **上下文修剪。** 长对话自动修剪早期上下文，避免模型窗口超限。

- **调试日志。** 可输出详细的调试日志，包括请求/响应摘要，方便开发排查。

## 使用前后对比

| 不用 Sakura | 使用 Sakura |
|---|---|
| 聊天发生在普通文本窗口里 | 角色作为桌宠停留在屏幕上 |
| 回复是一整段纯文本 | 回复拆成适合显示、朗读和表情切换的小段 |
| 表情和语音互不联动 | 语气标签同时驱动立绘和 TTS 参考音频 |
| 工具调用需手动切换应用 | 模型可在对话中规划并调用内置工具 |
| 看屏幕容易变成长期保存截图 | 截图只按需附加到当前轮消息，历史只保留标记 |
| 外部能力要写死在代码里 | MCP Server 可通过 YAML 配置接入 |
| 长期记忆容易被模型静默写入 | 候选记忆需要你明确确认 |
| 没有主动搭话 | 可按配置周期性主动关怀 |

## 启动流程

运行 `python main.py` 后：

1. 创建 `QApplication`
2. 通过 `ApiSettings.load()` 从 `.env` 加载 API 配置
3. `CharacterRegistry` 扫描角色包
4. 加载角色人格卡和可用语气/立绘
5. `bootstrap.py` 组装 `AppContext`——包括工具注册表、记忆库、提醒库、MCP 桥接器、记忆整理器、主动关怀配置、TTS Provider
6. 显示 `PetWindow`

```mermaid
flowchart LR
    A["main.py"] --> B[".env"]<br>启动配置
    A --> C["CharacterRegistry"]
    C --> D["characters/sakura/character.json"]<br>角色包
    A --> E["OpenAICompatibleClient"]<br>API 客户端
    B --> E
    E --> F["AgentRuntime"]<br>Agent 决策层
    F --> G["ToolRegistry"]
    G --> H["内置工具 + MCP 工具"]
    A --> I["TTSProvider"]
    A --> J["bootstrap.py"]
    J --> K["AppContext"]
    K --> L["PetWindow"]
    E --> F
    F --> L
    I --> L
```

## 对话与工具调用流程

`PetWindow.send_message()` 把用户输入加入上下文，在 `QThread` 中启动 `ChatWorker`。Worker 调用 `AgentRuntime.handle_user_message()`：

1. 模型先返回工具调用意图或回复
2. 如有工具调用 -> 执行 -> 返回结果给模型 -> 模型最终输出分段回复
3. 分段回复经过 `ChatReply` 解析后，通过信号发回 UI 线程
4. UI 逐段显示字幕、切换立绘、播放语音

工具确认流程：当工具风险级别为 `medium` 或 `high`，且用户未开启自由访问权限时，`PendingToolAction` 会弹出确认面板，由用户决定允许或拒绝。确认后 Worker 会携带确认结果继续执行。

## 项目结构

```text
.
├── main.py                         # 应用入口
├── config.example.env              # 示例配置
├── app/
│   ├── api_client.py               # OpenAI 兼容 chat/completions 客户端
│   ├── app_context.py              # 核心依赖容器
│   ├── bootstrap.py                # 启动组装流程
│   ├── character_loader.py         # 角色包扫描与校验
│   ├── chat_history.py             # 聊天历史存储
│   ├── chat_reply.py               # 分段回复解析与兜底
│   ├── chat_worker.py              # Qt 后台线程 Worker
│   ├── context_trimming.py         # 长对话上下文修剪
│   ├── debug_log.py                # 调试日志
│   ├── env_config.py               # .env 配置读写
│   ├── history_window.py           # 历史回看窗口
│   ├── pet_window.py               # 桌宠主窗口（托盘、字幕、表情、工具确认）
│   ├── portrait_utils.py           # 立绘工具函数
│   ├── proactive_care.py           # 主动关怀模块
│   ├── prompt_templates.py         # 提示词模板（Agent 协议、上下文策略、事件协议）
│   ├── screen_observation.py       # 屏幕观察入口（自动 + 手动）
│   ├── settings_dialog.py          # 设置对话框
│   ├── tts.py                      # GPT-SoVITS / 静音 Provider
│   ├── visual_observation.py       # 视觉观察记录存储
│   ├── agent/
│   │   ├── actions.py              # Agent 动作/事件/待确认数据结构
│   │   ├── builtin_tools.py        # 内置工具注册（待办、提醒、笔记、时间等）
│   │   ├── desktop_tools.py        # 本地桌面工具（笔记、打开文件夹/URL）
│   │   ├── memory.py               # 长期记忆与候选记忆
│   │   ├── memory_curator.py       # 自动记忆整理
│   │   ├── memory_curation_worker.py # 记忆整理后台 Worker
│   │   ├── reminders.py            # 一次性提醒
│   │   ├── runtime.py              # Agent 决策、工具调用与最终回复
│   │   ├── screen_policy.py        # 屏幕观察策略
│   │   ├── screen_tools.py         # 屏幕观察工具
│   │   ├── tool_policy.py          # 工具路由策略（浏览器/桌面/后台 web）
│   │   ├── tool_registry.py        # 工具注册表、权限与执行
│   │   └── mcp/
│   │       ├── bridge.py           # MCP 工具桥接器
│   │       ├── config.py           # MCP YAML 配置模型
│   │       ├── provider.py         # MCP 生命周期管理
│   │       ├── settings.py         # MCP 运行时开关
│   │       └── web_search_server.py# Web 搜索 MCP Server
│   ├── ui/
│   │   ├── fonts.py                # 字体配置
│   │   ├── frosted_glass_frame.py  # 毛玻璃窗口组件
│   │   ├── manual_screenshot_overlay.py # 手动框选截图
│   │   ├── portrait_controller.py  # 立绘控制器（动效）
│   │   ├── screen_capture.py       # 屏幕截取工具
│   │   ├── styles.py               # 统一样式表
│   │   ├── subtitle_controller.py  # 字幕控制器
│   │   ├── tool_confirmation_panel.py # 工具确认面板
│   │   └── tray_menu.py            # 托盘菜单
│   └── voice/
│       ├── playback_controller.py  # 语音播放控制器
│       └── __init__.py
├── characters/
│   └── sakura/
│       ├── character.json          # 角色清单
│       ├── card.md                 # 人格卡 / 系统提示词
│       ├── portraits/              # 语气立绘
│       └── voice/                  # 模型文件与参考音频
├── data/                           # 本地数据（历史、记忆、提醒、待办、笔记、MCP 配置）
└── tests/                          # pytest 测试
```

## 快速开始

**前置要求：** Python 3.10+，Windows 下推荐使用 PowerShell。

```powershell
# 1. 创建并激活虚拟环境
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. 安装依赖
pip install -r requirements.txt

# 3. 创建本地配置
Copy-Item config.example.env .env

# 4. 编辑 .env，至少填入 API_KEY
notepad .env

# 5. 启动桌宠
python main.py
```

**.env 最低配置：**

```env
BASE_URL=https://api.openai.com/v1
API_KEY=your_api_key_here
MODEL=gpt-4.1-mini
CURRENT_CHARACTER_ID=sakura
TTS_ENABLED=false
```

启动后，你应该能在屏幕右下附近看到夜乃桜。右键桌宠或托盘图标可以打开设置、历史记录、字幕语言、隐私开关、模型视觉开关、自由访问权限和退出菜单。

## 可选语音配置

语音默认关闭。项目内置 GPT-SoVITS 客户端接入和 Sakura 角色的语音资源配置，但不内置 GPT-SoVITS 服务端运行目录。你需要自行启动兼容以下接口的本地 GPT-SoVITS API：

- `POST /tts`
- `GET /set_gpt_weights`
- `GET /set_sovits_weights`

然后在 `.env` 或设置窗口中启用：

```env
TTS_ENABLED=true
GPT_SOVITS_API_URL=http://127.0.0.1:9880/tts
GPT_SOVITS_REF_LANG=ja
GPT_SOVITS_TEXT_LANG=ja
GPT_SOVITS_TIMEOUT_SECONDS=60
```

内置 Sakura 角色包已在 `characters/sakura/character.json` 中配置了 GPT/SoVITS 模型路径和语气参考表。

## 配置项

| 配置项 | 作用 | 默认值 |
|---|---|---|
| `BASE_URL` | OpenAI 兼容 API 地址 | `https://api.openai.com/v1` |
| `API_KEY` | 聊天请求使用的 API Key | 空 |
| `MODEL` | 聊天模型名称 | `gpt-4.1-mini` |
| `API_TIMEOUT_SECONDS` | 聊天请求超时时间 | `60` |
| `SUBTITLE_LANGUAGE` | 气泡显示 `ja` 或 `zh` | `ja` |
| `SCREEN_OBSERVATION_ENABLED` | 是否允许按需屏幕观察 | `true` |
| `AUTONOMOUS_SCREEN_OBSERVATION_ENABLED` | 是否允许模型自主请求屏幕观察 | `false` |
| `PROACTIVE_CARE_ENABLED` | 是否启用主动关怀 | `false` |
| `PROACTIVE_SCREEN_CONTEXT_ENABLED` | 主动关怀时是否附带屏幕上下文 | `false` |
| `PROACTIVE_CHECK_INTERVAL_MINUTES` | 主动关怀检查间隔（分钟） | `20` |
| `PROACTIVE_COOLDOWN_MINUTES` | 主动关怀冷却时间（分钟） | `10` |
| `AUTO_MEMORY_ENABLED` | 是否启用自动记忆整理 | `true` |
| `AUTO_MEMORY_TRIGGER_TURNS` | 自动记忆整理的触发对话轮次间隔 | `8` |
| `AUTO_MEMORY_BACKFILL_LIMIT` | 自动记忆整理回溯的消息上限 | `200` |
| `WINDOWS_MCP_ENABLED` | 是否启用 Windows 桌面操作 MCP | `false` |
| `SAKURA_DEBUG` | 是否输出调试日志 | `false` |
| `SAKURA_DEBUG_BODY` | 是否在调试日志中输出完整正文 | `false` |
| `CURRENT_CHARACTER_ID` | 当前角色包 id | `sakura` |
| `TTS_ENABLED` | 是否启用 GPT-SoVITS 语音 | `false` |
| `GPT_SOVITS_API_URL` | 本地 TTS 接口地址 | `http://127.0.0.1:9880/tts` |
| `GPT_SOVITS_REF_LANG` | 参考音频语言 | `ja` |
| `GPT_SOVITS_TEXT_LANG` | 发送给 TTS 的文本语言 | `ja` |
| `GPT_SOVITS_TIMEOUT_SECONDS` | TTS 请求超时时间 | `60` |

## 测试

```powershell
python -m pytest
```

测试覆盖了 API 客户端、Agent 核心链路、聊天 Worker、调试日志、桌宠窗口、TTS、历史窗口、记忆整理、视觉观察和 Web 搜索 MCP 等模块。

## 许可证

仓库根目录目前没有提供 `LICENSE` 文件。重新分发角色资源、模型权重或第三方运行前，请分别确认对应文件的授权。
