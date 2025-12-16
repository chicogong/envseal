# EnvSeal 使用指南

## 📦 完整设置流程

### 1. 安装外部依赖

```bash
# macOS
brew install age sops

# 验证安装
age-keygen --version
sops --version
```

### 2. 生成 Age 密钥

```bash
# 创建密钥目录
mkdir -p ~/Library/Application\ Support/sops/age/

# 生成密钥（会输出 public key）
age-keygen -o ~/Library/Application\ Support/sops/age/keys.txt

# 设置权限
chmod 600 ~/Library/Application\ Support/sops/age/keys.txt

# 查看公钥
age-keygen -y ~/Library/Application\ Support/sops/age/keys.txt
```

#### 🔐 密钥安全说明（必读！）

**密钥文件内容：**
```bash
# created: 2025-12-16T11:18:11+08:00
# public key: age1a9x8...（公钥，可以公开）
AGE-SECRET-KEY-...（私钥，必须保密！）
```

**公钥 vs 私钥：**

| 项目 | 说明 | 可以公开？ | 用途 |
|------|------|-----------|------|
| **公钥** | `age1...` | ✅ 可以 | 加密文件（写入 `.sops.yaml`） |
| **私钥** | `AGE-SECRET-KEY-...` | ❌ 绝对不行！ | 解密文件（保存在本地） |

**⚠️ 安全规则：**

1. **必须备份私钥文件**（整个 `keys.txt` 文件）
   ```bash
   # 备份方法（选一）：
   # - 放到密码管理器（1Password、Bitwarden）
   # - 加密后存云盘
   # - 打印到纸上放保险柜
   ```

2. **绝对不能提交到 Git**
   ```bash
   # ❌ 不要这样做：
   git add ~/Library/Application\ Support/sops/age/keys.txt

   # ✅ 只能提交公钥到 .sops.yaml：
   cd secrets-vault
   git add .sops.yaml  # 这个文件只包含公钥，可以提交
   ```

3. **丢失私钥 = 无法解密**
   - 已加密的 secrets 将永久无法访问
   - 必须重新生成密钥并重新加密所有文件

4. **解密是自动的**
   ```bash
   # envseal 会自动找到并使用私钥解密
   envseal pull my-project --env prod

   # 手动解密（了解原理）：
   export SOPS_AGE_KEY_FILE=~/Library/Application\ Support/sops/age/keys.txt
   sops -d secrets/my-project/prod.env
   ```

**💡 现在就备份：**
```bash
# 显示完整密钥文件，复制到密码管理器
cat ~/Library/Application\ Support/sops/age/keys.txt
```

### 3. 配置 secrets-vault

```bash
cd ~/Github/secrets-vault

# 编辑 .sops.yaml，替换 YOUR_AGE_PUBLIC_KEY_HERE 为实际公钥
nano .sops.yaml

# 示例（用你的实际公钥）：
# creation_rules:
#   - path_regex: ^secrets/.*\.env$
#     input_type: dotenv
#     age: age1abc123xyz...

# 提交配置
git add .sops.yaml
git commit -m "config: add age public key to .sops.yaml"
git push
```

### 4. 初始化 envseal

```bash
cd ~/Github

# 运行 init（交互式）
envseal init
```

**init 会做什么：**
1. 检查 age 密钥（已存在会跳过生成）
2. 扫描当前目录下的所有 Git 仓库
3. 让你选择要管理的仓库
4. 询问 vault 路径（`~/Github/secrets-vault`）
5. 生成配置文件：`~/.config/envseal/config.yaml`
6. 在 vault 创建 `.sops.yaml`（如果不存在）

**示例交互：**
```
🔍 Initializing envseal...

🔐 Checking age encryption key...
✅ Age key found at ~/Library/Application Support/sops/age/keys.txt

🔍 Scanning for Git repositories in ~/Github...
Found 5 repositories:
  [1] envseal (~/Github/chicogong/envseal)
  [2] my-project (~/Github/my-project)
  [3] api-service (~/Github/api-service)
  ...

Select repositories to manage (comma-separated, e.g., 1,2,3): 2,3

📝 Where is your secrets-vault repository?
Path [~/Github/secrets-vault]: (直接回车)

✅ Configuration saved to ~/.config/envseal/config.yaml
✅ Created .sops.yaml in vault

📦 Next steps:
  1. Run: envseal push to sync secrets to vault
  2. cd ~/Github/secrets-vault
  3. git add . && git commit -m 'Initial secrets import'
  4. git push
```

## 🚀 日常使用

### 推送 secrets 到 vault

```bash
# 推送所有配置的仓库
envseal push

# 只推送特定仓库
envseal push my-project api-service

# 只推送特定环境
envseal push --env prod
```

**会发生什么：**
1. 扫描仓库找到所有 `.env*` 文件
2. 解析并规范化（按 key 排序）
3. 用 SOPS + age 加密
4. 写入 `secrets-vault/secrets/<repo>/<env>.env`

**然后提交到 vault：**
```bash
cd ~/Github/secrets-vault
git status
git diff  # 查看加密文件的变化（看不到 value，只能看到 SOPS 元数据）
git add .
git commit -m "Update secrets for my-project"
git push
```

### 查看状态

```bash
# 查看所有仓库的同步状态
envseal status
```

