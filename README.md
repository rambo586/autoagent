# AutoAgent

一个能先用起来的多 Agent 开发闭环：你只提需求，MiniMax 先做独立需求质疑，Google Antigravity/Gemini 补充研究与架构意见，Claude CLI（可使用你现有的 DeepSeek 后端配置）负责总控，Cursor CLI 负责主力开发，Codex CLI 负责规划、测试和只读复审。

AutoAgent 基于 [AWS Labs CLI Agent Orchestrator (CAO)](https://github.com/awslabs/cli-agent-orchestrator) 运行，不复制、不读取你的 API Key。每次任务创建独立 Git worktree 和分支，默认不 push、不 merge、不部署。

## 当前角色

| 角色 | 默认客户端 | 职责 |
|---|---|---|
| Challenger | MiniMax `mmx` | 在规划前找歧义、遗漏验收项、边界和交付风险 |
| Researcher | Google Antigravity `agy` / Gemini | 提供独立研究、架构选项和待核实外部事实 |
| Manager | Claude CLI / 你的 DeepSeek 后端 | 拆派、答疑、控制循环、最终汇报 |
| Planner | Codex CLI（只读） | 分析需求、制定验收标准和实施方案 |
| Developer | Cursor CLI（固定 Auto） | 编码、修复、向 Manager 提问 |
| Tester | Codex CLI（workspace-write） | 执行测试、收集证据、给出质量门结果 |
| Reviewer | Codex CLI（只读） | 独立复审风险和验收完整性 |

## 五分钟开始

macOS 需要 Python 3.10+、Git、`tmux`、`uv`，以及已经登录可用的 `claude`、`cursor-agent`（或 `agent`）、`codex`、`mmx` 和 `agy`。安装脚本会在缺失时安装官方 MiniMax CLI 与 Google Antigravity CLI，但不会替你处理登录凭据。

```bash
git clone https://github.com/rambo586/autoagent.git
cd autoagent
./install.sh

# 首次使用 MiniMax 时在本机交互登录
mmx auth login

# 首次使用 Antigravity 时启动一次并登录 Google AI Pro 对应账号
agy

# 先做无消耗检查；加 --live 会真实调用五个客户端并消耗少量额度
autoagent doctor
autoagent doctor --live

cd /path/to/your/project
autoagent run "给订单列表增加按状态筛选，并补齐测试"
```

提交任务后可以离开终端：

```bash
autoagent status
autoagent attach
autoagent report
```

Web 控制台默认位于 <http://127.0.0.1:9889>。完整本地配置见 [docs/LOCAL_SETUP.md](docs/LOCAL_SETUP.md)。

## 执行闭环

1. `mmx` 对原始需求做一次只读质疑，建议存入运行目录；失败时默认降级继续。
2. `agy` 在沙箱无头模式下提供独立研究与架构意见；失败时默认降级继续。
3. Manager 把需求和两份建议交给 Planner，由 Planner 结合代码库验证，得到结构化计划和验收标准。
4. Developer 在隔离 worktree 中实现；遇到疑义必须向 Manager 发送澄清请求。
5. Tester 运行项目测试，并对每条验收标准给出证据。
6. 测试不通过就回到 Developer，最多循环 3 次；通过后交给 Reviewer 独立复审。
7. Manager 写入 `final-report.md`。涉及产品取舍、凭据、部署或破坏性操作时，任务标记为 `BLOCKED`，保留现场等待人工决定。

状态和报告默认保存在 `~/.local/share/autoagent/runs/`；代码 worktree 保存在 `~/.local/share/autoagent/worktrees/`。

## 安全边界

- 默认不读取或复制 Keychain、`~/.ssh`、浏览器 Cookie、API Key 或其他凭据。
- 默认不 push、不 merge、不创建 PR、不部署；最终分支由你检查后自行处理。
- Planner 与 Reviewer 使用 Codex `read-only` 沙箱；Tester 使用 `workspace-write` 以允许测试生成缓存和构建产物。
- Cursor CLI 在 CAO 当前版本中会自动批准工具调用。独立 worktree 防止直接污染原分支，但它不是操作系统级沙箱；只对可信仓库使用。
- Cursor 的 Live Probe 和 Developer profile 都显式使用 `model: auto`，避免无头任务继承交互会话中的命名模型并触发套餐权限错误。
- `autoagent stop` 只终止会话，不删除 worktree 或分支，便于恢复和审计。
- CAO 当前没有原生 `mmx` 或 `agy` provider；v0.1.3 将两者作为有边界的前置顾问，不把它们伪装成可收发 CAO 消息的 worker。

MiniMax 默认模式是 `auto`：可用时调用，失败时继续。可按任务关闭或强制成功：

```bash
AUTOAGENT_MINIMAX=off autoagent run "需求"
AUTOAGENT_MINIMAX=always autoagent run "需求"
autoagent minimax quota
```

Antigravity 默认模式也是 `auto`：可用时调用，失败时继续。可按任务关闭或强制成功：

```bash
AUTOAGENT_ANTIGRAVITY=off autoagent run "需求"
AUTOAGENT_ANTIGRAVITY=always autoagent run "需求"
```

## 当前限制（v0.1）

- 先固定五个 CAO 角色和两个前置顾问，暂未自动按任务生成更多专家；后续可加入数据库、安全、UI 等按需角色。
- Manager 的 DeepSeek 模型映射沿用你的 Claude CLI 配置，AutoAgent 不修改它。
- 真实 CLI、模型配额和项目测试只能在你的本机验证；仓库 CI 只做静态和契约检查。
- 运行前要求当前 Git 工作区干净，避免把未提交改动错误地排除在任务上下文外。

## 开发

```bash
make test
```

架构与协议见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。
