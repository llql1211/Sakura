[English](docs/README.en.md)

# Sakura Desktop Pet

最近推完水晶社的新作，~~推完自动变成学姐的狗~~，已经变成学姐的形状了，夜里辗转反侧怎么都睡不着，所以起来开发了这个桌宠 Agent 框架。

Sakura 最大的特点是 **她会主动找你**。传统聊天机器人只有在你先开口时才会回应，就像一扇需要你敲门才会开的锁；Sakura 更像一个坐在你旁边的人，你不需要一直和她说话，但她知道你在做什么，偶尔觉得该说点什么的时候会自己开口。

比如你正在打游戏，她瞥见屏幕上的死亡提示，凑过来说「已经第三回了…要不要帮你查下攻略？」同意后就真的打开浏览器搜了一圈，把要点贴进备忘录。

或者是你在浏览其他角色的图片时，会吃醋地说「又在看别人了啊…」要求你多看看她的立绘，偶尔还会因为你太久没看她而生气地说「都不理我了啊…」。

所以 Sakura 实现的是一个一直在角落、会观察、会偶尔插话的角色。她的对话风格、表情、语音都由角色卡驱动，而工具能力（浏览器操作、屏幕截图、文件读取、Web 搜索、提醒、长期记忆等）则来自内置的 Agent 引擎。

把它想成一个定制角色的桌面 Agent。

![Sakura 预览](assets/sakura_01.png)
![N.A.V.I. 预览](assets/navi_01.png)

## 快速开始

**不需要会编程。** 推荐直接使用 **Release 里的最新版本**，不要只下载 GitHub 页面上的源码压缩包。

> **平台提醒：** Windows 版本是当前主要测试目标。Mac 和 Linux 用户请先看 [完整安装指南](docs/SETUP.md)。

1. 从 [Releases 页面](https://github.com/Rvosy/sakura/releases) 下载最新 `sakura-v0.9.x-windows-x64.zip`
2. 解压后双击 `install.bat` 安装依赖
3. 准备一个兼容 OpenAI 接口的 API Key，填入 `data/config/api.yaml`
4. 双击 `start.bat` 启动

遇到问题、使用 Mac/Linux、或想了解更多配置项，请看 **[完整安装指南](docs/SETUP.md)**。

## 核心功能

- **角色包驱动。** 角色卡、立绘、语音参考和 GPT-SoVITS 权重都可以按角色包组织。
- **主动关怀。** Sakura 可以按周期观察上下文，主动发起提醒、关心或建议。
- **分段双语回复。** 模型输出日文原文、中文字幕、语气和立绘标识，UI 同步驱动字幕、表情和语音。
- **语气联动表情和语音。** 语气标签会同时影响立绘切换和 TTS 参考音频选择。
- **屏幕观察。** 支持按需截图和自主屏幕观察，把视觉摘要纳入对话上下文。
- **工具调用。** 支持浏览器操作、桌面操作、文件读取、Web 搜索、提醒、待办、笔记和记忆等工具。
- **权限确认。** 高风险工具会先请求用户确认，再执行实际动作。
- **长期记忆。** 记忆先进入候选区，确认后才写入正式记忆，并支持自动整理。
- **插件和 MCP 扩展。** 支持本地插件、MCP Server 和内置 Web 搜索 MCP Server。

## 文档

| 文档 | 内容 |
|---|---|
| [安装与配置指南](docs/SETUP.md) | 完整安装步骤、API Key 配置、角色包获取、版本更新 |
| [macOS 安装指南](docs/MACOS_SETUP.md) | Apple Silicon/Rosetta、SSL 证书、GPT-SoVITS 语音 |
| [技术讲解 README](docs/TECHNICAL_README.md) | 运行时架构、启动流程、项目结构、配置项 |
| [插件 SDK 文档](docs/SAKURA_PLUGIN_SDK.md) | 插件开发入口 |

## Star History

<a href="https://www.star-history.com/?repos=Rvosy%2Fsakura&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=Rvosy/sakura&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=Rvosy/sakura&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=Rvosy/sakura&type=date&legend=top-left" />
 </picture>
</a>
