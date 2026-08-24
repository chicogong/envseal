# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2026-08-24

### Added
- Local macOS Keychain backend for persistent developer API keys. Writes use the native hidden `security` prompt, so values never enter command arguments or EnvSeal's catalog.
- `envseal run` for just-in-time injection of Keychain references and one-shot prompted values into one trusted child process.
- Value-free local metadata catalog with private `0700` directory / `0600` file permissions.
- `envseal guard staged` and `guard install`, backed by Gitleaks with full value redaction and refusal to overwrite existing hooks.
- `envseal doctor` checks local prerequisites without reading Keychain values or decrypting the legacy SOPS vault.

### Fixed
- Existing mypy failures in the interactive selector, change collector, and update command.

### Changed
- Split the local secret, runtime injection, guard, and doctor CLI surface out of the legacy monolithic CLI module for clearer maintenance.
- `envseal secret list --verify` checks Keychain presence without reading values; stale metadata can be removed explicitly with `secret remove --catalog-only`.

## [0.3.2] - 2026-05-19

### Fixed
- The interactive `update` selector rendered `str(table)` — a Rich object repr (`<rich.table.Table object at 0x…>`) — instead of the repo list. It now wraps the table in a `rich.console.Group` so the picker shows the actual repos (bug present since `update` shipped in 0.2.0)

### Added
- `docs/ai-agents.md` — ready-to-paste prompts that make AI coding agents (Claude Code, Cursor, …) EnvSeal-aware: a project snippet, a machine-onboarding prompt, and a new-machine restore prompt
- README (EN + zh-CN) gains a "Using EnvSeal with AI Coding Agents" section
- A static landing page (`docs/index.html`), published via GitHub Pages

## [0.3.1] - 2026-05-19

### Fixed
- The `LICENSE` file is now Apache-2.0, matching `pyproject.toml`, the README and the PyPI classifiers (it was previously MIT — an inconsistency that shipped in 0.1.0–0.3.0)

### Changed
- PyPI classifiers add Python 3.13, `Python :: 3 :: Only`, `Environment :: Console`, `Topic :: Utilities` and a System Administrators audience for better discoverability
- README adds a comparison table positioning EnvSeal against dotenvx / SOPS / dotenv-vault / Doppler

### Docs
- The bundled Chinese README and the `USAGE.md` / `USAGE.en.md` guides now document `list`, `report` and the `--commit` / `--push` flags (the English README already did in 0.3.0)

## [0.3.0] - 2026-05-19

### Added
- `push` and `update` accept `--commit` / `--push` flags that commit (and push) the vault repository automatically; without the flags the manual git steps are printed as before
- `VaultManager` gained `is_git_repo` / `git_commit` / `git_push` helpers
- `envseal list` and `envseal report` — browse every project's secrets (key names only, never values); `report` writes a self-contained static HTML dashboard with stat cards, project/key search, collapsible per-project cards, click-to-copy `pull` commands, and a light/dark theme toggle

### Changed
- `push` skips re-encrypting unchanged files, so SOPS's non-deterministic output no longer produces noisy vault git diffs
- A nested `.env` (e.g. `sub/dir/.env`) is stored at a vault path mirroring its location (`secrets/<repo>/sub/dir/<env>.env`) instead of colliding with — and silently overwriting — the repo's root `.env`
- `diff` and `pull` now cover every env file in a repo — including nested ones — instead of only the first match

### Fixed
- `pull` temp-file mode no longer falsely claims the decrypted file is auto-deleted; the file is created with `0600` permissions and the message is accurate
- `status`, `diff` and `pull` print a friendly "run envseal init" message instead of a traceback when the config or age key is missing
- The scanner no longer ingests `.backup` files (left by `pull --replace`) or `.example` / `.sample` template files as real env files
- `pull --stdout` is written raw instead of through Rich, which line-wrapped output at 80 columns when redirected to a file and corrupted any value longer than the wrap point
- `pull --stdout` for an environment backed by multiple env files guarantees a newline between concatenated files and prints a stderr heads-up; the HTML report no longer offers a single-file `--stdout` copy command for such environments (it points to `--replace` instead)

## [0.2.0] - 2025-12-23

### Added
- **New `envseal update` command** - Interactive batch update for changed secrets
  - Scans all repositories for changed .env files
  - Shows interactive selection menu with keyboard navigation
  - Smart re-verification to skip files with no actual value changes
  - Only re-encrypts when content truly differs (prevents unnecessary git diffs)
  - Supports `--env` filter for specific environments
- New `ChangeCollector` component for detecting changes across repositories
- New `InteractiveSelector` component for terminal UI with keyboard controls
  - Arrow keys (↑↓) or vim keys (jk) for navigation
  - Spacebar to toggle selection
  - 'a' to select all, 'n' to deselect all
  - Enter to confirm, q/Esc to cancel

### Changed
- Update command now verifies changes twice before encryption to avoid unnecessary re-encryption
- Improved user feedback with skip notifications when no changes detected

### Fixed
- Prevented re-encryption of files when only formatting differs (not actual values)

## [0.1.2] - 2025-12-16

### Changed
- Updated package references and improved installation instructions
- Optimized documentation wording

## [0.1.1] - Previous releases

(Release history prior to 0.2.0 - see git tags for details)

---

[0.4.0]: https://github.com/chicogong/envseal/compare/v0.3.2...v0.4.0
[0.3.0]: https://github.com/chicogong/envseal/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/chicogong/envseal/compare/v0.1.2...v0.2.0
[0.1.2]: https://github.com/chicogong/envseal/releases/tag/v0.1.2
