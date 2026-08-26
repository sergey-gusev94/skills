# Council skills

Three related skills for convening multi-agent councils:

- **`council/`** — Codex skill (`$council`): a ten-subagent inquiry for any question, decision, plan, or investigation, critically synthesized by the lead.
- **`review-council/`** — Codex skill (`$review-council`): the ten-subagent code-review variant.
- **`hybrid-council/`** — Claude Code skill (`/hybrid-council`): convenes three voices — a Fable adviser, an Opus adviser, and the Codex `$council` via `scripts/run-codex-council.sh` — then synthesizes one answer.

## Install

Everything is discovered through symlinks; the repo is the single source of truth.

```sh
# Codex skills
ln -s ~/repo/skills/council ~/.codex/skills/council
ln -s ~/repo/skills/review-council ~/.codex/skills/review-council

# Claude Code skill
ln -s ~/repo/skills/hybrid-council ~/.claude/skills/hybrid-council

# Claude Code adviser agents — required separately: Claude does not discover
# agents nested inside a skill directory
ln -s ~/repo/skills/hybrid-council/agents/council-fable.md ~/.claude/agents/council-fable.md
ln -s ~/repo/skills/hybrid-council/agents/council-opus.md ~/.claude/agents/council-opus.md
```

## Requirements

- Codex CLI on `PATH` (tested with 0.149.1).
- The Codex model defaults to `gpt-5.6-sol`; override per run with `CODEX_COUNCIL_MODEL`.
- `run-codex-council.sh` reports `STATUS=ok|degraded|failed`; `degraded` means fewer than ten Codex subagents completed (detected via a `COUNCIL_SUBAGENTS=<n>` sentinel line the script requires in the answer).
