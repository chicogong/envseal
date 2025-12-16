# envseal

EnvSeal is a CLI tool that scans `.env*` files across multiple repositories, normalizes them, and syncs them into a centralized Git-backed vault as SOPS-encrypted dotenv files, providing safe key-only diffs and versioned rollback.

## Features

- 🔐 **Secure**: SOPS encryption with age keys
- 📦 **Centralized**: Git-backed vault for all your secrets
- 🔍 **Transparent**: Key-only diffs (values never exposed)
- 🔄 **Versioned**: Full Git history for rollback
- 🚀 **Simple**: One command to sync all repos

## Prerequisites

- Python 3.9+
- [SOPS](https://github.com/getsops/sops) CLI
- [age](https://github.com/FiloSottile/age) CLI

```bash
# macOS
brew install sops age

# Linux
# See installation instructions for your distro
```

## Installation

```bash
pipx install envseal
```

## Quick Start

1. **Initialize** (first time setup):
```bash
cd ~/your-projects-parent-dir
envseal init
```

2. **Push secrets to vault**:
```bash
envseal push
```

3. **Commit to vault**:
```bash
cd ~/Github/secrets-vault
git add .
git commit -m "Initial secrets import"
git push
```

4. **Check status**:
```bash
envseal status
```

5. **Pull secrets on a new machine**:
```bash
envseal pull my-project --env prod --replace
```

## Commands

### `envseal init`
Initialize configuration, generate age key, scan for repos

### `envseal push [repos...]`
Push .env files to vault and encrypt
- `--env ENV`: Only push specific environment

### `envseal status`
Show sync status for all repos

### `envseal diff REPO`
Show key-only diff for a repo
- `--env ENV`: Environment to compare (default: prod)

### `envseal pull REPO`
Pull and decrypt from vault
- `--env ENV`: Environment to pull (default: prod)
- `--replace`: Overwrite local .env file
- `--stdout`: Output to stdout

## Configuration

Config location: `~/.config/envseal/config.yaml`

```yaml
vault_path: /path/to/secrets-vault
repos:
  - name: project1
    path: /path/to/project1
env_mapping:
  ".env": "local"
  ".env.prod": "prod"
```

## Security

See [SECURITY.md](SECURITY.md) for security considerations and best practices.

## License

Apache-2.0
