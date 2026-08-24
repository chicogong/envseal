# Security Policy

## Overview

EnvSeal manages developer secrets through two explicit trust boundaries:

- **Local-only:** persistent API keys in macOS Keychain and one-shot values held for one command.
- **Portable ciphertext (opt-in):** `.env` files encrypted with SOPS + age in a user-controlled vault.

## Security Model

### What EnvSeal Does

- Encrypts .env files using SOPS with age encryption
- Stores encrypted files in a Git repository
- Provides key-only diffs (values never exposed in output)
- Manages age keys securely with proper file permissions
- Injects local Keychain references into a single trusted child process
- Blocks staged leaks with Gitleaks and full output redaction

### What EnvSeal Does NOT Do

- EnvSeal's local catalog stores only references and timestamps, never values
- EnvSeal does not transmit secrets over the network (local operations only)
- EnvSeal does not make an untrusted command safe: a child receiving a secret can read or leak it
- Environment-variable injection is a compatibility mechanism; target processes and crash dumps may expose their environment

## Best Practices

### 1. Age Key Security

- **Backup your age key**: `~/Library/Application Support/sops/age/keys.txt` (macOS), `~/.config/sops/age/keys.txt` (Linux), `~/AppData/Local/sops/age/keys.txt` (Windows)
- Store backup in a secure location (password manager, encrypted USB, etc.)
- Never commit age keys to Git
- Use different age keys for different trust boundaries if sharing vault

### Local Keychain Boundary

- New EnvSeal items are created with no application pre-trusted; macOS mediates later reads.
- Choosing "Always Allow" in a Keychain prompt weakens this boundary.
- The current CLI backend protects secrets at rest but is not isolation from malicious code already running as the same logged-in user. A signed native broker with stricter access controls is a future hardening step.

### 2. Vault Repository Security

- Keep vault repository **private** on GitHub/GitLab
- Enable branch protection on main branch
- Require pull request reviews for changes
- Enable GitHub Secret Scanning push protection

### 3. Multi-Device Setup

When syncing to a new device:
1. Copy age key to new device: `~/Library/Application Support/sops/age/keys.txt` (macOS), `~/.config/sops/age/keys.txt` (Linux), `~/AppData/Local/sops/age/keys.txt` (Windows)
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

### 5. Temporary Values and Files

- `envseal run --prompt NAME -- command` keeps a one-shot value in process memory and does not write it to disk.
- Legacy `pull` temp-file mode writes private `0600` plaintext files and does **not** auto-delete them; remove them as soon as they are no longer needed.
- Avoid passing values in argv, shell history, logs, or the clipboard.
- Run only trusted commands with injected secrets.

## Threat Model

### Protected Against

- ✅ Vault repository leak (files are encrypted)
- ✅ Accidental secret exposure in Git diffs (key-only diffs)
- ✅ Unauthorized access to vault (age encryption)
- ✅ Common accidental staged-secret commits when the optional guard is installed

### NOT Protected Against

- ❌ Age key compromise (protect your key!)
- ❌ Malicious code with filesystem access (use trusted code only)
- ❌ Physical access to unlocked computer (lock your screen)
- ❌ A malicious or compromised child process receiving an injected secret
- ❌ Secrets already committed before the guard was installed (revoke and rotate first)

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
