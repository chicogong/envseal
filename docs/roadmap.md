# EnvSeal Roadmap

Known rough edges and planned improvements. Last reviewed 2026-05-19.

## Shipped in 0.3.0

- Opt-in vault git automation — `push` / `update` accept `--commit` and `--push`
- `push` skips re-encrypting unchanged files (no more noisy vault diffs)
- `pull` temp-file mode: honest message, `0600` permissions
- `status` / `diff` / `pull`: friendly errors instead of tracebacks
- Scanner ignores `.backup`, `.example` and `.sample` files

## Known rough edges (not yet addressed)

- **No `envseal run`** — secrets can only be written to files, not injected
  into a process environment.
- **`pull` is one repo + one env at a time** — restoring a whole machine means
  many invocations; there is no `pull --all` / `restore`.
- **No `list` / `add` / `remove`** — the managed-repo set can only be changed
  by re-running `init` (which rebuilds the whole config) or editing the YAML.
- **`init` is all-or-nothing** — it registers every git repo it finds and
  overwrites any existing config; there is no interactive selection.
- **No `doctor`** — no diagnostic for the sops/age install, key permissions or
  vault state.
- **Recursive scanning collides** — the scanner walks the whole repo tree, so a
  nested `.env` (e.g. `sub/dir/.env`) maps to the same vault path as the
  top-level `.env` and the two overwrite each other.
- **Shell completion disabled** — `add_completion=False` in the Typer app.
- **`--env` default is inconsistent** — `push` / `update` default to all
  environments, `diff` / `pull` default to `prod`.
- **`status` is slow at scale** — one `sops` subprocess per vault file.
- **`pull --replace` reverse-mapping is ambiguous** — when several patterns map
  to one env name, the first match wins and may write the wrong filename.

## Planned features

- `envseal run -- <cmd>` — decrypt into the process environment and exec
- `envseal pull --all` / `restore` — one-shot full-machine restore
- `envseal list` / `add` / `remove` — manage the repo set without editing YAML
- `envseal doctor` — environment diagnostics
- Shell completion
- `.env.example` template generation
- Multi-key / team support, CI integration examples
