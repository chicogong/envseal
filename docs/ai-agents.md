# Using EnvSeal with AI Coding Agents

EnvSeal exists because AI coding (Claude Code, Cursor, Copilot, …) makes you
spin up *many* small projects — each with its own `.env`. This page shows how
to make your AI agent **EnvSeal-aware** without giving it a reason to reveal,
copy, or persist secret values.

---

## 1. Make a project EnvSeal-aware (drop-in snippet)

Paste this into the project's agent-instructions file — `CLAUDE.md`,
`AGENTS.md`, `.cursorrules`, or `.github/copilot-instructions.md`. The agent
then knows where the secrets are and how to get them.

```markdown
## Secrets & environment variables

This project's secrets are **not committed**. They are managed with EnvSeal
(https://github.com/chicogong/envseal) using local references by default.

- To see local references without values, run: `envseal secret list`
- Run a trusted command with an approved reference:
  `envseal run --secret NAME=<PROJECT>/<ENV>/<NAME> -- <command>`
- A human adds or changes values with `envseal secret put`; do not request the value in chat.
- Treat legacy `push`, `pull`, and Git-vault operations as opt-in and require explicit approval.
- Never commit `.env*` files, never print secret values into chat or logs.
```

Replace `<PROJECT>` with this repo's name as registered in EnvSeal.

> Why it helps: the agent reasons about a reference while the operating system
> mediates access to the value for one trusted child process.

---

## 2. Prompt: set up EnvSeal across all your projects

Paste this to your AI agent to onboard a whole machine:

```text
Install and set up EnvSeal as a local-first developer secret broker.

1. Install `envseal-vault` and Gitleaks, then run `envseal doctor`.
2. Do not read or import existing secret values automatically.
3. Show the human the `envseal secret put <PROJECT>/<ENV>/<NAME>` commands they
   should run for approved keys.
4. Configure `envseal guard staged --repo .` in each project's existing hook
   manager; never overwrite a shared hook.
5. Verify with a synthetic secret fixture and full output redaction.

Rules: local-only by default; never print values; never push ciphertext or
plaintext to Git without explicit approval.
```

---

## 3. Prompt: restore secrets on a new machine

```text
This machine is fresh. Restore my EnvSeal setup:

1. Install EnvSeal and run `envseal doctor`.
2. List expected reference names from my separately protected recovery metadata.
3. Let me re-add local-only values through `envseal secret put`; never ask me to
   paste them into chat or command arguments.
4. Only if I explicitly approve the legacy portable vault, restore the age
   identity and SOPS ciphertext, then run a dry-run before writing `.env` files.
```

---

## 4. Browse keys without decrypting

`envseal report` writes a self-contained static HTML dashboard of every
project and **key name** (never values). Key names can still reveal providers
or architecture, so review the report before sharing it:

```bash
envseal report -o envseal-report.html
```

---

## House rule for any agent

**Agents reason about references, not values.** `secret list`, `list`, `report`,
and `diff` are value-free by design, but their metadata may still be sensitive.
Inject values only into a trusted child process with `envseal run`; use legacy
`.env` materialization only when a target cannot consume runtime injection.
