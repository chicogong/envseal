# Discoverability & Positioning Notes

Research notes on EnvSeal's positioning and discoverability. 2026-05.

## Naming

The brand is "EnvSeal", but the PyPI name `envseal` was already taken by an
unrelated project, so this package is published as **`envseal-vault`**. The
repository and CLI command are `envseal`; the installable package is
`envseal-vault`. Worth keeping that distinction consistent across the docs, and
a future rename is a candidate if the split keeps causing confusion.

## Positioning

Most encrypted-dotenv tools (dotenvx, dotenv-vault, sealenv, SOPS on its own,
Infisical, Doppler) are single-repo or service-based. EnvSeal's distinct niche
is **multi-repo / many-projects** management: scan N repositories, keep one
central encrypted vault, diff key-only, restore a whole machine with one
command. The "AI coding produces many small projects" framing in the README
leans into exactly this.

## Discoverability checklist

- ✅ Keep PyPI keywords and classifiers accurate and current — refreshed in
  0.3.1 (Python 3.13, `Environment :: Console`, `Topic :: Utilities`, etc.).
- ✅ A short comparison (`vs dotenvx`, `vs sops`, `vs dotenv-vault`, `vs
  Doppler`) — added as a "How EnvSeal Compares" table in the README (0.3.1).
- ✅ License metadata is now consistent — the `LICENSE` file, `pyproject.toml`,
  the README and the PyPI classifiers all state Apache-2.0 (0.3.1; the
  `LICENSE` file was MIT through 0.1.0–0.3.0).
- ✅ Version / CI badges in the README (PyPI, Python versions, downloads, CI).
- ☐ Still open: a social-preview image for the GitHub repo (needs a designed
  PNG uploaded in repo settings — cannot be done from the repo tree).
- ☐ Still open: announce on the channels developers actually search —
  see "Where to announce" below.

## Where to announce

EnvSeal is installable and documented; the remaining discoverability work is
getting it in front of people. Highest-signal, lowest-effort first:

- **GitHub Topics + About** — keep topics in sync with the positioning above.
- **r/devops, r/Python, r/commandline** — a short "I built X because Y" post.
- **Hacker News "Show HN"** — link the repo; the multi-repo + AI-coding angle
  is the hook.
- **Awesome lists** — PRs to `awesome-devops`, `awesome-cli-apps`,
  `awesome-python`, and any `awesome-secrets-management` list.
- **dev.to / a blog post** — "Managing .env across 30 repos with one encrypted
  vault"; cross-link from the README.
- **SOPS / age communities** — EnvSeal is a friendly wrapper around them;
  their discussion spaces are warm audiences.