**输出示例：**
```
📊 Secrets Status:

my-project
  ✓ dev.env       - up to date
  ⚠ prod.env      - 3 keys changed

api-service
  + local.env     - new file (not in vault)
  ✓ prod.env      - up to date

Use 'envseal diff <repo>' to see details.
```

### 查看 diff（只显示 keys）

```bash
# 查看具体哪些 keys 变了
envseal diff my-project --env prod
```

**输出示例：**
```
📝 Changes in my-project/prod.env:

+ ADDED:
  - NEW_API_KEY
  - REDIS_HOST

~ MODIFIED:
  - DATABASE_URL

- REMOVED:
  - OLD_SERVICE_URL

Use 'envseal push my-project --env prod' to sync.
```

**注意：**只显示 key 名称，不显示 value（安全！）

### 从 vault 拉取 secrets

```bash
# 解密到临时目录（默认，安全）
envseal pull my-project --env prod
# 输出：✅ Decrypted to: /tmp/envseal-XXXXX/prod.env

# 直接覆盖本地文件（谨慎！）
envseal pull my-project --env prod --replace
# 会备份原文件到 .env.backup

# 输出到标准输出
envseal pull my-project --env prod --stdout
```

## 🔐 多设备同步

### 在新机器上设置

**1. 复制 age 私钥文件**

在原机器：
```bash
# 显示完整的密钥文件（包含公钥和私钥）
cat ~/Library/Application\ Support/sops/age/keys.txt
```

在新机器：
```bash
mkdir -p ~/Library/Application\ Support/sops/age/
nano ~/Library/Application\ Support/sops/age/keys.txt
# 粘贴完整内容（包括注释、公钥、私钥三行）
# created: ...
# public key: age1...
# AGE-SECRET-KEY-...
chmod 600 ~/Library/Application\ Support/sops/age/keys.txt
```

**⚠️ 重要：**必须复制**整个文件**（3行），不是只复制公钥或私钥！

**2. 克隆 vault**

```bash
cd ~/Github
git clone git@github.com:chicogong/secrets-vault.git
```

**3. 安装 envseal**

```bash
# 如果你的 envseal 还没有发布到 PyPI
cd ~/Github/chicogong/envseal
pip install -e .

# 或者（推荐）
pipx install -e ~/Github/chicogong/envseal
```

**4. 初始化并拉取**

```bash
cd ~/Github
envseal init
# 选择仓库，指向 vault

# 拉取 secrets
envseal pull my-project --env prod --replace
envseal pull api-service --env prod --replace
```

## 📁 配置文件位置

```
~/.config/envseal/config.yaml         # envseal 配置
~/Library/Application Support/sops/age/keys.txt  # age 密钥
~/Github/secrets-vault/  # vault 仓库
```

## 🛠️ 开发者命令

```bash
# 查看配置
cat ~/.config/envseal/config.yaml

# 手动编辑配置
nano ~/.config/envseal/config.yaml

# 添加新仓库
envseal add /path/to/new-repo

# 移除仓库
envseal remove repo-name

# 列出所有管理的仓库
envseal list
```

## ⚠️ 常见问题

### Q: envseal push 失败，提示 "sops: command not found"
A: 需要安装 SOPS：`brew install sops`

### Q: 加密失败，提示 "no key could be found"
A: 检查：
1. age 密钥是否存在：`ls -la ~/Library/Application\ Support/sops/age/keys.txt`
2. `.sops.yaml` 中的公钥是否正确
3. 运行 `age-keygen -y ~/Library/Application\ Support/sops/age/keys.txt` 查看公钥

### Q: 如何知道哪个 .env 文件映射到哪个环境？
A: 默认映射（可在配置中修改）：
- `.env` → `local`
- `.env.dev` → `dev`
- `.env.production` → `prod`
- `.env.staging` → `staging`

### Q: 可以在不同项目使用不同的环境名吗？
A: 可以！编辑 `~/.config/envseal/config.yaml` 中的 `env_mapping`

### Q: secrets-vault 可以公开吗？
A: **绝对不行！**即使文件已加密，仍应保持私有。

### Q: 如何与团队共享 secrets？
A: 见 [secrets-vault/README.md](../secrets-vault/README.md) 的"Team Sharing"部分。

## 📝 最佳实践

1. **定期推送**：修改 `.env` 后立即 `envseal push`
2. **commit 前 diff**：推送前用 `envseal diff` 检查变更
3. **备份密钥**：将 age 密钥存到密码管理器
4. **使用 pull --replace 谨慎**：会覆盖本地文件
5. **不要提交明文 .env**：在项目中加 `.env` 到 `.gitignore`
6. **vault 开启分支保护**：要求 PR review

## 🎯 完整工作流示例

```bash
# 1. 日常开发：修改 .env
cd ~/Github/my-project
echo "NEW_API_KEY=abc123" >> .env.prod

# 2. 检查变更
envseal status
envseal diff my-project --env prod

# 3. 推送到 vault
envseal push my-project --env prod

# 4. 提交 vault 变更
cd ~/Github/secrets-vault
git add .
git commit -m "Add NEW_API_KEY to my-project prod"
git push

# 5. 其他开发者同步
# (在另一台机器)
cd ~/Github/secrets-vault
git pull
envseal pull my-project --env prod --replace
```

## 📚 更多信息

- [README.md](./README.md) - 项目概述
- [SECURITY.md](./SECURITY.md) - 安全策略
- [secrets-vault README](../secrets-vault/README.md) - Vault 使用说明
