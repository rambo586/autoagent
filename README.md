# AutoAgent

AutoAgent 是一个本地多 Agent 开发闭环：你提需求，Manager 负责总牵头，Planner 拆解，Developer 实施，Tester 验证，Reviewer 独立复审，最后给你一份有证据的报告。

它基于 [AWS Labs CLI Agent Orchestrator (CAO)](https://github.com/awslabs/cli-agent-orchestrator)，不复制或保存你的 API Key。每个任务都在独立 Git worktree 和分支中运行，默认不 push、不 merge、不部署。

## 默认分工

| 角色 | 默认客户端 | 作用 |
|---|---|---|
| Manager | Claude CLI / 你现有的 DeepSeek 后端 | 总牵头、答疑、循环与最终报告 |
| Planner | Codex CLI（只读） | 仓库分析、计划、验收标准 |
| Developer | Cursor CLI（`auto`） | 编码与缺陷修复 |
| Tester | Codex CLI（workspace-write） | 运行检查，为每条验收标准提供证据 |
| Reviewer | Codex CLI（只读） | 独立检查正确性、回归与风险 |
| Challenger | MiniMax `mmx`（可选） | 规划前质疑歧义、边界与遗漏 |
| Researcher | Antigravity `agy`（手动） | 需要时由你在 Antigravity 产品内独立研究 |

Manager 会先把任务分为 `implementation`、`audit` 或 `mixed`。像“检查近三天开发质量”这类审计任务不会被强行制造代码改动。

## 五分钟开始

macOS 需要 Python 3.10+、Git、`tmux`、`uv`，以及已登录可用的 `claude`、`cursor-agent`（或 `agent`）、`codex` 和 `mmx`。

```bash
git clone https://github.com/rambo586/autoagent.git
cd autoagent
./install.sh

mmx auth login                   # 首次使用 MiniMax
autoagent doctor
autoagent doctor --live          # 会消耗少量模型额度
autoagent configure              # 交互选择预设、角色和模型

cd /path/to/your/project
autoagent run "给订单列表增加按状态筛选，并补齐测试"
```

任务提交后可以离开编排会话：

```bash
autoagent watch                 # 阶段、当前角色、轮次和最近事件
autoagent status                # 单次快照
autoagent attach                # 需要时接管 tmux 会话
autoagent report                # 最终报告
```

CAO Web 控制台默认位于 <http://127.0.0.1:9889>。

## 模型与角色配置

配置合并规则：

1. 全局、项目或本次 `run --preset` 决定使用哪个内置基线，后者的 preset 名优先；
2. `~/.config/autoagent/config.json` 中的显式字段覆盖基线；
3. 项目根目录 `.autoagent/config.json` 再覆盖全局显式字段；
4. 本次 `run --set key=value` 优先级最高。

因此 `run --preset fast` 会切换基线，但不会丢掉你显式配置的角色模型；需要临时覆盖时使用 `--set`。

`autoagent configure` 是推荐入口。也可以用快捷命令：

```bash
autoagent preset list
autoagent preset use balanced
autoagent models list             # 展示生效角色、模型和本机命令状态
autoagent models doctor           # 对生效配置做真实调用

autoagent role set manager claude
autoagent role set developer cursor --model auto
autoagent role set tester codex --model inherit --project
autoagent role disable reviewer --project

autoagent run --preset fast "修复这个小问题"
autoagent run --set developer.model=auto --set max_cycles=2 "需求"
```

`inherit` 表示沿用对应 CLI 当前配置。Cursor 默认用 `auto`，避免无头任务继承一个当前套餐不可用的命名模型。`models list` 不伪造不同订阅的远端模型目录；最终可用性以 `models doctor` 的真实调用为准。

可以把已安装的 CAO profile 注册为按需专家：

```bash
autoagent specialist add security my_security_profile \
  --purpose "认证与权限审计" \
  --when "任务修改认证、权限或敏感数据" \
  --project
autoagent specialist list
```

每次运行会把完整生效配置保存为 `effective-config.json`，并生成独立 CAO profiles；所以报告可以追溯当时真正使用的 provider 和 model。配置文件拒绝 token、secret、password、API key 等凭据字段。

## 内置 presets

| Preset | 最多修复轮次 | MiniMax | 适用场景 |
|---|---:|---|---|
| `balanced` | 3 | optional | 日常主力 |
| `quality` | 4 | optional | 风险更高、允许更多修复 |
| `fast` | 1 | disabled | 小任务、快速反馈 |
| `quota-saver` | 2 | disabled | 节省顾问额度 |

## Antigravity 边界

Antigravity 在 v0.2 中只是手动伴侣：`doctor` 可检查 `agy` 是否存在，但 `doctor --live` 和 `run` 都不会后台调用它。Google 明确说明，第三方软件不应使用 Antigravity 消费者登录；如果将来要把 Gemini 自动接入工作流，应改用 Vertex AI 或 AI Studio API Key。见 [Google Antigravity FAQ](https://antigravity.google/docs/faq)。

## 安全边界与限制

- 默认不读取 Keychain、`~/.ssh`、浏览器 Cookie、API Key 或其他凭据。
- Planner 与 Reviewer 使用 Codex `read-only`；Tester 使用 `workspace-write` 以允许正常缓存和构建产物。
- Cursor 在 CAO 集成中会自动批准工具调用。独立 worktree 能保护原分支，但不是操作系统级沙箱；只对可信仓库使用。
- 运行前要求当前 Git 工作区干净。
- `fallback_policy` 已预留配置字段，v0.2 不会悄悄换用其他模型或供应商。
- `autoagent stop` 只停止会话，不删除 worktree、分支或运行记录。

本地安装细节见 [docs/LOCAL_SETUP.md](docs/LOCAL_SETUP.md)，架构见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

## 开发

```bash
make test
```
