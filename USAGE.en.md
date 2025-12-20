# EnvSeal Usage Guide (English)

This guide covers installation, setup, and day-to-day use. For Chinese, see [USAGE.md](USAGE.md).

## 1. Install external tools

macOS:
```bash
brew install age sops

# Verify
age-keygen --version
sops --version
```

Linux/Windows: install `age` and `sops` with your package manager and ensure they are on PATH.

## 2. Install EnvSeal

```bash
# Recommended
pipx install envseal-vault

# Or with pip
pip install envseal-vault

# Verify
envseal --version
```

## 3. Generate an age key (optional)

If you run `envseal init`, this step is handled automatically. Use this if you want to create or inspect keys manually.

macOS:
```bash
mkdir -p ~/Library/Application\ Support/sops/age/
age-keygen -o ~/Library/Application\ Support/sops/age/keys.txt
chmod 600 ~/Library/Application\ Support/sops/age/keys.txt
age-keygen -y ~/Library/Application\ Support/sops/age/keys.txt
```

Linux key path: `~/.config/sops/age/keys.txt`  
Windows key path: `~/AppData/Local/sops/age/keys.txt`

Key safety notes:
- Back up the entire key file (it includes both public and private keys).
- Never commit the key file to Git.
- Losing the private key means you can never decrypt existing secrets.

## 4. Prepare your secrets vault

Create a private Git repository (for example `secrets-vault`) and clone it locally:
```bash
cd ~/Github
git clone git@github.com:USERNAME/secrets-vault.git
```

## 5. Initialize EnvSeal

Run init from the directory that contains your projects:
```bash
cd ~/Github
envseal init
```

Init will:
- Check or generate your age key
- Scan Git repositories under the current directory
- Ask for your vault path (for example `~/Github/secrets-vault`)
- Write `~/.config/envseal/config.yaml`
- Create `.sops.yaml` in the vault if it does not exist

To exclude or rename repos, edit the config file after init. Re-running init will overwrite the file with a fresh scan.

## 6. Daily workflow

Push secrets to the vault:
```bash
envseal push
envseal push my-project api-service
envseal push --env prod
```

Check status:
```bash
envseal status
```

Example output:
```
my-project
  ✓ .env       - up to date
  ⚠ .env.prod  - 3 keys changed

api-service
  + .env       - new file (not in vault)
  ✓ .env.prod  - up to date
```

View a key-only diff (values are never shown):
```bash
envseal diff my-project --env prod
```

Pull secrets from the vault:
```bash
# Decrypt to a temp directory and print the path
envseal pull my-project --env prod

# Replace local file (backs up to <file>.backup)
envseal pull my-project --env prod --replace

# Output to stdout
envseal pull my-project --env prod --stdout
```

## 7. Multi-device setup

1. Copy your age key file to the new device.
2. Clone your vault repo.
3. Install EnvSeal.
4. Run `envseal init` and then `envseal pull ... --replace` as needed.

## 8. Configuration reference

Config location: `~/.config/envseal/config.yaml`

Example:
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
  ".env.development": "dev"
  ".env.staging": "staging"
  ".env.prod": "prod"
  ".env.production": "prod"
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
    - ".venv"
```

Vault layout:
```
secrets/<repo>/<env>.env
```

## 9. Troubleshooting

- `sops: command not found`: install SOPS and make sure it is on PATH.
- `no key could be found`: verify your age key path and the `.sops.yaml` public key.
