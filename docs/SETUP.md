# Sakura 安装与配置指南

> 快速开始请看 [README.md](../README.md)；macOS 专项问题请看 [MACOS_SETUP.md](MACOS_SETUP.md)。

---

## 第一步：下载发布包

打开 [Releases 页面](https://github.com/Rvosy/sakura/releases)，下载最新的构建包。

| 文件名 | 是什么 | 适合谁下载 |
|:-:|---|---|
| `sakura-v0.9.x-windows-x64.zip` | Windows 完整包，包含项目文件和 `runtime` | **Windows 新手首选** |
| `runtime-windows-x64.zip` | 只有 Windows 预置 Python 运行环境 | 拉源码、缺 `runtime` 的用户 |

> 如果你只是想运行桌宠，下载 `sakura-v0.9.x-windows-x64.zip` 这种**完整包**。`runtime` 包不是完整程序，单独下载后不能直接启动。

---

## 第二步：安装依赖

解压完整包后，进入解压出来的软件目录。

- **Windows 用户：** 双击 `install.bat`，等待完成（约 5-15 分钟）。
- **Mac 用户：** 可尝试双击 `install.command`，或在终端进入项目目录后运行 `bash scripts/install.sh`。从源码运行、依赖踩坑、Apple Silicon/Rosetta 架构问题以及 GPT-SoVITS 语音搭建，详见 **[MACOS_SETUP.md](MACOS_SETUP.md)**（已在 Apple Silicon 实机测试）。
- **Linux 用户：** 当前没有正式发布包；如果从源码运行，进入项目目录后运行 `bash scripts/install.sh`。

> 如果是直接拉取的源码，需要先从 Release 页面下载对应平台的预编译依赖包（`sakura-runtime-*.zip`），把里面的 `runtime` 文件夹放到项目根目录，再运行安装脚本。不管下载的是 Release 完整包还是 GitHub 源码，这一步都要做。装完命令行窗口会自动关闭。

---

## 第三步：获取 API Key

桌宠需要一个「AI 大脑」才能说话，你需要一个 API Key。就像给手机插 SIM 卡才能上网一样。

获取 API Key 的渠道：

- 国内中转站如 [GemAI](https://api.gemai.cc/register?aff=rwbQ)（有便宜且按次计费的 gemini-flash 系列模型）
- 其他任何兼容 OpenAI 接口格式的服务

> **目前不要使用 DeepSeek 系列模型！**
>
> Sakura 的很多功能（屏幕观察、图像识别等）直接依赖模型的多模态能力（视觉理解），而 DeepSeek 系列模型不具备多模态能力，使用后会导致桌宠无法正常观察屏幕、识别图像等功能失效。
>
> 请选择支持视觉/多模态的模型，例如 Gemini Flash 等。

---

## 第四步：启动

- **Windows 用户：** 双击项目根目录的 **`start.bat`**
- **Mac 用户：** 可尝试双击 `start.command`，或在终端里运行 `bash scripts/start.sh`。详见 [MACOS_SETUP.md](MACOS_SETUP.md)。
- **Linux 用户：** 在终端里运行 `bash scripts/start.sh`
- **右键** 桌宠或托盘图标可以打开菜单（设置、聊天记录等）

---

## 第五步：获取角色包

暂时只有百度网盘：

- **[百度网盘](https://pan.baidu.com/s/5ZXvAi6n6i7-OJAYeWDpprg)**：包含所有已发布的角色包。

角色包会携带角色卡、立绘、语音参考音频，以及该角色可用的 GPT-SoVITS 权重（例如 `voice/models/*.ckpt`、`voice/models/*.pth`）。源码仓库和 TTS 运行环境安装脚本不会单独下载这些角色声线权重；如果完整包中没有对应角色资源，需要先通过角色包渠道获取并导入。

安装方式：

1. 下载角色包
2. 打开 Sakura 设置页
3. 选择导入角色包

---

## 如何更新版本

如果你已经装过旧版，推荐按下面方式更新：

1. 关闭正在运行的 Sakura。
2. 下载同平台的最新**完整包**，例如 Windows 用户下载 `sakura-v0.9.x-windows-x64.zip`。
3. 解压新包，把新包里的文件复制到旧 Sakura 目录，遇到同名文件选择**覆盖/替换**。
4. 如果启动失败，再运行一次安装脚本：Windows 双击 `install.bat`；Mac/Linux 运行 `bash scripts/install.sh`。
5. 启动 Sakura：Windows 双击 `start.bat`；Mac 可尝试 `start.command` 或 `bash scripts/start.sh`。
