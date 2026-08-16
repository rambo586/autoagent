# Local setup (macOS)

## 1. 准备 CLI

```bash
brew install uv tmux
python3 --version
git --version
```

需要下列客户端：

- Claude CLI：`claude`；保留你现有的 DeepSeek API/后端映射。
- Cursor CLI：`cursor-agent` 或 `agent`。
- Codex CLI：`codex`；AutoAgent 只添加两个安全 profile，不修改登录凭据。
- MiniMax CLI：`mmx`；用作可选 Challenger。
- Antigravity CLI：`agy`；仅作为可选手动伴侣。

`install.sh` 会在缺失时安装官方 `mmx-cli`，登录仍需你在本机交互完成：

```bash
mmx auth login
mmx auth status
mmx quota
```

如果 MiniMax 已登录但返回 401，可按订阅区域设置：

```bash
mmx config set --key region --value global
# 或
mmx config set --key region --value cn
```

AutoAgent 不自动安装、登录或无头调用 Antigravity。Google 的 [Antigravity FAQ](https://antigravity.google/docs/faq) 指明第三方软件不应使用 Antigravity 消费者登录；自动 Gemini 集成应使用 Vertex AI 或 AI Studio API Key。

## 2. 安装 AutoAgent

```bash
git clone https://github.com/rambo586/autoagent.git
cd autoagent
./install.sh
```

如果 `~/.local/bin` 不在 PATH：

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

安装器会：

- 通过 `uv` 安装/更新 CAO；
- 缺失时通过 npm 安装 `mmx-cli`；
- 安装 AutoAgent CLI、默认配置、profile 模板和 schema；
- 验证并安装五个默认 CAO profile；
- 备份 `~/.codex/config.toml` 后补充 `autoagent_readonly` 和 `autoagent_tester`。

它不读取或复制 API Key。

## 3. 配置角色与模型

```bash
autoagent configure
autoagent config show
autoagent config validate
autoagent models list
```

默认写入 `~/.config/autoagent/config.json`。在 Git 项目根目录运行以下命令，可生成项目级配置：

```bash
autoagent configure --project
# 或先创建最小配置
autoagent config init --project --preset balanced
```

命令式修改示例：

```bash
autoagent preset use quality --project
autoagent role set developer cursor --model auto --project
autoagent role set planner codex --model inherit --project
autoagent role disable reviewer --project
```

如果你填入命名模型，请使用对应 CLI 真正接受的 model ID/名称。不同订阅与 CLI 版本的目录会变；用下列命令对“当前生效配置”做真实验证：

```bash
autoagent models doctor
```

配置文件中不要放凭据。AutoAgent 会拒绝带有 token、secret、password、credential、API key 或 cookie 类字段的配置。

## 4. 诊断

```bash
autoagent doctor
autoagent doctor --live
```

第一个命令检查生效配置所需命令、Codex profiles 和 MiniMax 登录。`--live` 会调用生效的 Claude、Cursor、Codex 与 MiniMax 配置，消耗少量额度。Antigravity 显示为 `manual` 并被跳过。

Cursor 默认探针等价命令：

```bash
cursor-agent --trust --print --model auto "Reply exactly AUTOAGENT_OK"
```

如果当前套餐不匹配，用 `cursor-agent logout` 和 `cursor-agent login` 刷新登录，并确保浏览器登录到 Cursor Ultra 账号。

如果通过 SSH 使用 macOS，Cursor CLI 的登录钥匙串可能未解锁。只在你自己的终端中交互解锁，不要向 AutoAgent 或聊天粘贴钥匙串密码。

## 5. 运行与观察

从干净 Git 工作区开始：

```bash
cd /path/to/project
git status
autoagent run "实现一个具体需求，并补齐测试"
```

AutoAgent 会创建 `autoagent/<run-id>` 分支和 `~/.local/share/autoagent/worktrees/` 下的 worktree。原 checkout 保持不变。

```bash
autoagent watch [run-id]
autoagent status [run-id]
autoagent attach [run-id]
autoagent report [run-id]
autoagent stop [run-id]
autoagent list
```

`watch` 每 2 秒展示当前阶段、活跃角色、修复轮次与最近事件。Ctrl-C 只退出展示，不会停止任务。

## 6. 接受结果

阅读报告，进入报告中的 worktree，检查 diff 并再运行一次关键测试。然后按你自己的流程 commit/push/merge。AutoAgent 不会自动执行这些外部动作。
