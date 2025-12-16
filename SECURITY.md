# Security Policy

## Overview

EnvSeal is designed to securely manage environment variables across multiple projects using SOPS encryption with age keys.

## Security Model

### What EnvSeal Does

- Encrypts .env files using SOPS with age encryption
- Stores encrypted files in a Git repository
- Provides key-only diffs (values never exposed in output)
- Manages age keys securely with proper file permissions

### What EnvSeal Does NOT Do

- EnvSeal does not store secrets itself (stateless CLI)
- EnvSeal does not transmit secrets over the network (local operations only)
- EnvSeal does not provide access control (use Git repository permissions)

## Best Practices

### 1. Age Key Security

- **Backup your age key**: `~/Library/Application Support/sops/age/keys.txt` (macOS)
- Store backup in a secure location (password manager, encrypted USB, etc.)
- Never commit age keys to Git
- Use different age keys for different trust boundaries if sharing vault

### 2. Vault Repository Security

- Keep vault repository **private** on GitHub/GitLab
- Enable branch protection on main branch
- Require pull request reviews for changes
- Enable GitHub Secret Scanning push protection

### 3. Multi-Device Setup

When syncing to a new device:
1. Copy age key to new device: `~/Library/Application Support/sops/age/keys.txt`
2. Set permissions: `chmod 600 <key-file>`
3. Clone vault repository
4. Run `envseal pull` to restore secrets

### 4. Team Sharing (Advanced)

To share vault with team members:
1. Each member generates their own age key
2. Add all public keys to `.sops.yaml`:
   ```yaml
   creation_rules:
     - path_regex: ^secrets/.*\.env$
       input_type: dotenv
       age: >-
         age1abc...,
         age1def...,
         age1ghi...
   ```
3. Re-encrypt all files: `sops updatekeys secrets/**/*.env`

### 5. Temporary Files

- Temporary decrypted files are created in `/tmp` with random names
- Files are automatically cleaned up on process exit
- Never commit temporary files to Git

## Threat Model

### Protected Against

- ✅ Vault repository leak (files are encrypted)
- ✅ Accidental secret exposure in Git diffs (key-only diffs)
- ✅ Unauthorized access to vault (age encryption)

### NOT Protected Against

- ❌ Age key compromise (protect your key!)
- ❌ Malicious code with filesystem access (use trusted code only)
- ❌ Physical access to unlocked computer (lock your screen)

## Reporting Security Issues

If you discover a security vulnerability, please email: security@example.com

**Do not** open public GitHub issues for security vulnerabilities.

## Dependencies

EnvSeal relies on:
- SOPS (maintained by Mozilla, now community)
- age (maintained by Filippo Valsorda)

Keep these tools updated:
```bash
brew upgrade sops age
```

## Compliance Notes

- EnvSeal does not transmit data to external services
- All encryption happens locally
- Vault storage is user-controlled (your Git repository)
- No telemetry or usage tracking
