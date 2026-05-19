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

- Keep PyPI keywords and classifiers accurate and current.
- A short comparison page (`vs dotenvx`, `vs sops`) helps users searching for
  alternatives.
- Repo polish: an accurate "About" blurb and topics, a social-preview image,
  CI and version badges.
- Make license metadata consistent — the `LICENSE` file, `pyproject.toml` and
  the README should agree. They currently disagree: the `LICENSE` file is MIT
  while `pyproject.toml` and the README state Apache-2.0.
