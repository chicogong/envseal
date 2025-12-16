<div align="center">

# 🔐 EnvSeal

**Secure, centralized management for environment variables across multiple projects**

[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

[English](README.md) | [中文](README.zh-CN.md)

</div>

---

## 📖 What is EnvSeal?

EnvSeal is a CLI tool that helps you manage `.env` files across multiple repositories with **end-to-end encryption**. It scans your projects, normalizes environment files, and syncs them to a Git-backed vault using SOPS encryption.

**Key Benefits:**
- 🔒 **Secure**: Uses SOPS + age encryption (modern, battle-tested)
- 📦 **Centralized**: One vault for all your secrets across all projects
- 🔍 **Safe Diffs**: Only shows key names, never values
- 🔄 **Version Control**: Full Git history for audit and rollback
- 🚀 **Simple**: One command to sync everything

## 🎯 Use Cases

- **Individual Developers**: Manage secrets across 10+ personal projects
- **Multi-Device Setup**: Sync secrets between work laptop and home desktop
- **Team Collaboration**: Share secrets securely via private Git repo
- **Secret Rotation**: Track when and why secrets changed with Git history

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

**Currently in development - install from source:**

```bash
# Clone the repository
git clone https://github.com/chicogong/envseal.git
cd envseal

# Install globally with pipx (recommended)
pipx install .

# Or with pip
pip install .
```

> **Note**: PyPI package coming soon. Once published, you'll be able to install with `pipx install envseal`.

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

⚠️ **Warning**: Losing your private key = permanent data loss!

See [SECURITY.md](SECURITY.md) for details.

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
   pipx install envseal
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

## 🤝 Contributing

Contributions welcome! Please feel free to submit a Pull Request.

## 📄 License

Apache-2.0 License - see [LICENSE](LICENSE) for details.

---

<div align="center">

**Made with ❤️ by developers, for developers**

[Report Bug](https://github.com/chicogong/envseal/issues) · [Request Feature](https://github.com/chicogong/envseal/issues)

</div>
