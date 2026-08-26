# Council skills

Three related skills for convening multi-agent councils:

- **`council/`** — Codex skill (`$council`): a ten-subagent inquiry for any question, decision, plan, or investigation, critically synthesized by the lead.
- **`review-council/`** — Codex skill (`$review-council`): the ten-subagent code-review variant.
- **`hybrid-council/`** — Claude Code skill (`/hybrid-council`): convenes three voices — a Fable adviser, an Opus adviser, and the Codex `$council` via `scripts/run-codex-council.sh` — then synthesizes one answer.

## Install

Everything is discovered through symlinks; the repo is the single source of truth.

```sh
mkdir -p ~/.codex/skills ~/.claude/skills ~/.claude/agents

# Codex skills (~/.codex/skills is the tested location; newer Codex versions
# also discover user skills under ~/.agents/skills)
ln -sfn ~/repo/skills/council ~/.codex/skills/council
ln -sfn ~/repo/skills/review-council ~/.codex/skills/review-council

# Claude Code skill
ln -sfn ~/repo/skills/hybrid-council ~/.claude/skills/hybrid-council

# Claude Code adviser agents — required separately: Claude does not discover
# agents nested inside a skill directory
ln -sfn ~/repo/skills/hybrid-council/agents/council-fable.md ~/.claude/agents/council-fable.md
ln -sfn ~/repo/skills/hybrid-council/agents/council-opus.md ~/.claude/agents/council-opus.md
```

`ln -sfn` makes the block safe to rerun: plain `ln -s` fails on an existing link and silently nests a new link inside an existing directory.

## Requirements

- Codex CLI on `PATH` (tested with 0.150.0). The council needs Codex's `multi_agent` feature, stable and on by default in 0.150.0 — check with `codex features list`; without it the council silently collapses to a single-model answer.
- `hybrid-council` invokes the Codex `$council` skill, so the `council` symlink above must also be installed; without it the Codex voice degrades to a single-model answer.
- Ten parallel subagents need `[agents] max_concurrent_threads_per_session` of at least 10 in `~/.codex/config.toml`.
- The Codex model defaults to `gpt-5.6-sol` in `run-codex-council.sh`; override per run with `CODEX_COUNCIL_MODEL`. Direct `$council` and `$review-council` invocations use the active Codex model.
- Read-only is enforced by instruction, not by sandboxing: the script runs Codex with full access (so subagents have network and web search), the Claude advisers keep Bash, and every voice is told not to change anything.
- `run-codex-council.sh` reports `STATUS=ok|degraded|unverified|failed` plus a `SUBAGENTS=<n|unknown>` count: `degraded` means fewer than ten Codex subagents completed (`0` means no council ran), and `unverified` means the answer is usable but the count could not be confirmed. Both derive from a model-reported `COUNCIL_SUBAGENTS=<n>` sentinel line the script asks for in the answer, so even `ok` is self-reported, not independently verified. Resumed follow-ups always report `unverified` because completeness is not re-checked.
