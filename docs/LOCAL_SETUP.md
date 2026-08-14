# Local setup (macOS)

## 1. Prerequisites

```bash
brew install uv tmux
python3 --version
git --version
```

Install and authenticate these CLIs using their official instructions:

- Claude CLI: command `claude`; keep your existing DeepSeek API/backend mapping.
- Cursor CLI: command `cursor-agent` or `agent`; let Cursor use your plan's default/Auto model.
- Codex CLI: command `codex`; AutoAgent adds two named safety profiles but does not alter login credentials.

## 2. Install AutoAgent

```bash
git clone https://github.com/rambo586/autoagent.git
cd autoagent
./install.sh
```

If `~/.local/bin` is not in PATH:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

The installer:

- installs/updates CAO from its upstream `main` branch through `uv`;
- installs five CAO profiles;
- copies the launcher and schemas to `~/.local`;
- adds missing `autoagent_readonly` and `autoagent_tester` profiles to `~/.codex/config.toml` after creating a backup.

It never reads or copies API keys.

## 3. Diagnose

```bash
autoagent doctor
autoagent doctor --live
```

The first command only checks executables/configuration. `--live` sends a tiny prompt through Claude, Cursor, and Codex, so it consumes some subscription/API quota.

When Cursor CLI is invoked over SSH on macOS, its login keychain may be locked. Unlock it interactively on your machine, then rerun the live check:

```bash
security unlock-keychain "$HOME/Library/Keychains/login.keychain-db"
```

Do not paste the keychain password into AutoAgent or a chat.

## 4. Run a task

Start from a clean Git checkout:

```bash
cd /path/to/project
git status
autoagent run "实现一个具体需求，并补齐测试"
```

AutoAgent creates branch `autoagent/<run-id>` and a worktree under `~/.local/share/autoagent/worktrees/`. The original checkout remains on its existing branch.

Useful commands:

```bash
autoagent list
autoagent status [run-id]
autoagent attach [run-id]
autoagent report [run-id]
autoagent stop [run-id]
```

If a run is `BLOCKED`, inspect its report and attach to the manager session. v0.1 intentionally does not guess product decisions or provide a command that deletes run data.

## 5. Accept the result

Read the report, enter the reported worktree, inspect the diff and test once more. Then commit/push/merge using your normal process. AutoAgent does none of these external actions automatically.
