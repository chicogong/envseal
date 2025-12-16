<div align="center">

# 🔐 EnvSeal

**Secure, centralized environment variable management for the AI coding era**

[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![PyPI](https://img.shields.io/pypi/v/envseal-vault.svg)](https://pypi.org/project/envseal-vault/)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

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

EnvSeal is a CLI tool that helps you manage `.env` files across multiple repositories with **end-to-end encryption**. It scans your projects, normalizes environment files, and syncs them to a Git-backed vault using SOPS encryption.

**Key Benefits:**
- 🔒 **Secure**: SOPS + age encryption (modern, battle-tested)
- 📦 **Centralized**: One vault for all secrets across unlimited projects
- 🔍 **Safe Diffs**: Key-only diffs never expose values
- 🔄 **Version Control**: Full Git history for audit and rollback
- 🚀 **Simple**: One command to sync everything
- 💻 **Multi-Device**: Restore entire dev environment in minutes

## 🎯 Use Cases

- 🤖 **AI Coding / Vibe Coding**: Using Claude Code/Cursor? Manage 10+ projects without env chaos
- 💻 **Multi-Device Development**: Work laptop ↔ Home desktop ↔ GitHub Codespaces
- 🔄 **Environment Migration**: New machine? One command restores all project secrets
- 👥 **Team Collaboration**: Share secrets securely via private vault (supports multiple age keys)
- 🔐 **Secret Rotation**: Git history tracks "who changed what key and why"

## ⚡ Quick Start

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
# Install with pipx (recommended)
pipx install envseal-vault

# Or with pip
pip install envseal-vault

# Verify
envseal --version
```

### Initialize

```bash
cd ~/your-projects-directory
envseal init
```

This will:
1. ✅ Generate an age encryption key
2. 🔍 Scan for Git repositories
3. 📝 Create configuration at `~/.config/envseal/config.yaml`
4. 🗂️ Set up vault structure

### Sync Secrets

```bash
# Push all .env files to vault (encrypted)
envseal push

# Commit to vault
cd ~/Github/secrets-vault
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
  ⚠ prod.env   - 3 keys changed

api-service
  + local.env  - new file (not in vault)
  ✓ prod.env   - up to date
```

## 📚 Commands

| Command | Description | Options |
|---------|-------------|---------|
| `envseal init` | Initialize configuration and generate keys | `--root DIR` |
| `envseal push [repos...]` | Encrypt and push secrets to vault | `--env ENV` |
| `envseal status` | Show sync status for all repos | - |
| `envseal diff REPO` | Show key-only changes | `--env ENV` |
| `envseal pull REPO` | Decrypt and pull from vault | `--env ENV`, `--replace`, `--stdout` |

## 🚀 AI Coding Quick Recovery

**Scenario: Restore all project environments on a new machine in 10 minutes**

```bash
# 1. Copy age private key from your password manager
mkdir -p ~/Library/Application\ Support/sops/age/
nano ~/Library/Application\ Support/sops/age/keys.txt
# Paste the 3-line key file
chmod 600 ~/Library/Application\ Support/sops/age/keys.txt

# 2. Clone your vault
git clone git@github.com:USERNAME/secrets-vault.git

# 3. Install EnvSeal
pipx install envseal-vault

# 4. Pull all environments
envseal pull my-api --env prod --replace
envseal pull my-web --env dev --replace
envseal pull my-worker --env staging --replace

# Done! All .env files restored
```

## 🔐 Security

**Age Key Management:**
- **Private key**: `~/Library/Application Support/sops/age/keys.txt` (NEVER commit!)
- **Public key**: Stored in `vault/.sops.yaml` (safe to commit)

**Backup Your Private Key:**
```bash
# Display full key file
cat ~/Library/Application\ Support/sops/age/keys.txt

# Save to password manager (1Password, Bitwarden, etc.)
```

⚠️ **Critical**: Losing your private key = permanent data loss!

**Vault Repository Best Practices:**
- ✅ Keep vault repository **private** (even though files are encrypted)
- ✅ Enable branch protection and require PR reviews
- ✅ Use GitHub's secret scanning push protection
- ✅ Backup private key in password manager

See [SECURITY.md](SECURITY.md) for complete security model.

## 🌍 Multi-Device Setup

**On a new machine:**

1. Copy your age key from backup:
   ```bash
   mkdir -p ~/Library/Application\ Support/sops/age/
   nano ~/Library/Application\ Support/sops/age/keys.txt
   # Paste the 3-line key file (created, public key, private key)
   chmod 600 ~/Library/Application\ Support/sops/age/keys.txt
   ```

2. Clone vault and install:
   ```bash
   git clone git@github.com:USERNAME/secrets-vault.git
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

```bash
# Clone repo
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

## 📝 Documentation

- [USAGE.md](USAGE.md) - Complete usage guide (Chinese)
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
