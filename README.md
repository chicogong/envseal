<div align="center">

# 🔐 EnvSeal

**Secure, centralized management for environment variables across multiple projects**

[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

[English](#english) | [中文](#中文)

</div>

---

## English

### 📖 What is EnvSeal?

EnvSeal is a CLI tool that helps you manage `.env` files across multiple repositories with **end-to-end encryption**. It scans your projects, normalizes environment files, and syncs them to a Git-backed vault using SOPS encryption.

**Key Benefits:**
- 🔒 **Secure**: Uses SOPS + age encryption (modern, battle-tested)
- 📦 **Centralized**: One vault for all your secrets across all projects
- 🔍 **Safe Diffs**: Only shows key names, never values
- 🔄 **Version Control**: Full Git history for audit and rollback
- 🚀 **Simple**: One command to sync everything

### 🎯 Use Cases

- **Individual Developers**: Manage secrets across 10+ personal projects
- **Multi-Device Setup**: Sync secrets between work laptop and home desktop
- **Team Collaboration**: Share secrets securely via private Git repo
- **Secret Rotation**: Track when and why secrets changed with Git history

### ⚡ Quick Start

#### Prerequisites

```bash
# macOS
brew install age sops

# Verify installation
age-keygen --version
sops --version
```

#### Installation

```bash
# Install globally with pipx (recommended)
pipx install envseal

# Or with pip
pip install envseal
```

#### Initialize

```bash
cd ~/your-projects-directory
envseal init
```

This will:
1. ✅ Generate an age encryption key
2. 🔍 Scan for Git repositories
3. 📝 Create configuration at `~/.config/envseal/config.yaml`
4. 🗂️ Set up vault structure

#### Sync Secrets

```bash
# Push all .env files to vault (encrypted)
envseal push

# Commit to vault
cd ~/Github/secrets-vault
git add .
git commit -m "Add encrypted secrets"
git push
```

#### Check Status

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

### 📚 Commands

| Command | Description | Options |
|---------|-------------|---------|
| `envseal init` | Initialize configuration and generate keys | `--root DIR` |
| `envseal push [repos...]` | Encrypt and push secrets to vault | `--env ENV` |
| `envseal status` | Show sync status for all repos | - |
| `envseal diff REPO` | Show key-only changes | `--env ENV` |
| `envseal pull REPO` | Decrypt and pull from vault | `--env ENV`, `--replace`, `--stdout` |

### 🔐 Security

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

### 🌍 Multi-Device Setup

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
   git clone git@github.com:you/secrets-vault.git
   pipx install envseal
   envseal init
   ```

3. Pull secrets:
   ```bash
   envseal pull my-project --env prod --replace
   ```

### 📁 Configuration

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

### 🛠️ Development

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

### 📝 Documentation

- [USAGE.md](USAGE.md) - Complete usage guide (Chinese)
- [SECURITY.md](SECURITY.md) - Security model and best practices

### 🤝 Contributing

Contributions welcome! Please feel free to submit a Pull Request.

### 📄 License

Apache-2.0 License - see [LICENSE](LICENSE) for details.

---

## 中文

### 📖 EnvSeal 是什么？

EnvSeal 是一个 CLI 工具，帮助你**安全地管理多个项目的 `.env` 文件**。它会扫描你的项目，规范化环境变量文件，并使用 SOPS 加密同步到一个 Git 仓库（vault）中。

**核心优势：**
- 🔒 **安全加密**：使用 SOPS + age 加密（现代、经过实战检验）
- 📦 **集中管理**：一个 vault 管理所有项目的密钥
- 🔍 **安全 Diff**：只显示 key 名称，绝不暴露 value
- 🔄 **版本控制**：完整的 Git 历史，可审计、可回滚
- 🚀 **操作简单**：一条命令同步所有项目

### 🎯 使用场景

- **个人开发者**：管理 10+ 个个人项目的密钥
- **多设备同步**：工作电脑和家用电脑之间同步密钥
- **团队协作**：通过私有 Git 仓库安全分享密钥
- **密钥轮换**：用 Git 历史追踪密钥变更原因

### ⚡ 快速开始

#### 安装依赖

```bash
# macOS
brew install age sops

# 验证安装
age-keygen --version
sops --version
```

#### 安装 EnvSeal

```bash
# 使用 pipx 全局安装（推荐）
pipx install envseal

# 或使用 pip
pip install envseal
```

#### 初始化

```bash
cd ~/your-projects-directory
envseal init
```

初始化会：
1. ✅ 生成 age 加密密钥
2. 🔍 扫描 Git 仓库
3. 📝 创建配置文件 `~/.config/envseal/config.yaml`
4. 🗂️ 设置 vault 结构

#### 同步密钥

```bash
# 推送所有 .env 文件到 vault（加密）
envseal push

# 提交到 vault
cd ~/Github/secrets-vault
git add .
git commit -m "Add encrypted secrets"
git push
```

#### 查看状态

```bash
envseal status
```

**输出示例：**
```
📊 Checking secrets status...

my-project
  ✓ .env       - 已同步
  ⚠ prod.env   - 3 个 key 有变化

api-service
  + local.env  - 新文件（未加入 vault）
  ✓ prod.env   - 已同步
```

### 📚 命令列表

| 命令 | 说明 | 选项 |
|------|------|------|
| `envseal init` | 初始化配置并生成密钥 | `--root DIR` |
| `envseal push [repos...]` | 加密并推送 secrets 到 vault | `--env ENV` |
| `envseal status` | 查看所有仓库的同步状态 | - |
| `envseal diff REPO` | 查看某个仓库的 key 变化 | `--env ENV` |
| `envseal pull REPO` | 从 vault 解密并拉取 | `--env ENV`, `--replace`, `--stdout` |

### 🔐 安全说明

**Age 密钥管理：**
- **私钥**：`~/Library/Application Support/sops/age/keys.txt`（绝对不能提交到 Git！）
- **公钥**：存储在 `vault/.sops.yaml`（可以提交）

**备份私钥：**
```bash
# 显示完整密钥文件
cat ~/Library/Application\ Support/sops/age/keys.txt

# 保存到密码管理器（1Password、Bitwarden 等）
```

⚠️ **警告**：丢失私钥 = 永久无法解密！

详见 [SECURITY.md](SECURITY.md)。

### 🌍 多设备同步

**在新机器上：**

1. 从备份复制 age 密钥：
   ```bash
   mkdir -p ~/Library/Application\ Support/sops/age/
   nano ~/Library/Application\ Support/sops/age/keys.txt
   # 粘贴 3 行密钥文件（created、public key、private key）
   chmod 600 ~/Library/Application\ Support/sops/age/keys.txt
   ```

2. 克隆 vault 并安装：
   ```bash
   git clone git@github.com:USERNAME/secrets-vault.git
   pipx install envseal
   envseal init
   ```

3. 拉取密钥：
   ```bash
   envseal pull my-project --env prod --replace
   ```

### 📁 配置文件

**位置**：`~/.config/envseal/config.yaml`

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

### 🛠️ 开发

```bash
# 克隆仓库
git clone https://github.com/chicogong/envseal.git
cd envseal

# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest

# 代码检查和格式化
make lint
make format

# 类型检查
make type-check
```

### 📝 文档

- [USAGE.md](USAGE.md) - 完整使用指南（中文）
- [SECURITY.md](SECURITY.md) - 安全模型和最佳实践

### 🤝 贡献

欢迎贡献！请随时提交 Pull Request。

### 📄 许可证

Apache-2.0 许可证 - 详见 [LICENSE](LICENSE)。

---

<div align="center">

**Made with ❤️ by developers, for developers**

[Report Bug](https://github.com/chicogong/envseal/issues) · [Request Feature](https://github.com/chicogong/envseal/issues)

</div>
