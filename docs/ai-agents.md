# Using EnvSeal with AI Coding Agents

EnvSeal exists because AI coding (Claude Code, Cursor, Copilot, …) makes you
spin up *many* small projects — each with its own `.env`. This page shows how
to make your AI agent **EnvSeal-aware** so it fetches secrets itself instead
of asking you or hallucinating placeholder values.

---

## 1. Make a project EnvSeal-aware (drop-in snippet)

Paste this into the project's agent-instructions file — `CLAUDE.md`,
`AGENTS.md`, `.cursorrules`, or `.github/copilot-instructions.md`. The agent
then knows where the secrets are and how to get them.

```markdown
## Secrets & environment variables

This project's `.env*` files are **not committed**. They are managed with
EnvSeal (https://github.com/chicogong/envseal) — encrypted in a separate vault.

- To create the local `.env`, run: `envseal pull <PROJECT> --env local --replace`
- After editing a secret, sync it back: `envseal push --commit`
- To see which keys exist *without* decrypting: `envseal list`
- Never commit `.env*` files, never print secret values into chat or logs.
```

Replace `<PROJECT>` with this repo's name as registered in EnvSeal.

> Why it helps: when the agent hits a missing `.env`, it runs one command
> instead of stalling, inventing fake keys, or pasting real secrets into the
> conversation.

---

## 2. Prompt: set up EnvSeal across all your projects

Paste this to your AI agent to onboard a whole machine:

```text
Install and set up EnvSeal so my projects' .env files are encrypted and
centralized.

1. Install the prerequisites: `age` and `sops` (Homebrew on macOS), then
   `pipx install envseal-vault`.
2. Run `envseal init` and point it at the folder that contains my repos.
3. Run `envseal push --commit` to encrypt every .env into the vault.
4. Show me `envseal report -o envseal-report.html` and summarize how many
   projects and keys were captured.

Rules: never print decrypted secret values; only ever show key NAMES.
```

---

## 3. Prompt: restore secrets on a new machine

```text
This machine is fresh. Restore my project secrets with EnvSeal:

1. Install `age`, `sops`, and `pipx install envseal-vault`.
2. Put my age private key at the OS key path (I will paste it; do not echo it
   back).
3. Clone my secrets vault repo and run `envseal init`.
4. For the project in the current directory, run
   `envseal pull <PROJECT> --env local --replace`.
```

---

## 4. Browse keys without decrypting

`envseal report` writes a self-contained static HTML dashboard of every
project and **key name** (never values). It is safe to hand to an agent, a
teammate, or a wiki — point your agent at it when it needs to know *which*
keys a project expects:

```bash
envseal report -o envseal-report.html
```

---

## House rule for any agent

**Key names are shareable; key values are not.** Every EnvSeal read command
(`list`, `report`, `diff`) is key-only by design. Keep it that way in your
prompts: ask agents to reason about key *names*, and to materialize values
only into `.env` files via `envseal pull` — never into chat, commits, or logs.
