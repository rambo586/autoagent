# Local setup (macOS)

## 1. Prerequisites

```bash
brew install uv tmux
python3 --version
git --version
```

Install and authenticate these CLIs using their official instructions:

- Claude CLI: command `claude`; keep your existing DeepSeek API/backend mapping.
- Cursor CLI: command `cursor-agent` or `agent`; AutoAgent explicitly pins headless calls to Cursor's `auto` model.
- Codex CLI: command `codex`; AutoAgent adds two named safety profiles but does not alter login credentials.
- MiniMax CLI: command `mmx`; uses your MiniMax Token Plan and acts as a pre-planning Challenger.

`install.sh` installs the official `mmx-cli` when it is absent. Authentication remains an explicit local action:

```bash
mmx auth login
mmx auth status
mmx quota
```

The CLI normally detects Global/CN from your login. If an authenticated call returns 401, set the region that matches the subscription you purchased:

```bash
mmx config set --key region --value global
# or: mmx config set --key region --value cn
```

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
- installs the official MiniMax `mmx-cli` through npm when missing;
- installs five CAO profiles;
- copies the launcher and schemas to `~/.local`;
- adds missing `autoagent_readonly` and `autoagent_tester` profiles to `~/.codex/config.toml` after creating a backup.

It never reads or copies API keys.

## 3. Diagnose

```bash
autoagent doctor
autoagent doctor --live
```

The first command only checks executables/configuration and MiniMax auth state. `--live` sends a tiny prompt through Claude, Cursor, Codex, and MiniMax, so it consumes some subscription/API quota.

AutoAgent calls Cursor with `--model auto`. To isolate Cursor authentication or entitlement problems, run the same probe directly:

```bash
cursor-agent --trust --print --model auto "Reply exactly AUTOAGENT_OK"
```

If that direct Auto probe still reports the wrong plan, refresh the Cursor CLI login with `cursor-agent logout` followed by `cursor-agent login`, making sure the browser signs in to the account that owns Ultra.

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
autoagent minimax status
autoagent minimax quota
```

If a run is `BLOCKED`, inspect its report and attach to the manager session. v0.1 intentionally does not guess product decisions or provide a command that deletes run data.

MiniMax runs once before CAO planning and writes `minimax-advice.md` in the run directory. It is advisory data: Claude/DeepSeek does not blindly follow it, and Codex Planner must validate it against the repository. Use `AUTOAGENT_MINIMAX=off` to skip it or `AUTOAGENT_MINIMAX=always` to make its failure block task startup.

## 5. Accept the result

Read the report, enter the reported worktree, inspect the diff and test once more. Then commit/push/merge using your normal process. AutoAgent does none of these external actions automatically.
