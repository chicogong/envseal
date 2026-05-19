# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-05-19

### Added
- `push` and `update` accept `--commit` / `--push` flags that commit (and push) the vault repository automatically; without the flags the manual git steps are printed as before
- `VaultManager` gained `is_git_repo` / `git_commit` / `git_push` helpers

### Changed
- `push` skips re-encrypting unchanged files, so SOPS's non-deterministic output no longer produces noisy vault git diffs
- A nested `.env` (e.g. `sub/dir/.env`) is stored at a vault path mirroring its location (`secrets/<repo>/sub/dir/<env>.env`) instead of colliding with — and silently overwriting — the repo's root `.env`

### Fixed
- `pull` temp-file mode no longer falsely claims the decrypted file is auto-deleted; the file is created with `0600` permissions and the message is accurate
- `status`, `diff` and `pull` print a friendly "run envseal init" message instead of a traceback when the config or age key is missing
- The scanner no longer ingests `.backup` files (left by `pull --replace`) or `.example` / `.sample` template files as real env files

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

[0.3.0]: https://github.com/chicogong/envseal/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/chicogong/envseal/compare/v0.1.2...v0.2.0
[0.1.2]: https://github.com/chicogong/envseal/releases/tag/v0.1.2
