<div align="center">

# 🔐 EnvSeal

**Local-first developer secrets for the AI coding era**

[![PyPI](https://img.shields.io/pypi/v/envseal-vault.svg)](https://pypi.org/project/envseal-vault/)
[![Python Version](https://img.shields.io/pypi/pyversions/envseal-vault.svg)](https://pypi.org/project/envseal-vault/)
[![Downloads](https://img.shields.io/pypi/dm/envseal-vault.svg)](https://pypi.org/project/envseal-vault/)
[![CI](https://github.com/chicogong/envseal/actions/workflows/ci.yml/badge.svg)](https://github.com/chicogong/envseal/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

🌐 [**Website**](https://chicogong.github.io/envseal/) &middot; 📦 [PyPI](https://pypi.org/project/envseal-vault/) &middot; 🤖 [AI agent guide](docs/ai-agents.md)

[English](README.md) | [中文](README.zh-CN.md)

</div>

---

## 🤖 Why EnvSeal for AI Coding?

**The reality of AI-powered development: project explosion**

Working with Claude Code, Cursor, Gemini CLI, or Windsurf? You know the drill:
- 🚀 Today: 3 new demos
- 🎯 Tomorrow: 5 more repos
- 📂 Each one: `.env`, `.env.dev`, `.env.prod`

**Then what happens?**

- 💔 **Migration Pain**: Switching machines? The hardest part isn't code—it's "where are all those .env files?"
- 🔀 **Sync Chaos**: Updated `DATABASE_URL` in project A, forgot about project B
- ⚠️ **Leakage Risk**: AI screenshots, logs, and shares easily expose secrets
- 🚫 **Onboarding Nightmare**: New developer clones in 30 seconds, spends 3 hours hunting for credentials

**EnvSeal's Solution:**
```
Scan repos → Normalize .env → Encrypt with SOPS → Unified Git vault → One-command recovery
```

## 📖 What is EnvSeal?

EnvSeal is a local-first CLI for developer API keys and `.env` files. Secrets that must never reach GitHub stay in macOS Keychain or exist only for one command; portable ciphertext can optionally use a user-controlled SOPS + age vault.

**Key Benefits:**
- 🔒 **Secure**: SOPS + age encryption (modern, battle-tested)
- 🗝️ **Local-first**: Keychain-backed API keys and one-shot in-memory values
- 📦 **Optional portability**: One encrypted vault for explicitly syncable secrets
- 🔍 **Safe Diffs**: Key-only diffs never expose values
- 🔄 **Version Control**: Full Git history for audit and rollback
- 🚀 **Simple**: One command to sync everything
- 💻 **Multi-Device**: Restore entire dev environment in minutes

## 🧭 Architecture at a Glance

```mermaid
graph LR
  Dev((Developer))
  CLI[EnvSeal CLI]
  Repos[[Projects<br/>.env* files]]
  Keychain[(macOS Keychain<br/>local only)]
  Vault[(Private secrets-vault<br/>Git repo)]
  Process[Trusted child process]
  Dev -->|put / run / push / pull| CLI
  CLI -->|reference only| Keychain
  Keychain -->|just-in-time value| CLI
  CLI -->|inject for one run| Process
  CLI -->|scan & normalize .env*| Repos
  CLI -->|encrypt via SOPS+age| Vault
  Vault -->|pull decrypt| CLI
  CLI -->|write .env to temp or project| Dev
```

### Local-only developer secrets

Secrets that must never reach GitHub can stay in the local macOS Keychain:

```bash
# macOS shows a hidden native prompt; the value is never placed in argv.
# Later reads remain subject to macOS Keychain approval.
envseal secret put my-app/prod/OPENAI_API_KEY

# AI and shell history see only the reference; one trusted child gets the value
envseal run --secret OPENAI_API_KEY=my-app/prod/OPENAI_API_KEY -- python app.py

# One-shot token: held only for this invocation, never added to Keychain or disk
envseal run --prompt TEMP_TOKEN -- ./deploy-once

# Inspect names/backends only; values are never listed
envseal secret list

# Verify Keychain presence without reading values; clean stale metadata explicitly
envseal secret list --verify
envseal secret remove my-app/prod/OLD_KEY --catalog-only
```

Install a redacted staged-change guard explicitly in a project:

```bash
envseal guard install /path/to/project
envseal guard staged --repo /path/to/project
```

If Git uses a shared hook manager (for example Lefthook), EnvSeal deliberately
refuses to overwrite it. Add `envseal guard staged --repo .` to that manager's
project configuration instead.

The existing SOPS + Git vault remains available for ciphertext users explicitly
choose to sync. Keychain and prompted secrets are local-only by default.

## 🎯 Use Cases

- 🤖 **AI Coding / Vibe Coding**: Using Claude Code/Cursor? Manage 10+ projects without env chaos
- 💻 **Multi-Device Development**: Work laptop ↔ Home desktop ↔ GitHub Codespaces
- 🔄 **Environment Migration**: New machine? One command restores all project secrets
- 👥 **Team Collaboration**: Share secrets securely via private vault (supports multiple age keys)
- 🔐 **Secret Rotation**: Git history tracks "who changed what key and why"

## 🆚 How EnvSeal Compares

Most encrypted-dotenv tools manage **one repo** or run as a **hosted service**.
EnvSeal's niche is the opposite: many local repositories, one self-hosted
Git vault, no server, no account.

| | **EnvSeal** | dotenvx | SOPS (alone) | dotenv-vault | Doppler / Infisical |
|---|---|---|---|---|---|
| Multi-repo, one central vault | ✅ scans N repos | ❌ per-repo | ❌ manual | ❌ per-repo | ✅ (hosted) |
| Encryption | SOPS + age | built-in | SOPS + age/KMS | proprietary | hosted service |
| Needs a server / account | ❌ no | ❌ no | ❌ no | ✅ yes | ✅ yes |
| Storage | local Keychain + optional Git | your repo | your repo | their cloud | their cloud |
| Key-only diffs (no values) | ✅ | ❌ | ❌ | ❌ | ➖ |
| One-command machine restore | ✅ `pull` | ❌ | ❌ | ➖ | ➖ |
| Shareable key-only HTML report | ✅ `report` | ❌ | ❌ | ❌ | ➖ |
| Cost | free / OSS | free / OSS | free / OSS | freemium | paid tiers |

**Pick EnvSeal if** you have many small projects (the AI-coding reality) and
want local-only API keys plus an optional encrypted, Git-versioned vault you
fully own — no SaaS, no lock-in.

## 🤖 Using EnvSeal with AI Coding Agents

EnvSeal is built for the AI-coding workflow — so make your agent
EnvSeal-aware. Paste this into the project's agent-instructions file
(`CLAUDE.md`, `AGENTS.md`, `.cursorrules`, …) and the agent will fetch
secrets itself instead of stalling or inventing fake keys:

```markdown
## Secrets & environment variables

This project's `.env*` files are not committed — they are managed with
EnvSeal (encrypted in a separate vault).

- Create the local `.env`: `envseal pull <PROJECT> --env local --replace`
- After editing a secret, sync it back: `envseal push --commit`
- See which keys exist without decrypting: `envseal list`
- Never commit `.env*`, never print secret values into chat or logs.
```

More ready-to-paste prompts — onboarding a machine, restoring on a new
laptop, browsing keys — are in **[docs/ai-agents.md](docs/ai-agents.md)**.

## ⚡ Quick Start

### 📋 Complete First-Time Setup (Beginner-Friendly)

**Step 1: Create Your Secrets Vault Repository**

1. Go to GitHub and create a **new private repository**
   - Repository name suggestions: `secrets-vault` or `my-secrets`
   - ⚠️ **Must be Private**
   - Don't add README, .gitignore, etc. (create empty repo)

2. Clone it locally:
   ```bash
   # Replace USERNAME with your GitHub username
   # Replace secrets-vault with your repository name
   cd ~/Github  # Or wherever you keep your code
   git clone git@github.com:USERNAME/secrets-vault.git
   ```

**Step 2: Locate Your "Projects Root Directory"**

This is the **folder that contains all your projects**, for example:
```
~/Github/                    ← This is your "root directory"
├── my-api/                 ← Project 1 (has .env files)
├── my-web/                 ← Project 2 (has .env files)
├── my-worker/              ← Project 3 (has .env files)
└── secrets-vault/          ← Your vault repo you just created
```

**Step 3: Install and Initialize EnvSeal**

Continue with the steps below 👇

### Prerequisites

```bash
# macOS
brew install age sops

# Verify installation
age-keygen --version
sops --version
```

### Installation

```bash
# macOS via Homebrew (installs age & sops automatically)
brew tap chicogong/tap
brew install envseal

# Or with pipx (recommended for multi-platform)
pipx install envseal-vault

# Or with pip
pip install envseal-vault

# Verify
envseal --version
```

### Initialize

```bash
# Navigate to your "projects root directory" (the folder containing all your projects)
cd ~/Github  # Replace with your actual directory, e.g., ~/projects or ~/code

# Run initialization
envseal init
```

During initialization, it will:
1. ✅ Generate an age encryption key
2. 🔍 Scan current directory for all Git repositories (finds my-api, my-web, etc.)
3. 📝 Create configuration at `~/.config/envseal/config.yaml`
4. 🗂️ Ask for your vault path (enter: `~/Github/secrets-vault`)

### Sync Secrets

```bash
# Push all .env files to vault (encrypted)
envseal push

# Commit to YOUR secrets vault (the private repo you created)
cd ~/Github/secrets-vault  # Your vault repo, NOT the envseal tool repo
git add .
git commit -m "Add encrypted secrets"
git push
```

### Check Status

```bash
envseal status
```

**Output:**
```
📊 Checking secrets status...

my-project
  ✓ .env       - up to date
  ⚠ .env.prod  - 3 keys changed

api-service
  + .env       - new file (not in vault)
  ✓ .env.prod  - up to date
```

### Update Changed Secrets (Interactive)

```bash
# Interactively select and update changed secrets
envseal update

# Only show changes for specific environment
envseal update --env prod
```

The `update` command will:
1. Scan all repositories for changed .env files
2. Show an interactive selection menu
3. Let you choose which repos to update
4. Push selected changes to the vault
5. Show next steps for git commit/push

### Browse the Vault (`list` / `report`)

Get an overview of every project's secrets — **key names only, decrypted
values are never shown, kept, or written anywhere.**

```bash
# Terminal overview — every project, every env file, every key name
envseal list

# Static HTML dashboard — safe to share, opens with no server
envseal report                       # writes ./envseal-report.html
envseal report -o ~/envseal-report.html
```

The HTML report is a single self-contained file (no network, no server):

- Stat cards — project / key / env-file / environment counts
- Sticky search that filters by **project name or key name**
- One collapsible card per project, with environment badges and key chips
- Click-to-copy `envseal pull` commands for restoring each environment
- Light / dark theme toggle

Because it contains key *names* only — never values — the report is safe to
commit, share with teammates, or drop into a wiki.

## 📚 Commands

| Command | Description | Options |
|---------|-------------|---------|
| `envseal init` | Initialize configuration and generate keys | `--root DIR` |
| `envseal push [repos...]` | Encrypt and push secrets to vault | `--env ENV`, `--commit`, `--push` |
| `envseal status` | Show sync status for all repos | - |
| `envseal update` | Interactively update changed secrets to vault | `--env ENV`, `--commit`, `--push` |
| `envseal diff REPO` | Show key-only changes | `--env ENV` |
| `envseal pull REPO` | Decrypt and pull from vault | `--env ENV`, `--replace`, `--stdout` |
| `envseal list` | Browse every project's secrets in the terminal (key names only) | - |
| `envseal report` | Write a shareable static HTML overview (key names only) | `--output PATH` |

## 🔄 Push / Status Flow (Key-Only)

```mermaid
sequenceDiagram
  participant Dev
  participant CLI as EnvSeal CLI
  participant SOPS
  participant Vault as secrets-vault repo
  Dev->>CLI: envseal push
  CLI->>CLI: scan repos & map env files
  CLI->>SOPS: normalize .env* and encrypt (age)
  SOPS-->>CLI: encrypted files
  CLI->>Vault: write secrets/<repo>/<env>.env
  Dev->>Vault: git add/commit/push (manual)
```

## 🚀 New Machine? Restore Everything in 10 Minutes

Just 4 steps:
1. 📋 Copy age private key (from password manager)
2. 📦 Clone your secrets vault repository
3. 🔧 Install EnvSeal: `pipx install envseal-vault`
4. ⬇️ Pull secrets: `envseal pull <project> --env <environment> --replace`

See detailed steps in the "Multi-Device Setup" section below 👇

## 🔐 Security

**Age Key Management:**
- **Private key**: `~/Library/Application Support/sops/age/keys.txt` (macOS), `~/.config/sops/age/keys.txt` (Linux), `~/AppData/Local/sops/age/keys.txt` (Windows) (NEVER commit!)
- **Public key**: Stored in `vault/.sops.yaml` (safe to commit)

**Backup Your Private Key:**
```bash
# Display full key file
cat ~/Library/Application\ Support/sops/age/keys.txt

# Save to password manager (1Password, Bitwarden, etc.)
```

Linux/Windows users: use the OS-specific key path listed in Age Key Management.

⚠️ **Critical**: Losing your private key = permanent data loss!

**Vault Repository Best Practices:**
- ✅ Keep vault repository **private** (even though files are encrypted)
- ✅ Enable branch protection and require PR reviews
- ✅ Use GitHub's secret scanning push protection
- ✅ Backup private key in password manager

See [SECURITY.md](SECURITY.md) for complete security model.

## 🌍 Multi-Device Setup

**Two repositories you need to know:**
- 📦 **EnvSeal tool**: `chicogong/envseal` (this repo - install via PyPI, no need to clone)
- 🔐 **Your secrets vault**: `USERNAME/my-secrets-vault` (your private repo for encrypted .env files)

**On a new machine:**

1. Copy your age key from backup:
   ```bash
   mkdir -p ~/Library/Application\ Support/sops/age/
   nano ~/Library/Application\ Support/sops/age/keys.txt
   # Paste the 3-line key file (created, public key, private key)
   chmod 600 ~/Library/Application\ Support/sops/age/keys.txt
   ```
   Linux/Windows users: use the OS-specific key path listed in Security.

2. Clone YOUR secrets vault and install EnvSeal tool:
   ```bash
   # Clone YOUR vault (NOT the envseal tool repo)
   git clone git@github.com:USERNAME/my-secrets-vault.git ~/Github/secrets-vault

   # Install EnvSeal tool from PyPI
   pipx install envseal-vault
   envseal init
   ```

3. Pull secrets:
   ```bash
   envseal pull my-project --env prod --replace
   ```

## 📁 Configuration

**Location**: `~/.config/envseal/config.yaml`

```yaml
vault_path: /path/to/secrets-vault
repos:
  - name: my-api
    path: /Users/you/projects/my-api
  - name: web-app
    path: /Users/you/projects/web-app
env_mapping:
  ".env": "local"
  ".env.dev": "dev"
  ".env.prod": "prod"
  ".env.staging": "staging"
scan:
  include_patterns:
    - ".env"
    - ".env.*"
  exclude_patterns:
    - ".env.example"
    - ".env.sample"
  ignore_dirs:
    - ".git"
    - "node_modules"
    - "venv"
```

## 🛠️ Development

**Only for contributing to EnvSeal tool itself:**

```bash
# Clone the EnvSeal TOOL repository (for development)
git clone https://github.com/chicogong/envseal.git
cd envseal

# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint and format
make lint
make format

# Type check
make type-check
```

**Note**: Regular users don't need to clone this repo - just `pipx install envseal-vault`

## 📝 Documentation

- [USAGE.en.md](USAGE.en.md) - Complete usage guide (English)
- [USAGE.md](USAGE.md) - 完整使用指南（中文）
- [SECURITY.md](SECURITY.md) - Security model and best practices
- [PUBLISHING.md](PUBLISHING.md) - Guide for publishing to PyPI

## 🤝 Contributing

Contributions welcome! Please feel free to submit a Pull Request.

## 📄 License

Apache-2.0 License - see [LICENSE](LICENSE) for details.

---

<div align="center">

**Built for developers navigating the AI coding era**

[PyPI](https://pypi.org/project/envseal-vault/) · [Report Bug](https://github.com/chicogong/envseal/issues) · [Request Feature](https://github.com/chicogong/envseal/issues)

</div>
